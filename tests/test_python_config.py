from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from novel_spider.config import load_batch_config, load_config, resolve_config_path
from novel_spider.models import ChapterLink
from novel_spider.parser import parse_book_chapters, parse_book_name, parse_chapter


class PythonConfigTest(unittest.TestCase):
    def test_loads_existing_python_site_config_by_name(self) -> None:
        config = load_config("jinyong-net")

        self.assertEqual(config.site.name, "金庸小说全集网")
        self.assertEqual(config.book_url_template, "http://jinyong.net.cn/{id}/")
        self.assertEqual(config.book.chapters.url_selector, "a[href]")
        self.assertEqual(config.request.delay_seconds, 1.0)
        self.assertEqual(config.request.timeout_seconds, 20.0)
        self.assertEqual(config.request.retries, 2)
        self.assertIsNotNone(config.hooks.format_book_chapters)
        self.assertIsNotNone(config.hooks.format_chapter_content)

    def test_loads_python_template_config(self) -> None:
        config = load_config("site-template")

        self.assertEqual(config.site.name, "example")
        self.assertEqual(config.book_url_template, "https://example.com/{id}/")

    def test_loads_existing_python_batch_config_by_name(self) -> None:
        jobs = load_batch_config("jinyong-net-batch")

        self.assertEqual(len(jobs), 45)
        self.assertEqual(jobs[0].config.book_url, "http://jinyong.net.cn/old_feihuwaizhuan/")

    def test_existing_site_config_filters_chapters_with_format_hook(self) -> None:
        config = load_config("jinyong-net")
        links = parse_book_chapters(
            "http://jinyong.net.cn/demo/",
            """
<dl class="cat_box">
  <dd><a href="index.html">目录</a></dd>
  <dd><a href="001.html">第一章</a></dd>
  <dd><a href="default.html">首页</a></dd>
</dl>
""",
            config,
        )

        self.assertEqual(links, [ChapterLink(index=1, title="第一章", url="http://jinyong.net.cn/demo/001.html")])

    def test_loads_flat_python_config_and_hooks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "example.py"
            config_path.write_text(
                """
CONFIG = {
    "site": {
        "name": "example",
    },
    "book": {
        "url": "https://example.com/book/",
        "chapters": {
            "selector": "li",
            "url_selector": "a[href]",
            "name_selector": "a",
        },
    },
    "chapter": {
        "content_selector": ".content",
    },
}


def parse_book_name(url, html, config):
    return "Hooked Book"


def format_chapter_content(content, config):
    return "\\n\\n".join(line for line in content.splitlines() if "drop me" not in line)
""",
                encoding="utf-8",
            )

            config = load_config(config_path)
            chapter = parse_chapter(
                '<h1>One</h1><div class="content">keep me<br>drop me</div>',
                ChapterLink(index=1, title="fallback", url="https://example.com/1"),
                config,
            )

        self.assertEqual(parse_book_name("https://example.com/book/", "<title>Fallback</title>", config), "Hooked Book")
        self.assertEqual(chapter.content, "keep me")

    def test_default_parse_book_chapters_uses_nested_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "example.py"
            config_path.write_text(
                """
CONFIG = {
    "site": {"name": "example"},
    "book": {
        "url": "https://example.com/book/",
        "chapters": {
            "selector": ".chapter",
            "url_selector": "a[href]",
            "name_selector": "a",
        },
    },
    "chapter": {"content_selector": ".content"},
}
""",
                encoding="utf-8",
            )

            config = load_config(config_path)
            links = parse_book_chapters(
                "https://example.com/book/",
                '<div class="chapter"><a href="1.html" title="Chapter One">ignored</a></div>',
                config,
            )

        self.assertEqual(links, [ChapterLink(index=1, title="Chapter One", url="https://example.com/book/1.html")])

    def test_batch_config_supports_string_and_dict_books(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            site_path = temp_path / "site.py"
            batch_path = temp_path / "batch.py"
            site_path.write_text(
                """
CONFIG = {
    "site": {
        "name": "example",
    },
    "book": {
        "url_template": "https://example.com/{id}/",
        "chapters": {
            "selector": "li",
            "url_selector": "a[href]",
            "name_selector": "a",
        },
    },
    "chapter": {
        "content_selector": ".content",
    },
}
""",
                encoding="utf-8",
            )
            batch_path.write_text(
                """
SITE_CONFIG = "site"
BOOKS = [
    "first",
    {"id": "second", "name": "Second Book", "output": "second.txt"},
]
""",
                encoding="utf-8",
            )

            jobs = load_batch_config(batch_path)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0].config.book_url, "https://example.com/first/")
        self.assertIsNone(jobs[0].config.book_name)
        self.assertEqual(jobs[1].config.book_url, "https://example.com/second/")
        self.assertEqual(jobs[1].config.book_name, "Second Book")
        self.assertEqual(jobs[1].output, "second.txt")

    def test_resolve_adds_python_suffix(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            config_path = temp_path / "same.py"
            config_path.write_text("CONFIG = {}", encoding="utf-8")

            resolved = resolve_config_path("same", temp_path)

        self.assertEqual(resolved, config_path)

    def test_json_config_is_rejected_even_when_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "old.json"
            config_path.write_text("{}", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_config(config_path)


if __name__ == "__main__":
    unittest.main()

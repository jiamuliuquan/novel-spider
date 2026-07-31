from __future__ import annotations

from urllib.parse import urlparse

from novel_spider.models import ChapterLink


CONFIG = {
    "site": {
        "name": "金庸小说全集网",
        "home": "http://jinyong.net.cn/",
        "desc": "金庸小说在线阅读站点",
    },
    "book": {
        "url_template": "http://jinyong.net.cn/{id}/",
        "name_selector": ".novel h1",
        "chapters": {
            "selector": ".cat_box dd",
            "url_selector": "a[href]",
            "name_selector": "a",
        },
    },
    "chapter": {
        "content_selector": ".post .entry p",
    },
    "encoding": "UTF-8",
}


# 目录里如果混入 index/default 这类非章节页，就在 hook 里做站点适配，
# 不再把 include/exclude 正则做成所有配置都要理解的通用字段。
def format_book_chapters(chapters: list[ChapterLink], config):
    clean_links: list[ChapterLink] = []

    for link in chapters:
        file_name = urlparse(link.url).path.rsplit("/", 1)[-1].lower()
        if not file_name.endswith((".htm", ".html")):
            continue
        if file_name in {"index.htm", "index.html", "default.htm", "default.html"}:
            continue
        clean_links.append(ChapterLink(index=len(clean_links) + 1, title=link.title, url=link.url))

    return clean_links


# 这个站的正文尾部经常混入站点推广和导航；这些规则跟站点强相关，
# 放在 format_chapter_content 里比塞进 CONFIG 字典更直观。
_STOP_BEFORE_TEXT = (
    "一秒钟记住本站网址",
    "金庸小说改编的各个版本影视作品",
)


def format_chapter_content(content: str, config):
    clean_lines: list[str] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        if any(marker in line for marker in _STOP_BEFORE_TEXT):
            break
        if "上一章" in line and "下一章" in line:
            continue
        if "返回目录" in line:
            continue
        if line.startswith("字体"):
            continue
        clean_lines.append(line)
    return "\n\n".join(clean_lines)

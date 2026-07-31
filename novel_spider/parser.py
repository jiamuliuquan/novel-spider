from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup

from .config import SpiderConfig
from .models import Chapter, ChapterLink


def parse_book_name(url: str, html: str, config: SpiderConfig) -> str | None:
    # parse_* hook 负责“从 URL/HTML 里拿到原始结果”；返回 None 就走默认解析。
    if config.hooks.parse_book_name:
        name = config.hooks.parse_book_name(url, html, config)
        if name is None:
            name = default_parse_book_name(url, html, config)
    else:
        name = default_parse_book_name(url, html, config)

    if not name:
        return None

    name = default_format_book_name(name, config)
    if config.hooks.format_book_name:
        # format_* hook 负责“后置整理”；返回 None 表示保留当前结果。
        hook_name = config.hooks.format_book_name(name, config)
        if hook_name is not None:
            name = default_format_book_name(hook_name, config)

    return name


def default_parse_book_name(url: str, html: str, config: SpiderConfig) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    selectors = []
    if config.book.name_selector:
        selectors.append(config.book.name_selector)
    selectors.append("h1, title")

    for selector in selectors:
        for node in soup.select(selector):
            name = _normalize_line(node.get_text(" ", strip=True))
            if name:
                return name

    return None


def parse_book_chapters(url: str, html: str, config: SpiderConfig) -> list[ChapterLink]:
    # 复杂目录页可以完全接管解析；普通目录页只需要配置 selector/url_selector/name_selector。
    if config.hooks.parse_book_chapters:
        links = config.hooks.parse_book_chapters(url, html, config)
        if links is None:
            links = default_parse_book_chapters(url, html, config)
    else:
        links = default_parse_book_chapters(url, html, config)

    links = _normalize_chapter_links(links)
    if config.hooks.format_book_chapters:
        hook_links = config.hooks.format_book_chapters(links, config)
        if hook_links is not None:
            links = _normalize_chapter_links(hook_links)

    return links


def default_parse_book_chapters(url: str, html: str, config: SpiderConfig) -> list[ChapterLink]:
    soup = BeautifulSoup(html, "html.parser")
    chapters = config.book.chapters
    links: list[ChapterLink] = []

    for item in soup.select(chapters.selector):
        url_node = item.select_one(chapters.url_selector)
        name_node = item.select_one(chapters.name_selector) or url_node
        if url_node is None or name_node is None:
            continue

        href = url_node.get("href")  # type: ignore[attr-defined]
        title = _node_label(name_node)
        if not href or not title:
            continue

        chapter_url = urldefrag(urljoin(url, str(href))).url
        links.append(ChapterLink(index=len(links) + 1, title=title, url=chapter_url))

    return links


def parse_chapter(html: str, link: ChapterLink, config: SpiderConfig) -> Chapter:
    content = parse_chapter_content(link.url, html, config)
    if not content:
        raise ValueError(f"No content extracted from {link.url}")

    return Chapter(index=link.index, title=_clean_title(link.title), url=link.url, content=content)


def parse_chapter_content(url: str, html: str, config: SpiderConfig) -> str:
    # 章节正文可能有分页、懒加载或奇怪 DOM；需要时由 parse hook 自己解析。
    if config.hooks.parse_chapter_content:
        content = config.hooks.parse_chapter_content(url, html, config)
        if content is None:
            content = default_parse_chapter_content(url, html, config)
    else:
        content = default_parse_chapter_content(url, html, config)

    content = default_format_chapter_content(content)
    if config.hooks.format_chapter_content:
        hook_content = config.hooks.format_chapter_content(content, config)
        if hook_content is not None:
            content = default_format_chapter_content(hook_content)

    return content


def default_parse_chapter_content(url: str, html: str, config: SpiderConfig) -> str:
    soup = BeautifulSoup(html, "html.parser")
    content_nodes = soup.select(config.chapter.content_selector)
    if not content_nodes:
        content_nodes = [soup]

    lines: list[str] = []
    for node in content_nodes:
        lines.extend(_extract_lines(node))
    return _join_lines(lines)


def default_format_book_name(name: str, config: SpiderConfig) -> str | None:
    name = _normalize_line(name)
    if not name:
        return None

    if config.book.name_regex:
        match = re.search(config.book.name_regex, name)
        if match:
            groups = [group for group in match.groups() if group]
            name = groups[0] if groups else match.group(0)

    for separator in ("_", "|", " - "):
        if separator in name:
            name = name.split(separator, 1)[0]

    name = re.sub(r"(?:小说目录|目录|小说全文阅读|全文阅读)$", "", name)
    name = name.strip(" \t\r\n-_｜|")
    return name or None


def default_format_chapter_content(content: str) -> str:
    return _join_lines(_normalize_content_lines(content.splitlines()))


def _normalize_chapter_links(links: list[ChapterLink]) -> list[ChapterLink]:
    clean_links: list[ChapterLink] = []
    seen: set[str] = set()

    for link in links:
        title = _clean_title(link.title)
        url = str(link.url)
        if not url or url in seen:
            continue

        seen.add(url)
        clean_links.append(ChapterLink(index=len(clean_links) + 1, title=title, url=url))

    return clean_links


def _node_label(node: object) -> str:
    for attr in ("title", "alt"):
        value = node.get(attr)  # type: ignore[attr-defined]
        if value:
            return _normalize_line(str(value))
    return _normalize_line(node.get_text(" ", strip=True))  # type: ignore[attr-defined]


def _extract_lines(node: object) -> list[str]:
    text = node.get_text("\n", strip=True)  # type: ignore[attr-defined]
    return _normalize_content_lines(text.splitlines())


def _normalize_content_lines(lines: list[str]) -> list[str]:
    clean_lines: list[str] = []
    for line in lines:
        normalized = _normalize_line(str(line))
        if normalized:
            clean_lines.append(normalized)
    return clean_lines


def _join_lines(lines: list[str]) -> str:
    return "\n\n".join(lines)


def _normalize_line(line: str) -> str:
    line = line.replace("\u3000", " ")
    line = re.sub(r"[ \t]+", " ", line)
    return line.strip()


def _clean_title(title: str) -> str:
    title = _normalize_line(title)
    return title or "Untitled Chapter"

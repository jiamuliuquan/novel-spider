from __future__ import annotations

import re
from urllib.parse import urldefrag, urljoin

from bs4 import BeautifulSoup

from .config import SpiderConfig
from .models import Chapter, ChapterLink


def parse_book_name(html: str, config: SpiderConfig) -> str | None:
    soup = BeautifulSoup(html, "html.parser")
    selectors = []
    if config.selectors.book_name:
        selectors.append(config.selectors.book_name)
    selectors.append("h1, title")

    for selector in selectors:
        for node in soup.select(selector):
            name = _clean_book_name(node.get_text(" ", strip=True), config)
            if name:
                return name

    return None


def parse_chapter_links(html: str, base_url: str, config: SpiderConfig) -> list[ChapterLink]:
    soup = BeautifulSoup(html, "html.parser")
    include = re.compile(config.filters.include_url_regex) if config.filters.include_url_regex else None
    exclude = re.compile(config.filters.exclude_url_regex) if config.filters.exclude_url_regex else None
    links: list[ChapterLink] = []
    seen: set[str] = set()

    for anchor in soup.select(config.selectors.chapter_links):
        href = anchor.get("href")
        title = anchor.get_text(" ", strip=True)
        if not href or not title:
            continue

        url = urldefrag(urljoin(base_url, href)).url
        if include and not include.search(url):
            continue
        if exclude and exclude.search(url):
            continue
        if url in seen:
            continue

        seen.add(url)
        links.append(ChapterLink(index=len(links) + 1, title=title, url=url))

    return links


def parse_chapter(html: str, link: ChapterLink, config: SpiderConfig) -> Chapter:
    soup = BeautifulSoup(html, "html.parser")

    for selector in config.selectors.remove:
        for node in soup.select(selector):
            node.decompose()

    title_node = soup.select_one(config.selectors.chapter_title)
    title = title_node.get_text(" ", strip=True) if title_node else link.title
    content_nodes = soup.select(config.selectors.chapter_content)
    content = _extract_text_from_nodes(content_nodes, config) if content_nodes else _extract_text(soup, config)

    if not content:
        raise ValueError(f"No content extracted from {link.url}")

    return Chapter(index=link.index, title=_clean_title(title), url=link.url, content=content)


def _extract_text_from_nodes(nodes: list[object], config: SpiderConfig) -> str:
    lines: list[str] = []
    for node in nodes:
        lines.extend(_extract_lines(node))
    return _join_lines(_apply_content_filters(lines, config))


def _extract_text(node: object, config: SpiderConfig) -> str:
    return _join_lines(_apply_content_filters(_extract_lines(node), config))


def _extract_lines(node: object) -> list[str]:
    text = node.get_text("\n", strip=True)  # type: ignore[attr-defined]
    lines = [_normalize_line(line) for line in text.splitlines()]
    return [line for line in lines if line]


def _apply_content_filters(lines: list[str], config: SpiderConfig) -> list[str]:
    stop_patterns = [re.compile(pattern) for pattern in config.content_filters.stop_before_text_regex]
    drop_patterns = [re.compile(pattern) for pattern in config.content_filters.drop_line_regex]
    clean_lines: list[str] = []

    for line in lines:
        if any(pattern.search(line) for pattern in stop_patterns):
            break
        if any(pattern.search(line) for pattern in drop_patterns):
            continue
        clean_lines.append(line)

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


def _clean_book_name(name: str, config: SpiderConfig) -> str | None:
    name = _normalize_line(name)
    if not name:
        return None

    if config.book_name_regex:
        match = re.search(config.book_name_regex, name)
        if match:
            groups = [group for group in match.groups() if group]
            name = groups[0] if groups else match.group(0)

    for separator in ("_", "|", " - "):
        if separator in name:
            name = name.split(separator, 1)[0]

    name = re.sub(r"(?:小说目录|目录|小说全文阅读|全文阅读)$", "", name)
    name = name.strip(" \t\r\n-_｜|")
    return name or None

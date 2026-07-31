from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

from .config import SpiderConfig
from .fetcher import Fetcher
from .models import Chapter, ChapterLink
from .parser import parse_book_name, parse_chapter, parse_chapter_links
from .progress import ChapterCache, ProgressStore

LogFn = Callable[[str], None]


class NovelCrawler:
    def __init__(self, config: SpiderConfig, state_dir: str | Path = "state", log: LogFn | None = None) -> None:
        self.config = config
        self.log = log or (lambda message: None)
        self.state_dir = Path(state_dir)
        self.book_name = config.book_name
        self.progress: ProgressStore | None = None
        self.cache: ChapterCache | None = None
        self.fetcher = Fetcher(config.request, encoding=config.encoding)

    def close(self) -> None:
        self.fetcher.close()

    def discover(self) -> list[ChapterLink]:
        book_url = self._book_url()
        self.log(f"Fetching catalog: {book_url}")
        result = self.fetcher.fetch(book_url)
        self._resolve_book_name(result.html)
        self._ensure_state()
        links = parse_chapter_links(result.html, result.url, self.config)
        if not links:
            raise ValueError("No chapter links found. Check selectors.chapter_links and filters.")
        self.log(f"Found {len(links)} chapter links.")
        return links

    def crawl(self, limit: int | None = None, force: bool = False) -> list[Chapter]:
        links = self.discover()
        if limit is not None:
            links = links[:limit]

        chapters: list[Chapter] = []
        for link in links:
            progress = self._progress()
            cache = self._cache()
            if progress.is_done(link.url) and not force:
                cached = cache.load(link.index)
                if cached is not None:
                    chapters.append(cached)
                    self.log(f"Use cache: {link.index}. {link.title}")
                    continue
                self.log(f"Cache missing, refetching: {link.index}. {link.title}")

            self.log(f"Fetching chapter {link.index}: {link.title}")
            result = self.fetcher.fetch(link.url)
            chapter = parse_chapter(result.html, link, self.config)
            chapters.append(chapter)
            cache.save(chapter)
            progress.mark_done(link.url)

        return chapters

    def _resolve_book_name(self, catalog_html: str) -> None:
        if self.book_name:
            return

        self.book_name = parse_book_name(catalog_html, self.config) or _name_from_url(self._book_url())
        self.log(f"Book name: {self.book_name}")

    def _ensure_state(self) -> None:
        if self.progress is not None and self.cache is not None:
            return

        state_name = f"{_slug(self.config.site_name)}-{_slug(self.book_name or 'book')}"
        progress_file = self.state_dir / f"{state_name}.json"
        self.progress = ProgressStore(progress_file)
        self.cache = ChapterCache(self.state_dir / state_name)

    def _progress(self) -> ProgressStore:
        if self.progress is None:
            self._ensure_state()
        if self.progress is None:
            raise RuntimeError("Progress store was not initialized.")
        return self.progress

    def _cache(self) -> ChapterCache:
        if self.cache is None:
            self._ensure_state()
        if self.cache is None:
            raise RuntimeError("Chapter cache was not initialized.")
        return self.cache

    def _book_url(self) -> str:
        if not self.config.book_url:
            raise ValueError("Book URL was not resolved. Provide --id for configs with book_url_template.")
        return self.config.book_url


def _slug(value: str) -> str:
    chars = []
    for char in value.lower():
        if char.isalnum():
            chars.append(char)
        elif chars and chars[-1] != "-":
            chars.append("-")
    return "".join(chars).strip("-") or "novel"


def _name_from_url(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path.rstrip("/")
    if path:
        return path.rsplit("/", 1)[-1] or parsed.netloc
    return parsed.netloc or "book"

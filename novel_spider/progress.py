from __future__ import annotations

import json
from pathlib import Path

from .models import Chapter


class ProgressStore:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._done = self._load()

    def is_done(self, url: str) -> bool:
        return url in self._done

    def mark_done(self, url: str) -> None:
        self._done.add(url)
        self._save()

    def _load(self) -> set[str]:
        if not self.path.exists():
            return set()
        with self.path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return set(data.get("done_urls", []))

    def _save(self) -> None:
        with self.path.open("w", encoding="utf-8") as file:
            json.dump({"done_urls": sorted(self._done)}, file, ensure_ascii=False, indent=2)


class ChapterCache:
    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def load(self, index: int) -> Chapter | None:
        path = self._path(index)
        if not path.exists():
            return None
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
        return Chapter(
            index=int(data["index"]),
            title=str(data["title"]),
            url=str(data["url"]),
            content=str(data["content"]),
        )

    def save(self, chapter: Chapter) -> None:
        data = {
            "index": chapter.index,
            "title": chapter.title,
            "url": chapter.url,
            "content": chapter.content,
        }
        with self._path(chapter.index).open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)

    def _path(self, index: int) -> Path:
        return self.directory / f"{index:04d}.json"

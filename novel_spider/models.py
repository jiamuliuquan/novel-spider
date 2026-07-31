from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterLink:
    index: int
    title: str
    url: str


@dataclass(frozen=True)
class Chapter:
    index: int
    title: str
    url: str
    content: str


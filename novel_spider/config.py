from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class RequestConfig:
    delay_seconds: float = 1.0
    timeout_seconds: float = 20.0
    retries: int = 2
    user_agent: str = "novel-spider/0.1 (+personal archival use)"
    respect_robots: bool = True


@dataclass(frozen=True)
class SelectorConfig:
    chapter_links: str
    chapter_title: str
    chapter_content: str
    book_name: str | None = None
    remove: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class FilterConfig:
    include_url_regex: str | None = None
    exclude_url_regex: str | None = None


@dataclass(frozen=True)
class ContentFilterConfig:
    stop_before_text_regex: list[str] = field(default_factory=list)
    drop_line_regex: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SpiderConfig:
    site_name: str
    book_url: str | None
    book_url_template: str | None
    book_name: str | None
    book_name_regex: str | None
    encoding: str | None
    request: RequestConfig
    selectors: SelectorConfig
    filters: FilterConfig
    content_filters: ContentFilterConfig


@dataclass(frozen=True)
class BatchJob:
    config: SpiderConfig
    output: str | None = None


def resolve_config_path(config: str | Path, configs_dir: str | Path = "configs") -> Path:
    raw_path = Path(config)
    configs_path = Path(configs_dir)
    candidates: list[Path] = []

    if raw_path.is_absolute() or raw_path.parent != Path("."):
        candidates.append(raw_path)
        if not raw_path.suffix:
            candidates.append(raw_path.with_suffix(".json"))
    else:
        if raw_path.suffix:
            candidates.extend(
                [
                    raw_path,
                    configs_path / raw_path,
                    Path.cwd() / "configs" / raw_path,
                    Path(__file__).resolve().parent.parent / "configs" / raw_path,
                ]
            )
        else:
            config_file = raw_path.with_suffix(".json")
            candidates.extend(
                [
                    configs_path / config_file,
                    Path.cwd() / "configs" / config_file,
                    Path(__file__).resolve().parent.parent / "configs" / config_file,
                    raw_path,
                    config_file,
                ]
            )

    for candidate in candidates:
        if candidate.exists():
            return candidate

    raise FileNotFoundError(f"Config not found: {config}")


def load_config(path: str | Path) -> SpiderConfig:
    config_path = resolve_config_path(path)
    with config_path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    return _load_config_from_dict(raw, config_path)


def load_batch_config(path: str | Path) -> list[BatchJob]:
    config_path = resolve_config_path(path)
    with config_path.open("r", encoding="utf-8") as file:
        raw = json.load(file)

    _require(raw, "config", config_path)
    books = raw.get("books")
    if not isinstance(books, list) or not books:
        raise ValueError(f"Batch config must contain a non-empty 'books' list in {config_path}")

    return _load_referenced_batch_config(raw, config_path)


def build_book_config(config: SpiderConfig, book_id: str | None = None, book_name: str | None = None) -> SpiderConfig:
    resolved_name = _optional_str(book_name) or config.book_name
    if not book_id:
        if config.book_url:
            return replace(config, book_name=resolved_name)
        raise ValueError("Book id is required because this config only has book_url_template.")

    template = config.book_url_template
    if template is None and config.book_url and "{id}" in config.book_url:
        template = config.book_url
    if template is None:
        raise ValueError("Config must define book_url_template to use --id.")

    return replace(
        config,
        book_url=template.format(id=book_id, book_id=book_id),
        book_name=resolved_name,
    )


def _load_config_from_dict(raw: dict[str, Any], config_path: Path) -> SpiderConfig:
    _require(raw, "site_name", config_path)
    _require(raw, "selectors", config_path)
    book_url = _optional_str(raw.get("book_url"))
    book_url_template = _optional_str(raw.get("book_url_template"))
    if not book_url and not book_url_template:
        raise ValueError(f"Config must define 'book_url' or 'book_url_template' in {config_path}")

    request = raw.get("request") or {}
    selectors = raw["selectors"]
    filters = raw.get("filters") or {}
    content_filters = raw.get("content_filters") or {}

    for key in ("chapter_links", "chapter_title", "chapter_content"):
        _require(selectors, key, config_path)

    return SpiderConfig(
        site_name=str(raw["site_name"]),
        book_url=book_url,
        book_url_template=book_url_template,
        book_name=_optional_str(raw.get("book_name")),
        book_name_regex=_optional_str(raw.get("book_name_regex")),
        encoding=raw.get("encoding"),
        request=RequestConfig(
            delay_seconds=float(request.get("delay_seconds", 1.0)),
            timeout_seconds=float(request.get("timeout_seconds", 20.0)),
            retries=int(request.get("retries", 2)),
            user_agent=str(request.get("user_agent", "novel-spider/0.1 (+personal archival use)")),
            respect_robots=bool(request.get("respect_robots", True)),
        ),
        selectors=SelectorConfig(
            chapter_links=str(selectors["chapter_links"]),
            chapter_title=str(selectors["chapter_title"]),
            chapter_content=str(selectors["chapter_content"]),
            book_name=_optional_str(selectors.get("book_name")),
            remove=[str(item) for item in selectors.get("remove", [])],
        ),
        filters=FilterConfig(
            include_url_regex=_optional_str(filters.get("include_url_regex")),
            exclude_url_regex=_optional_str(filters.get("exclude_url_regex")),
        ),
        content_filters=ContentFilterConfig(
            stop_before_text_regex=_str_list(content_filters.get("stop_before_text_regex", [])),
            drop_line_regex=_str_list(content_filters.get("drop_line_regex", [])),
        ),
    )


def _load_referenced_batch_config(raw: dict[str, Any], config_path: Path) -> list[BatchJob]:
    base_config = load_config(resolve_config_path(str(raw["config"]), config_path.parent))
    jobs: list[BatchJob] = []

    for index, book in enumerate(raw["books"], start=1):
        if not isinstance(book, dict):
            raise ValueError(f"Batch book #{index} must be an object in {config_path}")

        book_id = _optional_str(book.get("id"))
        if not book_id:
            raise ValueError(f"Batch book #{index} is missing required field 'id' in {config_path}")

        jobs.append(
            BatchJob(
                config=build_book_config(base_config, book_id=book_id, book_name=_optional_str(book.get("name"))),
                output=_optional_str(book.get("output")),
            )
        )

    return jobs

def _require(data: dict[str, Any], key: str, path: Path) -> None:
    if key not in data or data[key] in (None, ""):
        raise ValueError(f"Missing required config field '{key}' in {path}")


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _str_list(value: Any) -> list[str]:
    if value in (None, ""):
        return []
    if isinstance(value, list):
        return [str(item) for item in value if item not in (None, "")]
    return [str(value)]

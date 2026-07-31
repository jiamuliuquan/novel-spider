from __future__ import annotations

import hashlib
import importlib.util
import sys
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from pathlib import Path
from types import ModuleType
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .models import ChapterLink


_CONFIG_SUFFIX = ".py"
_DEFAULT_USER_AGENT = "novel-spider/0.1 (+personal archival use)"


@dataclass(frozen=True)
class RequestConfig:
    delay_seconds: float = 1.0
    timeout_seconds: float = 20.0
    retries: int = 2
    user_agent: str = _DEFAULT_USER_AGENT
    respect_robots: bool = True


@dataclass(frozen=True)
class SiteConfig:
    name: str
    home: str | None = None
    desc: str | None = None


@dataclass(frozen=True)
class BookChaptersConfig:
    selector: str
    url_selector: str
    name_selector: str


@dataclass(frozen=True)
class BookConfig:
    url: str | None
    url_template: str | None
    name: str | None
    name_regex: str | None
    name_selector: str | None
    chapters: BookChaptersConfig


@dataclass(frozen=True)
class ChapterConfig:
    content_selector: str


@dataclass(frozen=True)
class ConfigHooks:
    parse_book_name: Callable[[str, str, "SpiderConfig"], str | None] | None = None
    format_book_name: Callable[[str, "SpiderConfig"], str | None] | None = None
    parse_book_chapters: Callable[[str, str, "SpiderConfig"], list["ChapterLink"] | None] | None = None
    format_book_chapters: Callable[[list["ChapterLink"], "SpiderConfig"], list["ChapterLink"] | None] | None = None
    parse_chapter_content: Callable[[str, str, "SpiderConfig"], str | None] | None = None
    format_chapter_content: Callable[[str, "SpiderConfig"], str | None] | None = None


@dataclass(frozen=True)
class SpiderConfig:
    site: SiteConfig
    book: BookConfig
    chapter: ChapterConfig
    encoding: str | None
    request: RequestConfig
    hooks: ConfigHooks = field(default_factory=ConfigHooks)

    @property
    def site_name(self) -> str:
        return self.site.name

    @property
    def book_url(self) -> str | None:
        return self.book.url

    @property
    def book_url_template(self) -> str | None:
        return self.book.url_template

    @property
    def book_name(self) -> str | None:
        return self.book.name


@dataclass(frozen=True)
class BatchJob:
    config: SpiderConfig
    output: str | None = None


def resolve_config_path(config: str | Path, configs_dir: str | Path = "configs") -> Path:
    """按项目习惯查找配置文件；现在只认 Python 配置。"""
    raw_path = Path(config)
    configs_path = Path(configs_dir)
    candidates: list[Path] = []

    if raw_path.is_absolute() or raw_path.parent != Path("."):
        candidates.append(raw_path)
        if not raw_path.suffix:
            candidates.append(raw_path.with_suffix(_CONFIG_SUFFIX))
    elif raw_path.suffix:
        candidates.extend(
            [
                raw_path,
                configs_path / raw_path,
                Path.cwd() / "configs" / raw_path,
                Path(__file__).resolve().parent.parent / "configs" / raw_path,
            ]
        )
    else:
        config_file = raw_path.with_suffix(_CONFIG_SUFFIX)
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

    raise FileNotFoundError(f"Config not found: {config}. Python configs must use .py files.")


def load_config(path: str | Path) -> SpiderConfig:
    config_path = resolve_config_path(path)
    module = _load_python_module(config_path)
    raw = _load_config_dict(module, config_path)

    return _load_site_config(raw, config_path, hooks=_load_hooks_from_module(module, config_path))


def load_batch_config(path: str | Path) -> list[BatchJob]:
    config_path = resolve_config_path(path)
    module = _load_python_module(config_path)
    site_ref = _optional_str(getattr(module, "SITE_CONFIG", None))
    books = getattr(module, "BOOKS", None)

    if not site_ref:
        raise ValueError(f"Batch config must define SITE_CONFIG in {config_path}")
    if not isinstance(books, list) or not books:
        raise ValueError(f"Batch config must define a non-empty BOOKS list in {config_path}")

    base_config = load_config(resolve_config_path(site_ref, config_path.parent))
    jobs: list[BatchJob] = []

    for index, book in enumerate(books, start=1):
        book_id, book_name, output = _load_batch_book(book, index, config_path)
        jobs.append(
            BatchJob(
                config=build_book_config(base_config, book_id=book_id, book_name=book_name),
                output=output,
            )
        )

    return jobs


def build_book_config(config: SpiderConfig, book_id: str | None = None, book_name: str | None = None) -> SpiderConfig:
    resolved_name = _optional_str(book_name) or config.book_name
    if not book_id:
        if config.book_url:
            return replace(config, book=replace(config.book, name=resolved_name))
        raise ValueError("Book id is required because this config only has book_url_template.")

    template = config.book_url_template
    if template is None and config.book_url and "{id}" in config.book_url:
        template = config.book_url
    if template is None:
        raise ValueError("Config must define book_url_template to use --id.")

    return replace(
        config,
        book=replace(
            config.book,
            url=template.format(id=book_id, book_id=book_id),
            name=resolved_name,
        ),
    )


def _load_python_module(config_path: Path) -> ModuleType:
    if config_path.suffix.lower() != _CONFIG_SUFFIX:
        raise ValueError(f"Unsupported config file type '{config_path.suffix}' in {config_path}. Use .py.")

    resolved_path = config_path.resolve()
    safe_stem = "".join(char if char.isalnum() else "_" for char in resolved_path.stem)
    path_token = hashlib.sha1(str(resolved_path).encode("utf-8")).hexdigest()[:12]
    module_name = f"_novel_spider_config_{safe_stem}_{path_token}"
    spec = importlib.util.spec_from_file_location(module_name, resolved_path)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load Python config: {config_path}")

    # 每个配置文件按路径生成独立模块名，避免同名配置互相污染。
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise RuntimeError(f"Failed to load Python config {config_path}: {exc}") from exc
    return module


def _load_config_dict(module: ModuleType, config_path: Path) -> dict[str, Any]:
    raw = getattr(module, "CONFIG", None)
    if not isinstance(raw, dict):
        raise ValueError(f"Site config must define CONFIG as a dict in {config_path}")
    return raw


def _load_hooks_from_module(module: ModuleType, config_path: Path) -> ConfigHooks:
    # hook 都是可选的：简单站点只写 CONFIG，复杂站点再按需补函数。
    return ConfigHooks(
        parse_book_name=_optional_hook(module, "parse_book_name", config_path),
        format_book_name=_optional_hook(module, "format_book_name", config_path),
        parse_book_chapters=_optional_hook(module, "parse_book_chapters", config_path),
        format_book_chapters=_optional_hook(module, "format_book_chapters", config_path),
        parse_chapter_content=_optional_hook(module, "parse_chapter_content", config_path),
        format_chapter_content=_optional_hook(module, "format_chapter_content", config_path),
    )


def _optional_hook(module: ModuleType, name: str, config_path: Path) -> Callable[..., Any] | None:
    hook = getattr(module, name, None)
    if hook is None:
        return None
    if not callable(hook):
        raise ValueError(f"Python config hook '{name}' must be callable in {config_path}")
    return hook


def _load_site_config(raw: dict[str, Any], config_path: Path, hooks: ConfigHooks | None = None) -> SpiderConfig:
    _require(raw, "site", config_path)
    _require(raw, "book", config_path)
    _require(raw, "chapter", config_path)
    site = raw["site"]
    book = raw["book"]
    chapter = raw["chapter"]
    if not isinstance(site, dict):
        raise ValueError(f"Config field 'site' must be a dict in {config_path}")
    if not isinstance(book, dict):
        raise ValueError(f"Config field 'book' must be a dict in {config_path}")
    if not isinstance(chapter, dict):
        raise ValueError(f"Config field 'chapter' must be a dict in {config_path}")

    _require(site, "name", config_path, field_name="site.name")
    _require(book, "chapters", config_path, field_name="book.chapters")
    chapters = book["chapters"]
    if not isinstance(chapters, dict):
        raise ValueError(f"Config field 'book.chapters' must be a dict in {config_path}")
    for key in ("selector", "url_selector", "name_selector"):
        _require(chapters, key, config_path, field_name=f"book.chapters.{key}")
    _require(chapter, "content_selector", config_path, field_name="chapter.content_selector")

    book_url = _optional_str(book.get("url"))
    book_url_template = _optional_str(book.get("url_template"))
    if not book_url and not book_url_template:
        raise ValueError(f"Config must define 'book.url' or 'book.url_template' in {config_path}")

    # 外部配置按业务对象分组；这里再折成内部结构，避免爬虫主流程知道配置文件的写法。
    # 请求参数全部有默认值，站点配置里只有确实需要改时才写。
    return SpiderConfig(
        site=SiteConfig(
            name=str(site["name"]),
            home=_optional_str(site.get("home")),
            desc=_optional_str(site.get("desc")),
        ),
        book=BookConfig(
            url=book_url,
            url_template=book_url_template,
            name=_optional_str(book.get("name")),
            name_regex=_optional_str(book.get("name_regex")),
            name_selector=_optional_str(book.get("name_selector")),
            chapters=BookChaptersConfig(
                selector=str(chapters["selector"]),
                url_selector=str(chapters["url_selector"]),
                name_selector=str(chapters["name_selector"]),
            ),
        ),
        chapter=ChapterConfig(
            content_selector=str(chapter["content_selector"]),
        ),
        encoding=_optional_str(raw.get("encoding")),
        request=RequestConfig(
            delay_seconds=_float(raw, "delay_seconds", 1.0),
            timeout_seconds=_float(raw, "timeout_seconds", 20.0),
            retries=_int(raw, "retries", 2),
            user_agent=str(raw.get("user_agent", _DEFAULT_USER_AGENT)),
            respect_robots=_bool(raw, "respect_robots", True),
        ),
        hooks=hooks or ConfigHooks(),
    )


def _load_batch_book(book: Any, index: int, config_path: Path) -> tuple[str, str | None, str | None]:
    # 书单可以直接写字符串；需要书名或输出路径时再写 dict。
    if isinstance(book, str):
        book_id = _optional_str(book)
        if not book_id:
            raise ValueError(f"Batch book #{index} is empty in {config_path}")
        return book_id, None, None

    if not isinstance(book, dict):
        raise ValueError(f"Batch book #{index} must be a string or dict in {config_path}")

    book_id = _optional_str(book.get("id"))
    if not book_id:
        raise ValueError(f"Batch book #{index} is missing required field 'id' in {config_path}")
    return book_id, _optional_str(book.get("name")), _optional_str(book.get("output"))


def _require(data: dict[str, Any], key: str, path: Path, field_name: str | None = None) -> None:
    if key not in data or data[key] in (None, ""):
        raise ValueError(f"Missing required config field '{field_name or key}' in {path}")


def _optional_str(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)


def _float(data: dict[str, Any], key: str, default: float) -> float:
    value = data.get(key, default)
    if value in (None, ""):
        return default
    return float(value)


def _int(data: dict[str, Any], key: str, default: int) -> int:
    value = data.get(key, default)
    if value in (None, ""):
        return default
    return int(value)


def _bool(data: dict[str, Any], key: str, default: bool) -> bool:
    value = data.get(key, default)
    if value in (None, ""):
        return default
    return bool(value)

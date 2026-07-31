from __future__ import annotations

from pathlib import Path

from .models import Chapter


def export_chapters(chapters: list[Chapter], output: str | Path, book_name: str, file_format: str) -> None:
    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if file_format == "txt":
        content = _to_txt(chapters, book_name)
    elif file_format == "md":
        content = _to_markdown(chapters, book_name)
    else:
        raise ValueError(f"Unsupported output format: {file_format}")

    output_path.write_text(content, encoding="utf-8", newline="\n")


def _to_txt(chapters: list[Chapter], book_name: str) -> str:
    parts = [book_name, ""]
    for chapter in chapters:
        parts.extend([chapter.title, "", chapter.content, ""])
    return "\n".join(parts).strip() + "\n"


def _to_markdown(chapters: list[Chapter], book_name: str) -> str:
    parts = [f"# {book_name}", ""]
    for chapter in chapters:
        parts.extend([f"## {chapter.title}", "", chapter.content, ""])
    return "\n".join(parts).strip() + "\n"


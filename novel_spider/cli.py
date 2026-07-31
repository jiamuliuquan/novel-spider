from __future__ import annotations

import argparse
from pathlib import Path

from .config import BatchJob, build_book_config, load_batch_config, load_config
from .crawler import NovelCrawler
from .exporters import export_chapters


def main() -> None:
    parser = argparse.ArgumentParser(prog="novel-spider", description="Configurable novel crawler.")
    parser.add_argument("--config", "-c", required=True, help="Config name or path, without .json if it is under configs/.")
    parser.add_argument("--id", help="Book id used by the site config's book_url_template.")
    parser.add_argument("--name", help="Optional manual book name. Otherwise it is read from the catalog page.")
    parser.add_argument("--batch", action="store_true", help="Treat --config as a batch config.")
    parser.add_argument("--format", choices=["txt", "md"], default="txt", help="Output format.")
    parser.add_argument("--output", help="Single-book output file. Defaults to <output-dir>/<book_name>.<format>.")
    parser.add_argument("--output-dir", default="downloads", help="Directory for generated book files.")
    parser.add_argument("--state-dir", default="state", help="Directory for progress files.")
    parser.add_argument("--limit", type=int, help="Only crawl the first N chapters.")
    parser.add_argument("--force", action="store_true", help="Fetch chapters even if they are marked done.")
    parser.add_argument("--dry-run", action="store_true", help="Only print discovered chapter links.")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue with the next book after a batch failure.")

    args = parser.parse_args()

    if args.batch:
        _run_batch(args)
    else:
        _run_single(args)


def _run_single(args: argparse.Namespace) -> None:
    base_config = load_config(args.config)
    config = build_book_config(base_config, book_id=args.id, book_name=args.name)
    output = args.output
    _run_job(BatchJob(config=config, output=output), args)


def _run_batch(args: argparse.Namespace) -> None:
    if args.output:
        raise ValueError("--output is only available for single-book runs. Use --output-dir with --batch.")

    jobs = load_batch_config(args.config)
    failed = 0

    for index, job in enumerate(jobs, start=1):
        print(f"[{index}/{len(jobs)}] {job.config.book_url}")
        try:
            _run_batch_job(job, args)
        except Exception as exc:
            failed += 1
            print(f"Failed: {exc}")
            if not args.continue_on_error:
                raise

    if failed:
        raise SystemExit(1)


def _run_batch_job(job: BatchJob, args: argparse.Namespace) -> None:
    _run_job(job, args)


def _run_job(job: BatchJob, args: argparse.Namespace) -> None:
    crawler = NovelCrawler(job.config, state_dir=args.state_dir, log=print)
    try:
        if args.dry_run:
            links = crawler.discover()
            print(f"Book: {crawler.book_name}")
            for link in links[: args.limit]:
                print(f"{link.index:04d} {link.title} {link.url}")
            return

        chapters = crawler.crawl(limit=args.limit, force=args.force)
        if not chapters:
            print("No chapters exported.")
            return

        book_name = crawler.book_name or job.config.book_name or "book"
        output = job.output or _default_output(book_name, args.format, args.output_dir)
        export_chapters(chapters, output, book_name, args.format)
        print(f"Saved {len(chapters)} chapters to {output}")
    finally:
        crawler.close()


def _default_output(book_name: str, file_format: str, output_dir: str | Path = "downloads") -> str:
    safe_name = "".join(char if char.isalnum() else "-" for char in book_name).strip("-") or "book"
    return str(Path(output_dir) / f"{safe_name}.{file_format}")

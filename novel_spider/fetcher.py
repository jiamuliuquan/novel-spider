from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx

from .config import RequestConfig


@dataclass
class FetchResult:
    url: str
    html: str


class RobotsGuard:
    def __init__(self, user_agent: str) -> None:
        self.user_agent = user_agent
        self._parsers: dict[str, RobotFileParser] = {}

    def allowed(self, url: str) -> bool:
        parsed = urlparse(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        parser = self._parsers.get(origin)
        if parser is None:
            parser = RobotFileParser()
            parser.set_url(urljoin(origin, "/robots.txt"))
            try:
                parser.read()
            except Exception:
                return True
            self._parsers[origin] = parser
        return parser.can_fetch(self.user_agent, url)


class Fetcher:
    def __init__(self, config: RequestConfig, encoding: str | None = None) -> None:
        self.config = config
        self.encoding = encoding
        self._last_request_at = 0.0
        self._robots = RobotsGuard(config.user_agent)
        self._client = httpx.Client(
            follow_redirects=True,
            timeout=config.timeout_seconds,
            headers={"User-Agent": config.user_agent},
        )

    def close(self) -> None:
        self._client.close()

    def fetch(self, url: str) -> FetchResult:
        if self.config.respect_robots and not self._robots.allowed(url):
            raise PermissionError(f"Blocked by robots.txt: {url}")

        self._wait_for_rate_limit()
        last_error: Exception | None = None
        for attempt in range(self.config.retries + 1):
            try:
                response = self._client.get(url)
                response.raise_for_status()
                html = self._decode(response)
                return FetchResult(str(response.url), html)
            except Exception as exc:
                last_error = exc
                if attempt >= self.config.retries:
                    break
                time.sleep(min(2 ** attempt, 5))

        raise RuntimeError(f"Failed to fetch {url}: {last_error}") from last_error

    def _wait_for_rate_limit(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        delay = max(0.0, self.config.delay_seconds - elapsed)
        if delay:
            time.sleep(delay)
        self._last_request_at = time.monotonic()

    def _decode(self, response: httpx.Response) -> str:
        if self.encoding:
            return response.content.decode(self.encoding, errors="replace")

        encoding = _guess_encoding(response)
        return response.content.decode(encoding, errors="replace")


def _guess_encoding(response: httpx.Response) -> str:
    content_type = response.headers.get("content-type", "")
    for part in content_type.split(";"):
        part = part.strip().lower()
        if part.startswith("charset="):
            return part.split("=", 1)[1]

    sample = response.content[:4096].decode("ascii", errors="ignore").lower()
    marker = "charset="
    if marker in sample:
        after = sample.split(marker, 1)[1]
        return after.split('"', 1)[0].split("'", 1)[0].split(">", 1)[0].strip()

    return response.encoding or "utf-8"


"""Polite, resilient crawler for the department website and the documents it links to.

Design notes
------------
* Seeds come from ``sitemap.xml`` plus the home page; every discovered same-site link and
  every linked document (PDF/Office) is followed breadth-first.
* Requests are rate-limited, retried with exponential back-off + jitter, and use
  conditional GET (ETag / Last-Modified) so refreshes are cheap and kind to the server.
* Failures never abort a run. A URL that fails keeps its previous snapshot, so a flaky
  site can't silently erase knowledge.
"""

from __future__ import annotations

import asyncio
import logging
import random
import re
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import unquote, urldefrag, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

from advisor.config import Settings
from advisor.ingest.snapshots import PageRecord, SnapshotStore, utcnow

log = logging.getLogger("advisor.crawl")

DOCUMENT_EXT = (".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".csv", ".txt")
SKIP_EXT = (
    ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".ico", ".css", ".js", ".map", ".woff",
    ".woff2", ".ttf", ".eot", ".mp4", ".mp3", ".zip", ".rar", ".7z", ".exe", ".dmg", ".apk",
)
# Paths that never contain public knowledge (auth, admin, search, calendars, feeds ...).
DENY_PATH = re.compile(
    r"(login|logout|signin|admin|cgi-bin|wp-admin|wp-json|/feed|/tag/|/author/|/search|"
    r"\?replytocom|/print/|/api/|/assets/|/static/)",
    re.I,
)
# Query strings produce endless filter/pagination/calendar variants of the same content.
# Only these (path, parameter) pairs carry distinct knowledge and are worth fetching.
QUERY_ALLOW = {("/explore", "topic")}
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "fbclid"}


def normalize_url(url: str) -> str:
    url, _ = urldefrag(url.strip())
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if parts.port and parts.port not in (80, 443):
        host = f"{host}:{parts.port}"
    scheme = "https" if parts.scheme in ("http", "https", "") else parts.scheme
    path = unquote(parts.path) or "/"
    path = re.sub(r"/{2,}", "/", path)
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = "&".join(
        p for p in parts.query.split("&") if p and p.split("=")[0] not in TRACKING_PARAMS
    )
    return urlunsplit((scheme, host, path.replace(" ", "%20"), query, ""))


@dataclass
class CrawlReport:
    fetched: int = 0
    unchanged: int = 0
    failed: list[tuple[str, str]] = field(default_factory=list)
    skipped: int = 0
    external_links: set[str] = field(default_factory=set)

    def summary(self) -> str:
        return (
            f"fetched={self.fetched} unchanged={self.unchanged} failed={len(self.failed)} "
            f"skipped={self.skipped}"
        )


class Crawler:
    def __init__(self, settings: Settings, store: SnapshotStore):
        self.s = settings
        self.store = store
        site = urlsplit(settings.site_url)
        self.host = (site.hostname or "").lower()
        self.extra_hosts = {h.lower() for h in settings.extra_hosts}
        self._robots: dict[str, RobotFileParser | None] = {}
        self._sem = asyncio.Semaphore(settings.crawl_concurrency)
        self._last_request = 0.0
        self._pace_lock = asyncio.Lock()

    # ------------------------------------------------------------------ policy
    def wants(self, url: str, *, from_host: str | None) -> bool:
        """Should this URL be fetched at all?"""
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        path = parts.path.lower()
        if parts.scheme not in ("http", "https"):
            return False
        if path.endswith(SKIP_EXT):
            return False
        if DENY_PATH.search(parts.path + ("?" + parts.query if parts.query else "")):
            return False
        if parts.query and host == self.host:
            names = {p.split("=")[0] for p in parts.query.split("&")}
            if not any((parts.path, n) in QUERY_ALLOW for n in names) or len(names) > 1:
                return False
        if host == self.host:
            return True
        # Other QAU hosts: only documents linked from our own site, never a blind crawl.
        if host in self.extra_hosts and from_host == self.host:
            return path.endswith(DOCUMENT_EXT) or self._looks_relevant_external(parts)
        return False

    @staticmethod
    def _looks_relevant_external(parts) -> bool:
        blob = (parts.path + "?" + parts.query).lower()
        return any(
            k in blob
            for k in (
                "fee", "rule", "regulation", "policy", "scheme", "admission", "prospectus",
                "hostel", "scholarship", "calendar", "semester", "academic",
            )
        )

    async def _robots_ok(self, client: httpx.AsyncClient, url: str) -> bool:
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = RobotFileParser()
            try:
                r = await client.get(f"{origin}/robots.txt", timeout=15)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                    self._robots[origin] = rp
                else:
                    self._robots[origin] = None  # no robots file => allowed
            except httpx.HTTPError:
                self._robots[origin] = None
        rp = self._robots[origin]
        return True if rp is None else rp.can_fetch(self.s.crawl_user_agent, url)

    async def _pace(self) -> None:
        async with self._pace_lock:
            loop = asyncio.get_running_loop()
            wait = self._last_request + self.s.crawl_delay_seconds - loop.time()
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = loop.time()

    # ------------------------------------------------------------------ fetching
    async def fetch(
        self,
        client: httpx.AsyncClient,
        url: str,
        discovered_from: str | None,
        force: bool = False,
    ) -> tuple[PageRecord, bytes | None, bool]:
        """Fetch ``url`` → (record, body if (re)downloaded, changed)."""
        prev = self.store.get(url)
        headers: dict[str, str] = {}
        if prev and prev.ok and not force:
            if prev.etag:
                headers["If-None-Match"] = prev.etag
            if prev.last_modified:
                headers["If-Modified-Since"] = prev.last_modified

        last_error = "unknown error"
        for attempt in range(self.s.crawl_retries):
            try:
                async with self._sem:
                    await self._pace()
                    resp = await client.get(url, headers=headers, follow_redirects=True)
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"[:300]
            else:
                if resp.status_code == 304 and prev:
                    prev.fetched_at = utcnow()
                    self.store.upsert(prev)
                    return prev, None, False
                if resp.status_code in (429, 500, 502, 503, 504):
                    last_error = f"HTTP {resp.status_code}"
                    retry_after = resp.headers.get("Retry-After", "")
                    if retry_after.isdigit():
                        await asyncio.sleep(min(int(retry_after), 30))
                else:
                    return self._record(url, resp, prev, discovered_from)
            backoff = min(2**attempt, 20) + random.random()
            log.warning("retry %s in %.1fs (%s)", url, backoff, last_error)
            await asyncio.sleep(backoff)

        # Exhausted: keep any earlier good snapshot, record the failure.
        rec = prev or PageRecord(url, None, None, None, None, None, None, None, None,
                                 utcnow(), None, last_error, discovered_from)
        if prev and prev.ok:
            prev.error = last_error  # stale-but-usable
            self.store.upsert(prev)
            return prev, None, False
        rec.error = last_error
        rec.fetched_at = utcnow()
        self.store.upsert(rec)
        return rec, None, False

    def _record(self, url, resp: httpx.Response, prev, discovered_from):
        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        ext = self._extension(url, ctype)
        body = resp.content
        sha = self.store.put_bytes(body, ext) if resp.status_code == 200 and body else None
        changed = bool(sha and (not prev or prev.sha256 != sha))
        rec = PageRecord(
            url=url,
            final_url=normalize_url(str(resp.url)),
            status=resp.status_code,
            content_type=ctype,
            sha256=sha,
            ext=ext,
            bytes=len(body),
            etag=resp.headers.get("etag"),
            last_modified=resp.headers.get("last-modified"),
            fetched_at=utcnow(),
            changed_at=utcnow() if changed else (prev.changed_at if prev else None),
            error=None if resp.status_code == 200 else f"HTTP {resp.status_code}",
            discovered_from=discovered_from,
        )
        self.store.upsert(rec)
        return rec, (body if sha else None), changed

    @staticmethod
    def _extension(url: str, ctype: str) -> str:
        path = urlsplit(url).path.lower()
        for ext in DOCUMENT_EXT:
            if path.endswith(ext):
                return ext
        if "pdf" in ctype:
            return ".pdf"
        if "html" in ctype or "xml" in ctype:
            return ".html"
        return ".bin"

    # ------------------------------------------------------------------ link discovery
    @staticmethod
    def extract_links(html: str, base_url: str) -> set[str]:
        soup = BeautifulSoup(html, "html.parser")
        base = soup.find("base", href=True)
        if base:
            base_url = urljoin(base_url, base["href"])
        found: set[str] = set()
        for tag in soup.find_all(["a", "iframe", "embed", "object", "link", "source"]):
            for attr in ("href", "src", "data", "data-href", "data-url", "data-file"):
                val = tag.get(attr)
                if val and not val.startswith(("mailto:", "tel:", "javascript:", "#", "data:")):
                    found.add(normalize_url(urljoin(base_url, val)))
        # Documents referenced from inline scripts / buttons.
        for m in re.finditer(r"""["']([^"'\s<>]+\.(?:pdf|docx?|xlsx?|pptx?))["']""", html, re.I):
            found.add(normalize_url(urljoin(base_url, m.group(1))))
        return found

    async def sitemap_urls(self, client: httpx.AsyncClient) -> list[str]:
        for attempt in range(3):
            try:
                r = await client.get(f"{self.s.site_url.rstrip('/')}/sitemap.xml", timeout=30)
                if r.status_code == 200:
                    return [
                        normalize_url(u) for u in re.findall(r"<loc>\s*(.*?)\s*</loc>", r.text)
                    ]
            except httpx.HTTPError:
                await asyncio.sleep(2**attempt)
        return []

    # ------------------------------------------------------------------ main loop
    async def run(self, *, force: bool = False, extra_seeds: list[str] | None = None) -> CrawlReport:
        report = CrawlReport()
        limits = httpx.Limits(max_connections=self.s.crawl_concurrency + 2)
        headers = {"User-Agent": self.s.crawl_user_agent, "Accept-Language": "en"}
        async with httpx.AsyncClient(
            headers=headers, limits=limits, timeout=self.s.crawl_timeout_seconds
        ) as client:
            seeds = [normalize_url(self.s.site_url)]
            seeds += await self.sitemap_urls(client)
            seeds += [normalize_url(u) for u in (extra_seeds or [])]
            queue: deque[tuple[str, str | None]] = deque((u, None) for u in dict.fromkeys(seeds))
            seen: set[str] = set()
            in_flight: set[asyncio.Task] = set()

            async def work(url: str, parent: str | None) -> None:
                try:
                    if not await self._robots_ok(client, url):
                        report.skipped += 1
                        return
                    rec, body, changed = await self.fetch(client, url, parent, force)
                    if not rec.ok:
                        report.failed.append((url, rec.error or f"HTTP {rec.status}"))
                        return
                    report.fetched += 1 if changed or body is not None else 0
                    report.unchanged += 0 if changed or body is not None else 1
                    if rec.content_type == "text/html":
                        data = body if body is not None else self.store.read_bytes(rec)
                        html = data.decode("utf-8", "replace")
                        host = urlsplit(url).hostname or ""
                        for link in self.extract_links(html, rec.final_url or url):
                            lhost = (urlsplit(link).hostname or "").lower()
                            if lhost != self.host and link.startswith("http"):
                                report.external_links.add(link)
                            if (
                                link not in seen
                                and self.wants(link, from_host=host.lower())
                                and len(seen) < self.s.crawl_max_pages
                            ):
                                seen.add(link)
                                queue.append((link, url))
                except Exception as exc:  # never let one URL kill the run
                    log.exception("crawl error %s", url)
                    report.failed.append((url, f"{type(exc).__name__}: {exc}"))

            for url, _ in list(queue):
                seen.add(url)
            while queue or in_flight:
                while queue and len(in_flight) < self.s.crawl_concurrency * 2:
                    url, parent = queue.popleft()
                    task = asyncio.create_task(work(url, parent))
                    in_flight.add(task)
                    task.add_done_callback(in_flight.discard)
                if in_flight:
                    await asyncio.wait(set(in_flight), return_when=asyncio.FIRST_COMPLETED)
        log.info("crawl finished: %s", report.summary())
        return report

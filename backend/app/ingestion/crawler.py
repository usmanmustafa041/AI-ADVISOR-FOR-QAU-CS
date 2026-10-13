"""Bounded public HTML/PDF crawler. No credentials or browser automation.

Every redirect is checked before sending it. Robots failures block that origin;
404/410 mean no robots policy. Protego supplies wildcard and rule precedence.
"""

import hashlib
import re
import time
from collections import deque
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urljoin, urlsplit, urlunsplit
from uuid import uuid4
from xml.etree import ElementTree

import httpx
from protego import Protego

from app.ingestion.archive import SourceArchive, atomic_write
from app.ingestion.parsing import PARSER_VERSION, parse_document

OFFICIAL_HOSTS = frozenset({"cs.qau.edu.pk", "www.cs.qau.edu.pk", "qau.edu.pk", "www.qau.edu.pk"})
USER_AGENT = "QAU-CSBot/1.0 (public academic document archive)"
IGNORED_SUFFIXES = {
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".svg",
    ".webp",
    ".ico",
    ".css",
    ".js",
    ".zip",
    ".gz",
    ".rar",
    ".mp4",
    ".mp3",
    ".woff",
    ".woff2",
    ".ttf",
    ".exe",
}


def public_url(value: str, allowed_hosts=OFFICIAL_HOSTS) -> str | None:
    try:
        parts = urlsplit(value.strip())
        if parts.scheme not in {"http", "https"} or parts.hostname not in allowed_hosts:
            return None
        if parts.username or parts.password or parts.port not in {None, 80, 443}:
            return None
        if any(ord(c) < 32 for c in value) or "\\" in value:
            return None
        if Path(parts.path).suffix.lower() in IGNORED_SUFFIXES:
            return None
        if any(
            k.lower() in {"logout", "delete", "action", "token", "password"}
            for k, _ in parse_qsl(parts.query)
        ):
            return None
        # Upgrade discovered HTTP links; preserve case, query and trailing slash.
        return urlunsplit(("https", parts.hostname, parts.path or "/", parts.query, ""))
    except ValueError:
        return None


@dataclass(frozen=True)
class CrawlConfig:
    max_pages: int = 300
    max_depth: int = 10
    delay_seconds: float = 1.0
    timeout_seconds: float = 20.0
    max_bytes: int = 20 * 1024 * 1024
    max_seconds: float = 900.0
    max_query_variants: int = 20
    ocr: bool = False
    discover_sitemaps: bool = False
    resume_pending: bool = False
    allowed_hosts: tuple[str, ...] = tuple(sorted(OFFICIAL_HOSTS))

    def __post_init__(self):
        if self.max_pages < 1 or self.max_depth < 0 or self.max_bytes < 1024:
            raise ValueError("Invalid page, depth or download limit")
        if self.delay_seconds < 0.2 or self.timeout_seconds <= 0 or self.max_seconds <= 0:
            raise ValueError("Delay must be >=0.2s; timeout and run budget must be positive")
        if self.max_query_variants < 1:
            raise ValueError("Query variant limit must be positive")
        if any(not (h == "qau.edu.pk" or h.endswith(".qau.edu.pk")) for h in self.allowed_hosts):
            raise ValueError("Additional hosts must be official QAU subdomains")


class PublicCrawler:
    def __init__(
        self,
        archive: SourceArchive,
        config: CrawlConfig | None = None,
        *,
        client=None,
        clock=time.monotonic,
        sleep=time.sleep,
    ):
        self.archive, self.config = archive, config or CrawlConfig()
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT},
            follow_redirects=False,
            timeout=self.config.timeout_seconds,
        )
        self.owns_client = client is None
        self.clock, self.sleep = clock, sleep
        self.policies, self.next_request, self.origin_delays = {}, {}, {}
        self.run_id = uuid4().hex
        self.deadline = self.clock() + self.config.max_seconds
        self.requests = 0
        self.sitemap_origins = set()

    def _url(self, value):
        return public_url(value, self.config.allowed_hosts)

    def _sitemaps(self, url):
        """Bound sitemap indexes as well as documents; use the same robots/rate checks."""
        origin = f"https://{urlsplit(url).netloc}"
        if origin in self.sitemap_origins or not self.config.discover_sitemaps:
            return []
        self.sitemap_origins.add(origin)
        policy = self._policy(url)
        candidates = deque(list(policy.sitemaps)[:10] + [origin + "/sitemap.xml"])
        seen, found = set(), []
        while candidates and len(seen) < 20 and self.clock() < self.deadline:
            sitemap = self._url(candidates.popleft())
            if not sitemap or sitemap in seen:
                continue
            seen.add(sitemap)
            try:
                status, _, raw, _ = self._fetch(sitemap)
                if status != 200:
                    raise ValueError(f"Sitemap HTTP {status}")
                if b"<!DOCTYPE" in raw.upper() or b"<!ENTITY" in raw.upper():
                    raise ValueError("Sitemap entity declarations are unsupported")
                tree = ElementTree.fromstring(raw)
                kind = tree.tag.rsplit("}", 1)[-1]
                if kind not in {"sitemapindex", "urlset"}:
                    raise ValueError("Not a sitemap XML document")
                locations = [
                    n.text.strip()
                    for n in tree.iter()
                    if n.tag.rsplit("}", 1)[-1] == "loc" and n.text
                ][:10000]
                if kind == "sitemapindex":
                    candidates.extend(locations[:20])
                else:
                    found.extend(locations)
                self.archive.observe(
                    self.run_id,
                    sitemap,
                    "sitemap_processed",
                    detail={"locations": len(locations), "kind": kind},
                )
            except Exception as exc:
                self.archive.observe(
                    self.run_id, sitemap, "sitemap_failed", detail={"error": str(exc)[:300]}
                )
        return found[: self.config.max_pages * 20]

    def _wait(self, origin: str):
        wait = max(0, self.next_request.get(origin, 0) - self.clock())
        if self.clock() + wait >= self.deadline:
            raise TimeoutError("Crawl time budget exhausted")
        if wait:
            self.sleep(wait)
        if self.clock() >= self.deadline:
            raise TimeoutError("Crawl time budget exhausted")
        self.next_request[origin] = self.clock() + self.origin_delays.get(
            origin, self.config.delay_seconds
        )

    def _fetch(self, url: str, *, headers=None, robots=False) -> tuple[int, dict, bytes, str]:
        for _ in range(6):
            normalized = self._url(url)
            if normalized is None:
                raise ValueError("Redirect outside approved public origins")
            url = normalized
            origin = f"https://{urlsplit(url).netloc}"
            if not robots and not self._policy(url).can_fetch(url, USER_AGENT):
                raise PermissionError("robots.txt disallows URL")
            self._wait(origin)
            self.requests += 1
            with self.client.stream(
                "GET",
                url,
                headers={"User-Agent": USER_AGENT, **(headers or {})},
                follow_redirects=False,
                timeout=self.config.timeout_seconds,
            ) as response:
                status = response.status_code
                if status in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirect without Location")
                    target = self._url(urljoin(url, location))
                    if target is None:
                        raise ValueError("Redirect outside approved public origins")
                    url, headers = target, None
                    continue
                limit = min(self.config.max_bytes, 512 * 1024) if robots else self.config.max_bytes
                size_header = response.headers.get("content-length", "")
                if size_header.isdigit() and int(size_header) > limit:
                    raise ValueError("Resource exceeds download limit")
                data = bytearray()
                for block in response.iter_bytes():
                    data.extend(block)
                    if len(data) > limit:
                        raise ValueError("Resource exceeds download limit")
                    if self.clock() >= self.deadline:
                        raise TimeoutError("Crawl time budget exhausted")
                if status in {429, 503}:
                    retry_after = response.headers.get("retry-after", "")
                    try:
                        seconds = float(retry_after)
                    except ValueError:
                        try:
                            seconds = parsedate_to_datetime(retry_after).timestamp() - time.time()
                        except (TypeError, ValueError, OverflowError):
                            seconds = 30.0
                    self.next_request[origin] = max(
                        self.next_request[origin], self.clock() + max(1, seconds)
                    )
                return status, dict(response.headers), bytes(data), url
        raise ValueError("Too many redirects")

    def _policy(self, url: str):
        origin = f"https://{urlsplit(url).netloc}"
        if origin in self.policies:
            return self.policies[origin]
        robots_url = origin + "/robots.txt"
        try:
            status, _, raw, _ = self._fetch(robots_url, robots=True)
            if status in {404, 410}:
                body = "User-agent: *\nDisallow:\n"
            elif status == 200:
                body = raw.decode("utf-8", errors="replace")
                # HTML error pages served as 200 do not establish permission.
                if "<html" in body.lower() or "<!doctype" in body.lower():
                    raise ValueError("robots.txt returned HTML")
            else:
                raise ValueError(f"robots.txt HTTP {status}")
            policy = Protego.parse(body)
            delay = policy.crawl_delay(USER_AGENT) or 0
            rate = policy.request_rate(USER_AGENT)
            self.origin_delays[origin] = max(
                self.config.delay_seconds,
                delay,
                rate.seconds / rate.requests if rate and rate.requests else 0,
            )
            # Apply the newly discovered delay after the robots request too.
            self.next_request[origin] = max(
                self.next_request.get(origin, 0), self.clock() + self.origin_delays[origin]
            )
            digest = hashlib.sha256(raw).hexdigest()
            atomic_write(self.archive.root / "robots" / f"{digest}.txt", raw)
            self.archive.observe(
                self.run_id,
                robots_url,
                "robots_policy",
                detail={
                    "http_status": status,
                    "sha256": digest,
                    "delay_seconds": self.origin_delays[origin],
                },
            )
        except (httpx.HTTPError, ValueError, TimeoutError) as exc:
            policy = Protego.parse("User-agent: *\nDisallow: /\n")
            self.archive.observe(
                self.run_id, robots_url, "robots_unavailable", detail={"error": str(exc)}
            )
        self.policies[origin] = policy
        return policy

    def crawl(self, seeds: list[str]) -> dict:
        queue, scheduled, visited, variants = deque(), set(), set(), {}
        discarded = 0
        seed_urls = {self._url(value) for value in seeds}

        def schedule(value, depth):
            nonlocal discarded
            url = self._url(value)
            if url is None or url in scheduled or depth > self.config.max_depth:
                return
            parts = urlsplit(url)
            key = (parts.netloc, parts.path)
            if parts.query and variants.get(key, 0) >= self.config.max_query_variants:
                discarded += 1
                return
            if len(scheduled) >= self.config.max_pages * 20:
                discarded += 1
                return
            variants[key] = variants.get(key, 0) + bool(parts.query)
            scheduled.add(url)
            queue.append((url, depth))

        for seed in seeds:
            if self._url(seed) is None:
                raise ValueError(f"Invalid seed URL: {seed}")
            schedule(seed, 0)
        resumed = 0
        if self.config.resume_pending:
            import json

            attempted = {
                row[0]
                for row in self.archive.db.execute(
                    "SELECT DISTINCT url FROM observations WHERE status NOT IN "
                    "('robots_policy','sitemap_processed')"
                )
            }
            for path in sorted(
                (self.archive.root / "runs").glob("*.json"), key=lambda p: p.stat().st_mtime
            ):
                try:
                    resources = json.loads(path.read_text()).get("resources", [])
                except (OSError, ValueError):
                    continue
                for resource in resources:
                    if resource.get("status") == "pending" and resource["url"] not in attempted:
                        before = len(scheduled)
                        schedule(resource["url"], resource.get("depth", 1))
                        resumed += len(scheduled) - before
        try:
            while queue and len(visited) < self.config.max_pages and self.clock() < self.deadline:

                def priority(item):
                    address, level = item
                    path = urlsplit(address).path.lower()
                    important = bool(
                        re.search(
                            r"rules|regulation|polic|fee|scholarship|hostel|transport|examin|"
                            r"semester|registration|calendar|timetable|scheme|catalog|syllab|fyp",
                            path,
                        )
                    )
                    document = path.endswith((".pdf", ".docx"))
                    department = "cs.qau.edu.pk" in address and bool(
                        re.search(r"faculty|research|academic|admission|programme|contact", path)
                    )
                    # Keep roots fresh, then make progress on previously unvisited
                    # links before repeatedly crawling already archived pages.
                    progress = (
                        (0 if address in seed_urls else 1 if address not in attempted else 2)
                        if self.config.resume_pending
                        else 0
                    )
                    return (progress, -int(document), -int(important), -int(department), level)

                queue = deque(sorted(queue, key=priority))
                url, depth = queue.popleft()
                visited.add(url)
                for discovered in self._sitemaps(url):
                    schedule(discovered, 1)
                previous = self.archive.latest(url)
                headers = {}
                prior_extraction = self.archive.parsed(previous) if previous else None
                needs_reparse = prior_extraction and (
                    prior_extraction["parser_version"] != PARSER_VERSION
                    or (self.config.ocr and bool(prior_extraction["warnings"]))
                )
                if previous and not needs_reparse:
                    if previous["etag"]:
                        headers["If-None-Match"] = previous["etag"]
                    if previous["last_modified"]:
                        headers["If-Modified-Since"] = previous["last_modified"]
                raw = b""
                try:
                    for attempt in range(2):
                        status, response_headers, raw, final_url = self._fetch(url, headers=headers)
                        if status not in {429, 503} or attempt == 1:
                            break
                    if status == 304:
                        version = self.archive.not_modified(self.run_id, url)
                        parsed = self.archive.parsed(version)
                    elif status == 200:
                        mime = response_headers.get("content-type", "").split(";", 1)[0].lower()
                        parsed = parse_document(raw, final_url, mime, ocr=self.config.ocr)
                        parsed["final_url"] = final_url
                        self.archive.save(self.run_id, url, raw, parsed, response_headers)
                    else:
                        self.archive.observe(
                            self.run_id, url, "http_error", detail={"http_status": status}
                        )
                        continue
                    for link in parsed["links"][:5000]:
                        schedule(link, depth + 1)
                except PermissionError as exc:
                    self.archive.observe(
                        self.run_id, url, "robots_denied", detail={"error": str(exc)}
                    )
                except Exception as exc:
                    # Bad PDFs/OCR must not terminate a run or discard its originals.
                    detail = {"error_type": type(exc).__name__, "error": str(exc)[:500]}
                    if raw:
                        digest = hashlib.sha256(raw).hexdigest()
                        relative = f"quarantine/{digest}.raw"
                        atomic_write(self.archive.root / relative, raw)
                        detail["raw_path"] = relative
                    self.archive.observe(self.run_id, url, "error", detail=detail)
            report = {
                **self.archive.run_summary(self.run_id),
                "requests": self.requests,
                "visited": len(visited),
                "pending": len(queue),
                "discarded": discarded,
                "bounded": bool(queue) or bool(discarded),
                "discovered": len(scheduled),
                "resources": [{"url": u, "status": "pending", "depth": d} for u, d in queue],
                "allowed_hosts": list(self.config.allowed_hosts),
                "resumed_pending": resumed,
                "note": (
                    "Link-discovered bounded crawl; inaccessible and unlinked resources "
                    "are not coverage claims."
                ),
            }
            statuses = {
                o["url"]: o["status"] for o in report["observations"] if o["url"] in visited
            }
            report["resources"] += [
                {"url": u, "status": statuses.get(u, "failed")} for u in sorted(visited)
            ]
            report["structured_records"] = self.archive.export_records(
                self.archive.root / "structured_records.jsonl"
            )
            import json

            atomic_write(
                self.archive.root / "runs" / f"{self.run_id}.json",
                json.dumps(report, ensure_ascii=False, indent=2).encode(),
            )
            return report
        finally:
            if self.owns_client:
                self.client.close()

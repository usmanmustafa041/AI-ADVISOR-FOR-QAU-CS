"""Bounded official public acquisition into staging; never publishes an index."""

import argparse
import asyncio
import hashlib
import ipaddress
import json
import re
import socket
import time
from collections import Counter, deque
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urldefrag, urljoin, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup
from protego import Protego

from chatbot_v3.ingest import import_one, now
from chatbot_v3.resources import public_resource_url, source_links
from chatbot_v3.settings import settings
from chatbot_v3.store import Store

HOSTS = {"qau.edu.pk", "www.qau.edu.pk", "cs.qau.edu.pk"}
AGENT = "QAU-CS-Assistant-Preview/3.0"


def safe_url(url):
    u = urlsplit(urldefrag(url)[0])
    if (
        u.scheme not in {"http", "https"}
        or u.hostname not in HOSTS
        or u.username
        or u.password
        or u.port not in {None, 80, 443}
    ):
        raise ValueError("URL outside the explicit public university allowlist")
    if any(
        x in u.path.lower()
        for x in ["login", "logout", "signin", "wp-admin", "cdn-cgi", "lostpassword"]
    ):
        raise ValueError("Authentication/action path excluded")
    if u.query and public_resource_url(url) is None:
        raise ValueError("Query/action URLs excluded in this bounded preview crawl")
    query = urlsplit(public_resource_url(url)).query if u.query else ""
    return urlunsplit(("https", u.hostname, u.path or "/", query, ""))


def public_dns(host):
    addresses = {row[4][0] for row in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
    if not addresses or any(not ipaddress.ip_address(a).is_global for a in addresses):
        raise ValueError("University host resolves to a nonpublic address")


def retry_delay(value):
    try:
        return min(60, max(1, float(value)))
    except (ValueError, TypeError):
        try:
            return min(
                60, max(1, (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds())
            )
        except (ValueError, TypeError):
            return 5


class Crawler:
    def __init__(self, store, max_pages=100, max_seconds=300):
        self.store, self.max_pages, self.max_seconds = store, max_pages, max_seconds
        self.robots, self.last_fetch = {}, {}
        self.report = []
        self.root = settings().data_dir / "acquisition"
        self.root.mkdir(parents=True, exist_ok=True)
        self.state_path = self.root / "validators.json"
        self.state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.frontier_path = self.root / "frontier.json"

    async def fetch(self, client, url, headers=None):
        url = safe_url(url)
        for _ in range(5):
            u = urlsplit(url)
            await asyncio.to_thread(public_dns, u.hostname)
            delay = max(0, 1.0 - (time.monotonic() - self.last_fetch.get(u.hostname, 0)))
            await asyncio.sleep(delay)
            self.last_fetch[u.hostname] = time.monotonic()
            async with client.stream("GET", url, headers=headers or {}) as response:
                if response.is_redirect:
                    target = safe_url(urljoin(url, response.headers["location"]))
                    if not target.endswith("/robots.txt") and not await self.allowed(
                        client, target
                    ):
                        raise ValueError("Redirect blocked by robots")
                    url = target
                    continue
                data = bytearray()
                async for part in response.aiter_bytes():
                    data.extend(part)
                    if len(data) > 15_000_000:
                        raise ValueError("Download exceeds 15 MB bound")
                return response.status_code, dict(response.headers), bytes(data), url
        raise ValueError("Redirect limit")

    async def allowed(self, client, url):
        origin = "https://" + urlsplit(url).hostname
        if origin not in self.robots:
            try:
                status, headers, data, _ = await self.fetch(client, origin + "/robots.txt")
                if status in {404, 410}:
                    policy = Protego.parse("")
                elif status == 200:
                    policy = Protego.parse(data.decode("utf-8", "replace"))
                else:
                    self.robots[origin] = None
                    return False
                self.robots[origin] = policy
                (self.root / (urlsplit(url).hostname + "-robots.txt")).write_bytes(data)
            except Exception:
                self.robots[origin] = None
                return False
        policy = self.robots[origin]
        if policy is None:
            return False
        delay = policy.crawl_delay(AGENT) or 1
        if delay > 1:
            await asyncio.sleep(
                min(
                    60,
                    max(
                        0,
                        delay - (time.monotonic() - self.last_fetch.get(urlsplit(url).hostname, 0)),
                    ),
                )
            )
        return policy.can_fetch(url, AGENT)

    async def run(self, seeds, resume=False):
        pending = []
        if resume:
            if self.frontier_path.exists():
                pending = json.loads(self.frontier_path.read_text()).get("pending_urls", [])
            else:
                # Recover the previous bounded run's frontier from retained link/visit records.
                visited = set()
                for report_path in self.root.glob("crawl-*.json"):
                    visited.update(
                        r["url"] for r in json.loads(report_path.read_text()).get("results", [])
                    )
                pending = [
                    link
                    for value in self.state.values()
                    for link in value.get("links", [])
                    if link not in visited
                ]
        validated = []
        for url in [*seeds, *pending]:
            try:
                validated.append(safe_url(url))
            except ValueError:
                continue
        queue = deque(dict.fromkeys(validated))
        deferred = []
        seen = set()
        started = time.monotonic()
        async with httpx.AsyncClient(
            timeout=20, follow_redirects=False, trust_env=False, headers={"User-Agent": AGENT}
        ) as client:
            while (
                queue
                and len(seen) < self.max_pages
                and time.monotonic() - started < self.max_seconds
            ):
                url = queue.popleft()
                if url in seen:
                    continue
                seen.add(url)
                try:
                    if not await self.allowed(client, url):
                        self.report.append(
                            {
                                "url": url,
                                "status": "blocked",
                                "reason": "Robots unavailable or disallowed",
                            }
                        )
                        if self.robots.get("https://" + urlsplit(url).hostname) is None:
                            deferred.append(url)
                        continue
                    saved = self.state.get(url, {})
                    request_headers = {
                        k: v
                        for k, v in [
                            ("If-None-Match", saved.get("etag")),
                            ("If-Modified-Since", saved.get("last_modified")),
                        ]
                        if v
                    }
                    status, headers, data, final = await self.fetch(client, url, request_headers)
                    if status in {429, 503}:
                        deferred.append(url)
                        self.report.append(
                            {
                                "url": url,
                                "status": "deferred",
                                "http_status": status,
                                "retry_after": headers.get("retry-after"),
                            }
                        )
                        await asyncio.sleep(retry_delay(headers.get("retry-after")))
                        continue
                    if status == 304:
                        self.report.append({"url": url, "status": "unchanged"})
                        links = saved.get("links", [])
                    elif status != 200:
                        self.report.append(
                            {
                                "url": url,
                                "status": "missing" if status in {404, 410} else "failed",
                                "http_status": status,
                            }
                        )
                        continue
                    else:
                        mime = headers.get("content-type", "").split(";")[0]
                        if "xml" in mime or url.endswith(".xml"):
                            soup = BeautifulSoup(data, "xml")
                            links = [x.text for x in soup.find_all("loc")]
                            self.report.append(
                                {"url": url, "status": "sitemap", "links": len(links)}
                            )
                        elif (
                            "html" in mime
                            or "pdf" in mime
                            or "wordprocessingml" in mime
                            or data.startswith(b"%PDF-")
                        ):
                            suffix = (
                                ".pdf"
                                if "pdf" in mime or data.startswith(b"%PDF-")
                                else ".docx"
                                if "wordprocessingml" in mime
                                else ".html"
                            )
                            checksum = hashlib.sha256(data).hexdigest()
                            path = self.root / "objects" / checksum[:2] / (checksum + suffix)
                            path.parent.mkdir(parents=True, exist_ok=True)
                            if not path.exists():
                                with path.open("xb") as f:
                                    f.write(data)
                            links = []
                            if suffix == ".html":
                                soup = BeautifulSoup(data, "html.parser")
                                declared_base = soup.find("base", href=True)
                                base = (
                                    public_resource_url(declared_base["href"], final)
                                    if declared_base
                                    else None
                                ) or final
                                links = [
                                    urljoin(base, a["href"]) for a in soup.find_all("a", href=True)
                                ]
                                links.extend(r["url"] for r in source_links(soup, base))
                            result = await asyncio.to_thread(
                                import_one, self.store, path, final, now(), checksum, mime, True
                            )
                            self.report.append({"url": url, "status": "parsed", **result})
                        else:
                            self.report.append({"url": url, "status": "unsupported", "mime": mime})
                            continue
                        self.state[url] = {
                            "etag": headers.get("etag"),
                            "last_modified": headers.get("last-modified"),
                            "links": links,
                            "checked_at": now(),
                        }
                    for link in links:
                        try:
                            link = safe_url(link)
                            if (
                                link not in seen
                                and link not in queue
                                and not re.search(
                                    r"\.(jpg|png|gif|css|js|mp4|zip)$", urlsplit(link).path, re.I
                                )
                            ):
                                queue.append(link)
                        except ValueError:
                            pass
                    policy = self.robots.get("https://" + urlsplit(url).hostname)
                    if policy:
                        for sitemap in policy.sitemaps:
                            try:
                                sitemap = safe_url(sitemap)
                                if sitemap not in seen and sitemap not in queue:
                                    queue.append(sitemap)
                            except ValueError:
                                pass
                except Exception as e:
                    deferred.append(url)
                    self.report.append(
                        {
                            "url": url,
                            "status": "failed",
                            "reason": (str(e) or type(e).__name__)[:200],
                        }
                    )
        pending_urls = list(dict.fromkeys([*queue, *deferred]))
        report = {
            "checked_at": now(),
            "discovered": len(seen | set(queue)),
            "visited": len(seen),
            "pending": len(pending_urls),
            "pending_urls": pending_urls,
            "counts": dict(Counter(r["status"] for r in self.report)),
            "seconds": round(time.monotonic() - started, 2),
            "results": self.report,
            "publication": "staging only; no active index modified",
        }
        from chatbot_v3.index import atomic_json

        atomic_json(self.state_path, self.state)
        atomic_json(self.frontier_path, {"checked_at": now(), "pending_urls": pending_urls})
        atomic_json(self.root / ("crawl-" + str(int(time.time())) + ".json"), report)
        return report


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", action="append")
    p.add_argument("--max-pages", type=int, default=100)
    p.add_argument("--max-seconds", type=int, default=300)
    p.add_argument("--resume", action="store_true")
    a = p.parse_args()
    r = asyncio.run(
        Crawler(Store(), a.max_pages, a.max_seconds).run(
            a.seed
            or [
                "https://cs.qau.edu.pk/",
                "https://cs.qau.edu.pk/sitemap.xml",
                "https://qau.edu.pk/sitemap.xml",
                "https://qau.edu.pk/sitemap_index.xml",
                "https://cs.qau.edu.pk/admissions",
                "https://cs.qau.edu.pk/bs.php",
                "https://cs.qau.edu.pk/faculty",
                "https://qau.edu.pk/fee-structure/",
                "https://cs.qau.edu.pk/students",
                "https://cs.qau.edu.pk/events",
                "https://qau.edu.pk/downloads/",
                "https://qau.edu.pk/download-category/examinations/",
            ],
            resume=a.resume,
        )
    )
    print(json.dumps({k: v for k, v in r.items() if k != "results"}))


if __name__ == "__main__":
    main()

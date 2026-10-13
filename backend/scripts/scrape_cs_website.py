"""Compatibility exports backed by the robots-aware, versioned QAU crawler.

New jobs should call crawl_sources.py and refresh_knowledge.py. Legacy JSON
exports contain the latest successful observation from this run; originals and
all historical versions remain in the immutable archive.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import SourceArchive, atomic_write
from app.ingestion.crawler import CrawlConfig, PublicCrawler, public_url
from app.rag.corpus import PROJECT_ROOT


class CSWebsiteScraper:
    def __init__(self, base_url="https://cs.qau.edu.pk", *, archive=None, config=None):
        self.base_url = public_url(base_url)
        if self.base_url is None:
            raise ValueError("Expected an official public QAU URL")
        self.archive = Path(archive) if archive else PROJECT_ROOT / "academic-data/crawl-archive"
        self.config = config or CrawlConfig()
        self.visited_urls = set()
        self.scraped_data = []
        self.report = {}
        self._links = {}

    def is_valid_url(self, url):
        return public_url(url) is not None

    def _crawl(self, seeds, config):
        archive = SourceArchive(self.archive)
        try:
            self.report = PublicCrawler(archive, config).crawl(seeds)
            successful = dict.fromkeys(
                row["url"]
                for row in self.report["observations"]
                if row["status"] in {"new", "changed", "unchanged", "not_modified"}
            )
            by_url = {page["url"]: page for page in self.scraped_data}
            for url in successful:
                version = archive.latest(url)
                parsed = archive.parsed(version)
                content = "\n\n".join(p["content"] for p in parsed["pages"])
                by_url[url] = {
                    "url": url,
                    "title": parsed["title"],
                    "content": content,
                    "pages": parsed["pages"],
                    "timestamp": version["last_seen_at"],
                    "local_path": str(archive.root / version["raw_path"]),
                    "content_hash": version["text_sha256"],
                    "word_count": len(content.split()),
                    "mime_type": parsed["mime_type"],
                    "source_version_id": version["version_id"],
                    "source_sha256": version["raw_sha256"],
                    "metadata": parsed["metadata"],
                    "warnings": parsed["warnings"],
                }
                self._links[url] = {
                    normalized for link in parsed["links"] if (normalized := public_url(link))
                }
            self.visited_urls.update(row["url"] for row in self.report["observations"])
            self.scraped_data = list(by_url.values())
            return self.scraped_data
        finally:
            archive.close()

    def scrape_page(self, url):
        from dataclasses import replace

        self._crawl([url], replace(self.config, max_pages=1))
        return self._links.get(url, set()) - self.visited_urls

    def scrape_all(self, start_url=None):
        return self._crawl([start_url or self.base_url], self.config)

    def save_to_json(self, output_file):
        atomic_write(
            Path(output_file), json.dumps(self.scraped_data, ensure_ascii=False, indent=2).encode()
        )

    def save_for_rag(self, output_dir):
        output = Path(output_dir)
        pages = []
        for index, page in enumerate(self.scraped_data):
            filename = f"page_{index:03d}_{page['content_hash'][:8]}.json"
            atomic_write(output / filename, json.dumps(page, ensure_ascii=False, indent=2).encode())
            pages.append(
                {
                    "id": index,
                    "url": page["url"],
                    "title": page["title"],
                    "word_count": page["word_count"],
                    "filename": filename,
                }
            )
        atomic_write(
            output / "index.json",
            json.dumps({"total_pages": len(pages), "pages": pages}, indent=2).encode(),
        )


if __name__ == "__main__":
    from crawl_sources import main

    raise SystemExit(main())

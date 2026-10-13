"""Network-free crawl policy, provenance and source-version regressions."""

import json
import os

import httpx
import pytest

from app.ingestion.archive import SourceArchive
from app.ingestion.crawler import CrawlConfig, PublicCrawler, public_url
from app.ingestion.parsing import PARSER_VERSION, credit_hours, document_metadata, parse_document
from app.rag.corpus import build_corpus

ORIGIN = "https://cs.qau.edu.pk"


class FakeTime:
    def __init__(self):
        self.now = 0.0

    def clock(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds


@pytest.fixture
def archive(tmp_path):
    store = SourceArchive(tmp_path / "archive")
    yield store
    store.close()


def run_crawl(archive, handler, seeds=None, **options):
    clock = FakeTime()
    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        crawler = PublicCrawler(
            archive, CrawlConfig(**options), client=client, clock=clock.clock, sleep=clock.sleep
        )
        return crawler.crawl(seeds or [ORIGIN + "/"]), clock


def html(body, title="BSCS Scheme Fall 2025"):
    return f"<html><title>{title}</title><main>{body}</main></html>".encode()


def table(credits="3", prerequisite="CSC-100 OR CSC-101"):
    return (
        "<table><tr><th>Course Code</th><th>Course Name</th><th>Credit Hours</th>"
        "<th>Prerequisites</th></tr><tr><td>csc 104</td><td>Programming</td>"
        f"<td>{credits}</td><td>{prerequisite}</td></tr></table>"
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://cs.qau.edu.pk.attacker.com/",
        "https://localhost/",
        "file:///etc/passwd",
        "https://user:secret@cs.qau.edu.pk/",
        "https://cs.qau.edu.pk:8080/",
        "https://cs.qau.edu.pk/?action=delete",
        "https://cs.qau.edu.pk/a\\b",
    ],
)
def test_only_exact_public_origins_are_accepted(url):
    assert public_url(url) is None


def test_normalization_preserves_case_and_meaningful_queries():
    assert public_url("http://cs.qau.edu.pk/Profile.php?id=8#bio") == ORIGIN + "/Profile.php?id=8"


def test_explicit_schedule_header_dates_opaque_pdf_metadata_without_guessing_body_dates():
    metadata = document_metadata(
        "TT_v7 fall 26.docx",
        ORIGIN + "/uploads/opaque.pdf",
        "TIME TABLE BS / MS / PhD (CS) Fall 2026\n"
        "w.e.f Monday 28th September 2026\nCSC-104 Monday 8:30-10:00",
    )
    assert metadata["category"] == "timetable"
    assert metadata["is_time_sensitive"] and metadata["effective_term"] == "Fall 2026"
    unknown = document_metadata(
        "Notes", ORIGIN + "/notes.pdf", "Meeting notes\nWe discussed the timetable for Fall 2026."
    )
    assert unknown["effective_term"] is None and unknown["category"] == "general"


def test_resuming_bounded_runs_progresses_without_resetting_depth_or_origin_checks(archive):
    requested = []

    def handler(request):
        requested.append(request.url.path)
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nAllow: /")
        return httpx.Response(
            200,
            content=html('<p>Public page</p><a href="/pending">Next</a>'),
            headers={"Content-Type": "text/html"},
        )

    first, _ = run_crawl(archive, handler, max_pages=1)
    assert first["pending"] == 1
    requested.clear()
    second, _ = run_crawl(archive, handler, max_pages=2, resume_pending=True)
    assert second["resumed_pending"] == 1 and "/pending" in requested
    third, _ = run_crawl(archive, handler, max_pages=1, resume_pending=True)
    assert third["resumed_pending"] == 0
    (archive.root / "runs/depth.json").write_text(
        json.dumps(
            {
                "resources": [
                    {"url": ORIGIN + "/too-deep", "status": "pending", "depth": 2},
                    {"url": "https://attacker.invalid/", "status": "pending", "depth": 0},
                ]
            }
        )
    )
    last, _ = run_crawl(archive, handler, max_pages=2, max_depth=1, resume_pending=True)
    assert last["resumed_pending"] == 0 and "/too-deep" not in requested


def test_robots_wildcards_precedence_and_delay_are_enforced(archive):
    requests = []

    def handler(request):
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(
                200,
                text="User-agent: *\nDisallow: /private/*\nAllow: /private/public$\nCrawl-delay: 3",
            )
        return httpx.Response(
            200,
            content=html(
                '<p>Public academic information.</p><a href="/private/secret">Secret</a>'
                '<a href="/private/public">Public</a>'
            ),
            headers={"Content-Type": "text/html"},
        )

    report, clock = run_crawl(archive, handler)
    assert ORIGIN + "/private/secret" not in requests
    assert ORIGIN + "/private/public" in requests
    assert report["counts"]["robots_denied"] == 1
    assert clock.now >= 6


@pytest.mark.parametrize("status", [401, 403, 429, 500, 503])
def test_robots_failures_block_document_requests(archive, status):
    requests = []

    def handler(request):
        requests.append(str(request.url))
        return httpx.Response(status)

    report, _ = run_crawl(archive, handler)
    assert requests == [ORIGIN + "/robots.txt"]
    assert report["counts"]["robots_unavailable"] == 1
    assert not archive.versions()


def test_redirect_targets_are_checked_before_requesting(archive):
    requests = []

    def handler(request):
        requests.append(str(request.url))
        if request.url.path == "/robots.txt":
            return httpx.Response(200, text="User-agent: *\nDisallow: /blocked")
        if request.url.path == "/outside":
            return httpx.Response(302, headers={"Location": "https://attacker.example/collect"})
        return httpx.Response(302, headers={"Location": "/blocked"})

    report, _ = run_crawl(archive, handler, [ORIGIN + "/outside", ORIGIN + "/redirect"])
    assert not any("attacker" in url or url.endswith("/blocked") for url in requests)
    assert report["counts"]["error"] == 1
    assert report["counts"]["robots_denied"] == 1


def test_unchanged_responses_reuse_versions_and_continue_link_discovery(archive):
    conditional = []

    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.headers.get("If-None-Match"):
            conditional.append(str(request.url))
            return httpx.Response(304)
        return httpx.Response(
            200,
            content=html('<p>Public course information.</p><a href="/course">Course</a>'),
            headers={"Content-Type": "text/html", "ETag": '"v1"'},
        )

    run_crawl(archive, handler)
    report, _ = run_crawl(archive, handler)
    assert len(archive.versions()) == 2
    assert len(conditional) == 2
    assert report["counts"]["not_modified"] == 2


def test_rate_limit_respects_retry_after(archive):
    attempts = 0

    def handler(request):
        nonlocal attempts
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        attempts += 1
        if attempts == 1:
            return httpx.Response(429, headers={"Retry-After": "10"})
        return httpx.Response(
            200,
            content=html("<p>Published information.</p>"),
            headers={"Content-Type": "text/html"},
        )

    report, clock = run_crawl(archive, handler)
    assert report["counts"]["new"] == 1
    assert attempts == 2 and clock.now >= 11


def test_download_and_query_limits_bound_a_run(archive):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/large":
            return httpx.Response(200, content=b"a" * 2048, headers={"Content-Type": "text/html"})
        links = "".join(f'<a href="/?page={n}">Page {n}</a>' for n in range(100))
        return httpx.Response(
            200,
            content=html(links + '<a href="/large">Large</a>'),
            headers={"Content-Type": "text/html"},
        )

    report, _ = run_crawl(
        archive, handler, [ORIGIN + "/large", ORIGIN + "/"], max_bytes=1024, max_pages=2
    )
    assert report["visited"] == 2
    assert report["counts"]["error"] == 2


def test_corrupt_pdf_is_quarantined_without_terminating_crawl(archive):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        if request.url.path == "/broken.pdf":
            return httpx.Response(200, content=b"%PDF-1.7\nnot really a PDF")
        return httpx.Response(
            200,
            content=html("<p>A valid university document.</p>"),
            headers={"Content-Type": "text/html"},
        )

    report, _ = run_crawl(archive, handler, [ORIGIN + "/broken.pdf", ORIGIN + "/"])
    assert report["counts"]["error"] == 1 and report["counts"]["new"] == 1
    assert list((archive.root / "quarantine").glob("*.raw"))


def test_course_fields_are_explicit_and_prerequisite_logic_is_preserved():
    document = parse_document(html(table("4(3+1)")), ORIGIN + "/scheme.html", "text/html")
    course = next(r for r in document["records"] if r["record_type"] == "course")
    assert course["course_code"] == "CSC-104"
    assert course["credit_hours"] == 4 and course["lab_hours"] == 1
    assert course["prerequisites_raw"] == "CSC-100 OR CSC-101"
    assert course["semester"] is None
    assert course["source"]["line_start"] > 0
    missing = parse_document(
        html(
            table().replace("<th>Prerequisites</th>", "").replace("<td>CSC-100 OR CSC-101</td>", "")
        ),
        ORIGIN,
        "text/html",
    )
    assert (
        next(r for r in missing["records"] if r["record_type"] == "course")["prerequisites"] is None
    )


@pytest.mark.parametrize("value", ["3 or 4", "4(2+1)", "2025", "3.5"])
def test_ambiguous_credits_are_not_guessed(value):
    assert credit_hours(value) == (None, None, None)


def test_body_dates_do_not_become_effective_terms():
    document = parse_document(
        html("<p>Fall 2025 open day.</p>", "Department Home"), ORIGIN, "text/html"
    )
    assert document["metadata"]["effective_term"] is None


def test_versions_diffs_and_cohorts_survive_repeated_crawls(archive):
    url = ORIGIN + "/scheme.html"
    first = html(table("3"), "BSCS Scheme Fall 2021")
    old = archive.save("run1", url, first, parse_document(first, url, "text/html"), {})
    same = archive.save("run2", url, first, parse_document(first, url, "text/html"), {})
    second = html(table("4"), "BSCS Scheme Fall 2025")
    new = archive.save("run3", url, second, parse_document(second, url, "text/html"), {})
    assert old["version_id"] == same["version_id"]
    assert len(archive.versions()) == 2 and len(archive.corpus_documents()) == 2
    assert new["change"]["structured_changes"][0]["fields"]["credit_hours"] == {
        "before": 3,
        "after": 4,
    }
    old_version = next(v for v in archive.versions() if v["version_id"] == old["version_id"])
    assert (archive.root / old_version["raw_path"]).read_bytes() == first
    assert archive.export_records(archive.root / "records.jsonl") == 2


def test_same_cohort_revision_and_rollback_select_current_observation(archive):
    url = ORIGIN + "/scheme.html"
    a, b = html(table("3")), html(table("4"))
    old = archive.save("a", url, a, parse_document(a, url, "text/html"), {})
    archive.save("b", url, b, parse_document(b, url, "text/html"), {})
    assert len(archive.corpus_documents()) == 1
    archive.save("c", url, a, parse_document(a, url, "text/html"), {})
    assert archive.corpus_documents()[0]["version_id"] == old["version_id"]
    assert len(archive.versions()) == 2


def test_archive_versions_flow_into_corpus_with_checksums(archive, tmp_path):
    url = ORIGIN + "/scheme.html"
    raw = html(table() + "<p>" + "Official course information. " * 12 + "</p>")
    saved = archive.save("test", url, raw, parse_document(raw, url, "text/html"), {})
    chunks, audit = build_corpus(tmp_path, crawl_archive=archive.root)
    assert audit["crawl_versions"] == 1 and chunks
    assert all(
        c.source_version_id == saved["version_id"] and len(c.source_sha256) == 64 for c in chunks
    )
    assert all(c.verification_status == "archived" for c in chunks)
    assert json.loads(json.dumps(chunks[0].citation()))["source_version_id"] == saved["version_id"]


def test_real_digital_scheme_keeps_semesters_and_credit_components():
    from app.rag.corpus import PROJECT_ROOT

    path = PROJECT_ROOT / "academic-data/bs/bscs_scheme_fall-2025.pdf"
    document = parse_document(path.read_bytes(), ORIGIN + "/doc/scheme-2025.pdf", "application/pdf")
    courses = [r for r in document["records"] if r["record_type"] == "course"]
    programming = next(r for r in courses if r["course_code"] == "CSC-104")
    oop = next(r for r in courses if r["course_code"] == "CSC-121")
    assert programming["semester"] == 1 and programming["credit_hours"] == 4
    assert programming["lecture_hours"] == 3 and programming["lab_hours"] == 1
    assert oop["semester"] == 2 and oop["prerequisites"] is None
    assert len(courses) >= 30
    assert document["metadata"]["program"] == "BSCS"
    assert document["metadata"]["effective_term"] == "Fall 2025"


def test_archive_tampering_is_detected_before_building_evidence(archive):
    url = ORIGIN + "/source.html"
    raw = html("<p>Original published text.</p>")
    archive.save("run", url, raw, parse_document(raw, url, "text/html"), {})
    version = archive.latest(url)
    (archive.root / version["raw_path"]).write_bytes(b"Changed outside ingestion")
    with pytest.raises(ValueError, match="integrity check"):
        archive.parsed(version)


def test_superseded_legacy_scrape_does_not_reenter_current_corpus(archive, tmp_path):
    url = ORIGIN + "/scheme.html"
    raw = html("<p>" + "Current published requirement. " * 12 + "</p>")
    archive.save("run", url, raw, parse_document(raw, url, "text/html"), {})
    scraped = tmp_path / "academic-data/scraped/cs_website_full.json"
    scraped.parent.mkdir(parents=True)
    scraped.write_text(
        json.dumps(
            [{"url": url, "title": "Old snapshot", "content": "An obsolete requirement. " * 20}]
        )
    )
    chunks, _ = build_corpus(tmp_path, crawl_archive=archive.root)
    assert chunks and not any("obsolete" in c.content for c in chunks)


def test_provided_pdf_cannot_become_official_through_archive_exports(archive, tmp_path):
    url = "provided:///student-supplied.pdf"
    raw = html("<p>" + "A supplied course description. " * 10 + "</p>")
    parsed = parse_document(raw, url, "text/html")
    parsed["metadata"]["verification_status"] = "provided_unverified"
    archive.save("run", url, raw, parsed, {})
    chunks, _ = build_corpus(tmp_path, crawl_archive=archive.root)
    assert chunks and all(c.source_url == "" for c in chunks)
    assert all(c.verification_status == "provided_unverified" for c in chunks)


def test_cohort_changes_compare_different_document_urls(archive):
    for year, credits in ((2023, "3"), (2025, "4")):
        url = ORIGIN + f"/scheme-{year}.html"
        raw = html(table(credits), f"BSCS Scheme Fall {year}")
        archive.save("run", url, raw, parse_document(raw, url, "text/html"), {})
    output = archive.root / "cohort_changes.json"
    archive.export_cohort_changes(output)
    report = json.loads(output.read_text())
    assert report["changes"][0]["before_term"] == "Fall 2023"
    assert report["changes"][0]["courses"][0]["fields"]["credit_hours"] == {"before": 3, "after": 4}


def test_query_variant_limit_reports_truncated_discovery(archive):
    def handler(request):
        if request.url.path == "/robots.txt":
            return httpx.Response(404)
        links = "".join(f'<a href="/?page={n}">Page {n}</a>' for n in range(100))
        return httpx.Response(200, content=html(links), headers={"Content-Type": "text/html"})

    report, _ = run_crawl(archive, handler, max_query_variants=2, max_pages=10)
    assert report["visited"] == 3 and report["discarded"] >= 98
    assert report["bounded"] is True


def test_table_cell_paragraphs_do_not_detach_fee_amounts_from_columns():
    document = parse_document(
        html(
            "<table><tr><td>Semester Total</td><td><p>60,860</p></td>"
            "<td><p>100,000</p></td></tr></table>"
        ),
        ORIGIN + "/fees",
        "text/html",
    )
    assert "Semester Total | 60,860 | 100,000" in document["pages"][0]["content"]


def test_programme_summary_belongs_to_its_following_degree_heading():
    from app.rag.corpus import scoped_sections

    content = (
        "MPhil (Computer Science)\nMPhil description.\n"
        "BS Four years (8 semesters) 134 Credit Hours\nBS (Computer Science)\nBS description."
    )
    sections = scoped_sections(content, "programme")
    assert any(program == "BSCS" and "Four years" in text for _, text, program in sections)
    assert not any(program == "MPhil" and "Four years" in text for _, text, program in sections)


def test_archive_reprocessing_preserves_originals_and_current_cohort(archive):
    from scripts.reprocess_source_archive import reprocess

    url = ORIGIN + "/scheme.html"
    for year in (2023, 2025):
        raw = html(table(), f"BSCS Scheme Fall {year}")
        parsed = parse_document(raw, url, "text/html")
        parsed["parser_version"] = 0
        archive.save("old-parser", url, raw, parsed, {})
    previous = archive.latest(url)
    report = reprocess(archive)
    assert report["errors"] == [] and len(archive.versions()) == 4
    assert archive.latest(url)["raw_sha256"] == previous["raw_sha256"]
    assert len(archive.corpus_documents()) == 2
    assert all(
        v["document"]["parser_version"] == PARSER_VERSION for v in archive.corpus_documents()
    )


@pytest.mark.skipif(os.environ.get("RUN_OCR_TESTS") != "1", reason="Requires PyMuPDF and Tesseract")
def test_real_scanned_2021_scheme_uses_installed_ocr():
    from app.rag.corpus import PROJECT_ROOT

    path = PROJECT_ROOT / "academic-data/bs/bscs_scheme_fall-2021.pdf"
    parsed = parse_document(
        path.read_bytes(), ORIGIN + "/doc/scheme-2021.pdf", "application/pdf", ocr=True
    )
    assert parsed["pages"] and any(
        p["extraction_method"] == "tesseract_ocr" for p in parsed["pages"]
    )
    assert sum(len(p["content"]) for p in parsed["pages"]) > 300

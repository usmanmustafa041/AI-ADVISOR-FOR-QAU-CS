"""Procedure/source boundaries; these are engineering tests, not human accuracy grades."""

import pytest
from chatbot_v3.contracts import Task
from chatbot_v3.crawl import safe_url
from chatbot_v3.generation import AnswerBlock, GroundingError, validate_block
from chatbot_v3.index import Index
from chatbot_v3.ingest import import_one, source_metadata
from chatbot_v3.parsing import parse
from chatbot_v3.resources import public_resource_url
from chatbot_v3.store import Store


def task(kind="procedure", **fields):
    return Task(
        question="certificate correction",
        search_query="certificate name correction application",
        topic="procedures",
        evidence_type=kind,
        **fields,
    )


def test_nested_workflows_preserve_ownership_and_real_resource_links(tmp_path):
    page = tmp_path / "services.html"
    page.write_text("""<html><title>Student Services</title><main>
      <section><h2>Name correction</h2><p>Send the completed correction form to the records office.</p>
        <a href="/Downloads/correction.pdf">Correction application</a></section>
      <section><h2>Graduation clearance</h2><p>Obtain departmental clearance.</p>
        <a href="/Downloads/clearance.pdf">Clearance checklist</a></section>
      <form><p>Verify the name printed on the certificate.</p><input name="secret"></form>
      <a href="javascript:alert(1)">Unsafe link</a>
      <a href="https://attacker.example/form.pdf">Unverified mirror</a>
    </main></html>""")
    _, chunks, _ = parse(page, source_uri="https://qau.edu.pk/services/")
    correction = next(c for c in chunks if c.heading == "Name correction")
    assert (
        "records office" in correction.content
        and "departmental clearance" not in correction.content
    )
    assert correction.resources == [
        {"title": "Correction application", "url": "https://qau.edu.pk/Downloads/correction.pdf"}
    ]
    assert not any(
        "attacker" in link["url"] or "javascript" in link["url"]
        for c in chunks
        for link in c.resources
    )
    assert any("Verify the name" in c.content for c in chunks)


def test_download_manager_links_are_read_only_and_stable():
    assert (
        public_resource_url("https://qau.edu.pk/download/form/?wpdmdl=42&refresh=publiccache")
        == "https://qau.edu.pk/download/form/?wpdmdl=42"
    )
    assert (
        safe_url("https://qau.edu.pk/download/form/?wpdmdl=42")
        == "https://qau.edu.pk/download/form/?wpdmdl=42"
    )
    assert public_resource_url("https://qau.edu.pk/?action=delete&wpdmdl=42") is None
    assert public_resource_url("https://qau.edu.pk/?wpdmdl=42&wpdmdl=43") is None
    assert public_resource_url("https://user:password@qau.edu.pk/file.pdf") is None
    assert public_resource_url("https://qau.edu.pk/wp-admin/file.pdf") is None
    assert public_resource_url("https://qau.edu.pk:bad/file.pdf") is None
    with pytest.raises(ValueError):
        safe_url("https://qau.edu.pk/?action=delete")


def test_form_discovery_does_not_certify_unreviewed_rules(tmp_path):
    s = Store(tmp_path / "knowledge.sqlite3")
    page = tmp_path / "rules.html"
    page.write_text(
        "<title>Degree regulations</title><main><h2>Rules</h2><p>Correction requires an approved application and costs 900 rupees.</p></main>"
    )
    import_one(s, page, "https://qau.edu.pk/rules/correction/", "2026-10-01", official=True)
    index = Index(s, load_bundle=False)
    hits, _ = index.search(task())
    assert not hits
    navigation, _ = index.search(task("resource"))
    assert navigation and navigation[0]["evidence_types"] == ["resource"]
    assert "900" not in navigation[0]["content"]
    assert not index.search(task("resource", high_stakes=True))[0]


def test_main_campus_does_not_borrow_affiliated_college_instructions(tmp_path):
    s = Store(tmp_path / "knowledge.sqlite3")
    page = tmp_path / "form.html"
    page.write_text(
        "<title>ICT College certificate correction</title><main><h2>Application</h2><p>Ask the college principal to sign the correction application.</p></main>"
    )
    import_one(
        s,
        page,
        "https://qau.edu.pk/download/certificate-correction-ict/",
        "2026-10-01",
        official=True,
    )
    index = Index(s, load_bundle=False)
    assert not index.search(task())[0]
    assert index.search(task(audience="affiliated_colleges"))[0]


def test_new_capture_replaces_search_visibility_without_deleting_history(tmp_path):
    s = Store(tmp_path / "knowledge.sqlite3")
    page = tmp_path / "services.html"
    page.write_text(
        "<title>Certificate correction</title><main><p>Send the correction form to Office A.</p></main>"
    )
    a = import_one(s, page, "https://qau.edu.pk/download/correction/", "2026-10-01", official=True)
    page.write_text(
        "<title>Certificate correction</title><main><p>Send the correction form to Office B.</p></main>"
    )
    b = import_one(s, page, "https://qau.edu.pk/download/correction/", "2026-10-02", official=True)
    assert {c["source_version_id"] for c in s.chunks()} == {b["version_id"]}
    with s.connect() as c:
        assert c.execute("SELECT count(*) FROM document_version").fetchone()[0] == 2
    s.review(b["version_id"], "rejected", "test reviewer", "Extraction failed verification")
    assert not s.chunks()  # Rejection must not silently resurrect a superseded procedure.
    assert a["version_id"] != b["version_id"]


def test_missing_steps_cannot_be_replaced_by_made_up_numbers():
    evidence = [
        {
            "content": "Correction application form",
            "evidence_types": ["resource"],
            "effective_term": None,
        }
    ]
    b = AnswerBlock(
        text="Attach 7 copies.", sources=[1], kind="university_fact", evidence_type="resource"
    )
    # The type boundary and existing numeric checker remain independent safeguards.
    from chatbot_v3.generation import validate_paragraph

    validate_block(b, evidence, [task()])
    with pytest.raises(GroundingError):
        validate_paragraph(b.text + " [1]", evidence, "Which application form?")


def test_course_outcomes_are_not_a_submission_channel(tmp_path):
    s = Store(tmp_path / "knowledge.sqlite3")
    page = tmp_path / "course.html"
    page.write_text(
        "<title>Capstone studio</title><main><p>BS</p><h1>Capstone studio</h1><p>Deliver a demonstration and written report.</p></main>"
    )
    import_one(s, page, "https://cs.qau.edu.pk/course/csc-599", "2026-10-01", official=True)
    index = Index(s, load_bundle=False)
    q = Task(
        question="studio hand-in",
        search_query="capstone studio report",
        topic="procedures",
        programme="BSCS",
        evidence_type="procedure",
    )
    hits, _ = index.search(q)
    assert hits and all(h["evidence_types"] == ["course_description"] for h in hits)
    assert (
        source_metadata(
            "https://qau.edu.pk/download/transcript-application/", "Transcript application", ""
        )["topic"]
        == "procedures"
    )


def test_specific_content_container_beats_surrounding_sidebar(tmp_path):
    page = tmp_path / "page.html"
    page.write_text(
        '<title>Records form</title><div id="content"><div class="post-texts"><h3>Records form</h3><a data-downloadurl="https://qau.edu.pk/download/form/?wpdmdl=55&refresh=cache" href="#">Download</a></div><div><h3>Unrelated news</h3><p>Sports trials.</p></div></div>'
    )
    _, parts, _ = parse(page, source_uri="https://qau.edu.pk/download/form/")
    assert all("Sports" not in p.content for p in parts)
    assert any(link["url"].endswith("wpdmdl=55") for p in parts for link in p.resources)


def test_document_base_resolves_nested_course_and_download_paths(tmp_path):
    page = tmp_path / "nested.html"
    page.write_text(
        '<base href="https://cs.qau.edu.pk/"><title>Programme</title><main><h2>Resources</h2><a href="doc/report-format.pdf">Report format</a><a href="course/csc-599">Studio</a></main>'
    )
    _, parts, _ = parse(page, source_uri="https://cs.qau.edu.pk/programme/bs-cs")
    urls = {r["url"] for p in parts for r in p.resources}
    assert urls == {
        "https://cs.qau.edu.pk/doc/report-format.pdf",
        "https://cs.qau.edu.pk/course/csc-599",
    }


def test_named_regulations_are_review_required_even_with_a_procedures_slug():
    metadata = source_metadata(
        "https://qau.edu.pk/phd-procedures/", "Regulations Relating to Examinations for PhD", ""
    )
    assert metadata["topic"] == "academic_policy" and metadata["programme"] == "PhD"

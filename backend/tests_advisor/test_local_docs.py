import base64
import io
import json
import zipfile

import numpy as np
import pytest
from fastapi.testclient import TestClient

from advisor.api.app import create_app
from advisor.config import Settings
from advisor.context import build_context
from advisor.ingest.chunker import chunk_document
from advisor.ingest.local_docs import docx_to_markdown, load_document, local_documents
from advisor.retrieval.bundle import Bundle
from advisor.retrieval.retriever import Retriever
from advisor.security import hash_password

W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def make_docx(path, paragraphs):
    """Tiny but valid-enough .docx: paragraphs are (style, text, bullet)."""
    body = ""
    for style, text, bullet in paragraphs:
        ppr = ""
        if style:
            ppr += f'<w:pStyle w:val="{style}"/>'
        if bullet:
            ppr += '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>'
        body += f"<w:p><w:pPr>{ppr}</w:pPr><w:r><w:t>{text}</w:t></w:r></w:p>"
    body += "<w:tbl><w:tr><w:tc><w:p><w:r><w:t>Item</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Deadline</w:t></w:r></w:p></w:tc></w:tr>" \
            "<w:tr><w:tc><w:p><w:r><w:t>Report</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>Week 14</w:t></w:r></w:p></w:tc></w:tr></w:tbl>"
    xml = f'<?xml version="1.0"?><w:document {W}><w:body>{body}</w:body></w:document>'
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", xml)
    return path


@pytest.fixture
def sample(tmp_path):
    d = tmp_path / "documents"
    d.mkdir()
    make_docx(d / "fyp_rules.docx", [
        ("Heading1", "Final Year Project Submission", False),
        (None, "Reports are submitted to the supervisor.", False),
        ("Heading2", "Format", False),
        (None, "Use the department template", True),
        (None, "Maximum two hundred pages", True),
    ])
    (d / "fyp_rules.docx.meta.json").write_text(json.dumps({"title": "FYP Submission Rules", "effective": "Fall 2026"}))
    return d


def test_docx_headings_lists_and_tables_survive(sample):
    md = docx_to_markdown(sample / "fyp_rules.docx")
    assert "## Final Year Project Submission" in md and "### Format" in md
    assert "- Use the department template" in md
    assert "| Item | Deadline |" in md and "| Report | Week 14 |" in md


def test_local_document_is_official_titled_and_noted(sample):
    (doc,) = local_documents(sample)
    assert doc.kind == "department_document" and doc.title == "FYP Submission Rules"
    assert doc.priority == 10 and "Fall 2026" in doc.meta["note"]
    chunks = chunk_document(doc)
    assert chunks and all(c.title == "FYP Submission Rules" for c in chunks)
    assert any("department template" in c.text for c in chunks)


def test_broken_or_unsupported_files_are_skipped_not_fatal(sample):
    (sample / "broken.docx").write_bytes(b"not a zip")
    (sample / "notes.exe").write_bytes(b"MZ")
    assert [d.title for d in local_documents(sample)] == ["FYP Submission Rules"]


def test_plain_text_documents_work(tmp_path):
    (tmp_path / "rules.txt").write_text("# Submission\nThe report is due in week 14.\n")
    (doc,) = local_documents(tmp_path)
    assert "week 14" in doc.text()


@pytest.fixture
def api(tmp_path):
    settings = Settings(data_dir=tmp_path, rate_limit_per_minute=1000, rate_limit_burst=1000)
    ctx = build_context(settings, load_kb=False)
    bundle = Bundle(None, [], np.zeros((0, 4), dtype=np.float32), {"build_id": "t", "chunks": 0})
    ctx.kb.bundle, ctx.kb.retriever = bundle, Retriever(bundle, None, None)
    ctx.db.execute("INSERT INTO admins(username, password_hash) VALUES('root', ?)", (hash_password("a-long-password"),))
    with TestClient(create_app(ctx)) as client:
        token = client.post("/api/v1/admin/login", json={"username": "root", "password": "a-long-password"}).json()["token"]
        yield client, {"Authorization": f"Bearer {token}"}, tmp_path


def b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode()


def test_document_upload_requires_admin(api):
    client, _h, _ = api
    assert client.post("/api/v1/admin/documents", json={"filename": "a.txt", "content_base64": b64(b"hello")}).status_code == 401
    assert client.get("/api/v1/admin/documents").status_code == 401


def test_admin_can_upload_list_and_delete_a_document(api):
    client, h, root = api
    r = client.post("/api/v1/admin/documents", headers=h, json={
        "filename": "FYP rules.txt", "content_base64": b64(b"Submit in week 14."), "title": "FYP Rules", "effective": "Fall 2026"})
    assert r.status_code == 200 and r.json()["needs_rebuild"]
    listed = client.get("/api/v1/admin/documents", headers=h).json()["documents"]
    assert listed[0]["title"] == "FYP Rules" and (root / "documents" / "FYP rules.txt").exists()
    assert client.delete(f"/api/v1/admin/documents/{listed[0]['name']}", headers=h).status_code == 200
    assert client.get("/api/v1/admin/documents", headers=h).json()["documents"] == []


def test_upload_validation(api):
    client, h, _ = api
    bad_type = client.post("/api/v1/admin/documents", headers=h, json={"filename": "x.exe", "content_base64": b64(b"MZ")})
    assert bad_type.status_code == 422
    fake_pdf = client.post("/api/v1/admin/documents", headers=h, json={"filename": "x.pdf", "content_base64": b64(b"hello")})
    assert fake_pdf.status_code == 422  # content must match the extension
    assert client.post("/api/v1/admin/documents", headers=h, json={"filename": "x.txt", "content_base64": "###"}).status_code == 422
    traversal = client.post("/api/v1/admin/documents", headers=h, json={"filename": "../../etc/passwd.txt", "content_base64": b64(b"x")})
    assert traversal.status_code == 200 and traversal.json()["saved"] == "passwd.txt"  # path components stripped
    assert client.delete("/api/v1/admin/documents/..%2Fsecret", headers=h).status_code == 404

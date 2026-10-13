import csv
import io
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest
from chatbot_v3.settings import ROOT, settings
from chatbot_v3.timetable.contracts import (
    PublishAction,
    ReviewAction,
    RowEdit,
    TimetableQuery,
    UploadMetadata,
)
from chatbot_v3.timetable.parser import extract
from chatbot_v3.timetable.query import execute, render
from chatbot_v3.timetable.store import TimetableStore, check_pdf
from fastapi.testclient import TestClient

PDF = ROOT / "TT_v4.1 20-4-26-sp 26.docx.pdf"
META = dict(
    academic_term="Spring 2026",
    effective_from="2026-04-20",
    programmes=["BSCS", "MPhil", "PhD", "MS-DS", "deficiency"],
)


@pytest.fixture(scope="module")
def parsed():
    return extract(PDF)


def stage(s, data=None, **meta):
    version, _ = s.upload(
        data or PDF.read_bytes(), "fixture.pdf", UploadMetadata(**(META | meta)), "test-admin"
    )
    s.parse(version)
    return version


def approve_test_fixture(s, version):
    """Synthetic workflow approval in a test DB, never an independent accuracy label."""
    d = s.detail(version)
    for m in d["meetings"]:
        if any(c["offering_id"] is None for c in m["courses"]):
            s.edit(
                version,
                m["id"],
                RowEdit(
                    expected_revision=s.version(version)["revision"],
                    reason="TEST ONLY: omit unqualified NLP until an administrator resolves its section",
                    changes={"omitted": True},
                ),
                "test-admin",
            )
    for issue in s.detail(version)["issues"]:
        s.resolve(
            version,
            issue["id"],
            ReviewAction(
                expected_revision=s.version(version)["revision"],
                reason="TEST ONLY: AI visual reference; no human approval claimed",
            ),
            "test-admin",
        )
    d = s.detail(version)
    return PublishAction(
        expected_revision=d["revision"],
        expected_active_version=d["active_version"],
        reason="TEST ONLY: exercise lifecycle in isolated database",
        reviewed_pages=list(range(1, d["pages"] + 1)),
        confirm_complete=True,
    )


@pytest.fixture
def active(tmp_path):
    s = TimetableStore(tmp_path)
    v = stage(s)
    s.publish(v, approve_test_fixture(s, v), "test-admin")
    return s, v


def test_full_grid_against_separately_transcribed_visual_reference(parsed):
    with Path(__file__).with_name("timetable_visual_reference.csv").open() as f:
        expected = {
            tuple(row[k] for k in ("weekday", "room", "start", "end", "codes", "section", "page"))
            for row in csv.DictReader(f)
        }
    actual = {
        (
            m["weekday"],
            m["room"],
            m["start_time"],
            m["end_time"],
            "|".join(m["codes"]),
            m["section"],
            str(m["page"]),
        )
        for m in parsed["meetings"]
    }
    assert actual == expected
    assert len(parsed["offerings"]) == 57
    assert {p["page"] for p in parsed["coverage"]} == {1, 2, 3}


def test_legends_overrides_and_unresolved_ownership(parsed):
    offers = parsed["offerings"]
    regular = next(o for o in offers if o["code"] == "CS-104" and o["section"] == "regular")
    selfsupport = next(
        o for o in offers if o["code"] == "CS-104" and o["section"] == "self support"
    )
    assert "Ghazanfar" in regular["faculty"] and "Memoona" in selfsupport["faculty"]
    assert regular["semester"] == 1 and selfsupport["semester"] == 1
    assert all(m["mode"] == "online" for m in parsed["meetings"] if m["weekday"] == "Friday")
    ds = next(
        m for m in parsed["meetings"] if m["weekday"] == "Thursday" and m["codes"] == ["CS-211"]
    )
    assert (ds["start_time"], ds["end_time"]) == ("15:05", "17:15")
    assert {p["page"] for p in ds["provenance"]} == {1, 2}
    nlp = [m for m in parsed["meetings"] if m["codes"] == ["CS-455"]]
    assert len(nlp) == 2 and all(m["links"][0]["offering"] is None for m in nlp)
    assert not any(set(m["codes"]) & {"CS-489", "CS-490"} for m in parsed["meetings"])
    assert {o["semester"] for o in offers if o["code"] == "CS-455"} == {7, 8}
    assert all("Nadia Saeed" in o["faculty"] for o in offers if o["code"] == "CS-455")


def test_upload_stage_no_automatic_publication_duplicate_and_failure(tmp_path):
    s = TimetableStore(tmp_path)
    v = stage(s)
    assert s.version(v)["status"] == "review"
    assert execute(s, TimetableQuery(academic_term="Spring 2026"))["clarification"] == "coverage"
    duplicate, new = s.upload(PDF.read_bytes(), "same.pdf", UploadMetadata(**META), "test-admin")
    assert duplicate == v and not new
    with pytest.raises(ValueError):
        s.publish(
            v,
            PublishAction(
                expected_revision=1,
                reason="not reviewed",
                reviewed_pages=[1, 2, 3],
                confirm_complete=True,
            ),
            "test-admin",
        )
    with pytest.raises(ValueError):
        check_pdf(b"%PDF-1.7\nmalicious broken")


def revised_pdf():
    from pypdf import PdfReader, PdfWriter
    from pypdf.generic import ArrayObject, DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    reader = PdfReader(PDF)
    for page in reader.pages:
        writer.add_page(page)
    # Visible TEST ONLY amendment creates real new bytes; no original is modified.
    page = writer.pages[-1]
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page["/Resources"]["/Font"][NameObject("/TTTest")] = writer._add_object(font)
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /TTTest 10 Tf 40 80 Td (TEST ONLY amendment: Monday CS-104 Regular room 209.) Tj ET"
    )
    old = page.raw_get("/Contents")
    page[NameObject("/Contents")] = ArrayObject([*old] if isinstance(old, ArrayObject) else [old])
    page["/Contents"].append(writer._add_object(stream))
    out = io.BytesIO()
    writer.write(out)
    with __import__("pdfplumber").open(io.BytesIO(out.getvalue())) as verified:
        assert len(verified.pages) == 3
    return out.getvalue()


def test_a_b_historical_rollback_and_consistent_reads(active):
    s, a = active
    q = TimetableQuery(
        academic_term="Spring 2026",
        programme="BSCS",
        semester=1,
        section="regular",
        weekday="Monday",
    )
    assert execute(s, q)["rows"][0]["room"] == "201"
    b = stage(s, revised_pdf())
    d = s.detail(b)
    m = next(
        m
        for m in d["meetings"]
        if m["weekday"] == "Monday"
        and any(c["code"] == "CS-104" and c["section"] == "regular" for c in m["courses"])
    )
    s.edit(
        b,
        m["id"],
        RowEdit(
            expected_revision=d["revision"],
            reason="TEST ONLY amendment printed on page three",
            changes={"room": "209"},
        ),
        "test-admin",
    )
    body = approve_test_fixture(s, b)
    assert s.detail(b)["diff"]["removed"] and s.detail(b)["diff"]["added"]
    with ThreadPoolExecutor(max_workers=4) as pool:
        reads = [pool.submit(execute, s, q) for _ in range(10)]
        s.publish(b, body, "test-admin")
        reads += [pool.submit(execute, s, q) for _ in range(10)]
        for f in reads:
            result = f.result()
            assert {r["version_id"] for r in result["rows"]} <= {result["version"]["id"]}
    assert execute(s, q)["rows"][0]["room"] == "209"
    historical = q.model_copy(update={"historical": True, "version_id": a})
    assert execute(s, historical)["rows"][0]["room"] == "201"
    assert {r.source_version_id for r in render(execute(s, q))[1]} == {b}
    old = s.detail(a)
    s.publish(
        a,
        PublishAction(
            expected_revision=old["revision"],
            expected_active_version=b,
            reason="TEST ONLY rollback",
            reviewed_pages=[1, 2, 3],
            confirm_complete=True,
        ),
        "test-admin",
        rollback=True,
    )
    assert execute(s, q)["rows"][0]["room"] == "201"


def test_cross_term_and_overlapping_scope(active):
    s, a = active
    b = stage(s, revised_pdf(), academic_term="Fall 2026", effective_from="2026-09-01")
    s.publish(b, approve_test_fixture(s, b), "test-admin")
    assert execute(s, TimetableQuery(academic_term="Spring 2026"))["version"]["id"] == a
    assert execute(s, TimetableQuery(academic_term="Fall 2026"))["version"]["id"] == b
    # Incomplete ownership coverage is rejected even if someone dismisses issue flags.
    c = stage(s, PDF.read_bytes(), programmes=["BSCS"])
    with pytest.raises(ValueError, match="coverage|ownership"):
        s.publish(c, approve_test_fixture(s, c), "test-admin")


def test_count_joint_mapping_aliases_and_no_project_time(active):
    s, _ = active
    q = TimetableQuery(academic_term="Spring 2026", weekday="Friday", operation="count_meetings")
    result = execute(s, q)
    assert result["meeting_count"] == 6 and result["course_mapping_count"] == 7
    assert all(r["mode"] == "online" for r in result["rows"])
    assert (
        execute(s, TimetableQuery(academic_term="Spring 2026", course="PSP"))["clarification"]
        == "course"
    )
    assert (
        execute(
            s,
            TimetableQuery(
                academic_term="Spring 2026", programme="BSCS", course="CS104", weekday="Monday"
            ),
        )["meeting_count"]
        == 2
    )
    project = execute(
        s, TimetableQuery(academic_term="Spring 2026", programme="BSCS", course="CS-489")
    )
    assert not project["rows"] and project["legend_only"]
    assert "no meeting time" in render(project)[0]


def test_current_term_clock_half_open_and_free_room_coverage(active):
    s, _ = active
    clock = datetime(2026, 10, 12, 9, 0, tzinfo=ZoneInfo("Asia/Karachi"))
    assert execute(s, TimetableQuery(), clock)["clarification"] == "term"
    assert (
        execute(
            s,
            TimetableQuery(
                academic_term="Spring 2026", operation="next_class", relative_day="today"
            ),
            clock,
        )["clarification"]
        == "term"
    )
    with s.connect(write=True) as c:
        c.execute(
            "INSERT INTO tt_current_term VALUES('CS','QAU','Spring 2026','2026-04-20','2026-06-30')"
        )
    monday = datetime(2026, 4, 20, 10, 5, tzinfo=ZoneInfo("Asia/Karachi"))
    ongoing = execute(
        s,
        TimetableQuery(
            operation="next_class", programme="BSCS", semester=1, section="regular", ongoing=True
        ),
        monday,
    )
    assert not ongoing["rows"]  # 10:05 end is excluded, not counted twice.
    friday = execute(
        s,
        TimetableQuery(
            academic_term="Spring 2026",
            weekday="Friday",
            operation="free_room_intervals",
            at_time="10:00",
            until_time="11:00",
        ),
    )
    assert not friday["free_rooms"] and "cannot be established" in friday["availability_basis"]


# More than 100 indexed-filter variants, with counts derived from independent visual CSV.
# These are tool semantics checks, NOT claims about natural-language interpretation accuracy.
VARIANTS = [
    (day, room, op)
    for day in ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
    for room in ["201", "217", "235", "F8", "F6", "CS Lab", "BS Lab"]
    for op in ["list_classes", "count_meetings", "room_schedule"]
]


@pytest.mark.parametrize("day,room,operation", VARIANTS)
def test_105_structured_query_variants(tmp_path, parsed, day, room, operation):
    # Avoid decoding the PDF 105 times; stage the same extracted layout into each isolated DB.
    s = TimetableStore(tmp_path)
    v, _ = s.upload(PDF.read_bytes(), "fixture.pdf", UploadMetadata(**META), "test-admin")
    with s.connect(write=True) as c:
        c.execute("UPDATE tt_version SET status='parsing' WHERE id=?", (v,))
    s.stage(v, parsed, "test-parser")
    s.publish(v, approve_test_fixture(s, v), "test-admin")
    result = execute(
        s, TimetableQuery(academic_term="Spring 2026", weekday=day, room=room, operation=operation)
    )
    with Path(__file__).with_name("timetable_visual_reference.csv").open() as f:
        expected = [
            r
            for r in csv.DictReader(f)
            if r["weekday"] == day and r["room"] == room and r["codes"] != "CS-455"
        ]
    assert result["meeting_count"] == len(expected)
    assert len({r["version_id"] for r in result["rows"]}) <= 1


def test_admin_api_role_security(tmp_path, monkeypatch):
    from app.core.auth import current_user
    from chatbot_v3.api import create_app
    from chatbot_v3.index import Index
    from chatbot_v3.service import Service
    from chatbot_v3.store import Store

    monkeypatch.setattr(settings(), "data_dir", tmp_path)
    base = Store(tmp_path / "knowledge.sqlite3")
    app = create_app(Service(base, None, Index(base)))
    with TestClient(app) as client:
        assert client.get("/api/v3/admin/timetables/versions").status_code == 401
        app.dependency_overrides[current_user] = lambda: {"id": "test-student", "role": "student"}
        assert client.get("/api/v3/admin/timetables/versions").status_code == 403
        assert (
            client.post(
                "/api/v3/admin/timetables/versions",
                content=PDF.read_bytes(),
                headers={"Content-Type": "application/pdf"},
            ).status_code
            == 403
        )
        app.dependency_overrides[current_user] = lambda: {"id": "test-admin", "role": "admin"}
        assert client.get("/api/v3/admin/timetables/versions").status_code == 200
        assert (
            client.post(
                "/api/v3/admin/timetables/versions",
                content=b"not pdf",
                headers={"Content-Type": "text/plain"},
            ).status_code
            == 415
        )
        assert (
            client.post(
                "/api/v3/timetables/query", json={"academic_term": "Spring 2026"}
            ).status_code
            == 200
        )
        assert (
            client.post("/api/v3/timetables/query", json={"operation": "DROP TABLE"}).status_code
            == 422
        )


def test_active_content_rejected_and_interrupted_job_recovers(active):
    from pypdf import PdfReader, PdfWriter

    s, a = active
    writer = PdfWriter()
    writer.append(PdfReader(PDF))
    writer.add_js('app.alert("untrusted PDF action")')
    out = io.BytesIO()
    writer.write(out)
    with pytest.raises(ValueError):
        check_pdf(out.getvalue())
    b, _ = s.upload(revised_pdf(), "revised.pdf", UploadMetadata(**META), "test-admin")
    with s.connect(write=True) as c:
        c.execute("UPDATE tt_version SET status='parsing' WHERE id=?", (b,))
    assert b in s.recover_jobs()
    assert s.version(b)["status"] == "queued"
    assert execute(s, TimetableQuery(academic_term="Spring 2026"))["version"]["id"] == a


def test_parameterized_query_and_explicit_ownership_review(active):
    s, _ = active
    result = execute(s, TimetableQuery(academic_term="Spring 2026", teacher="' OR 1=1 --"))
    assert not result["rows"]
    assert execute(s, TimetableQuery(academic_term="Spring 2026", programme="BSCS"))["rows"]


def programme_pdf(programme, room):
    """Independent small PDF fixture with a different page size and grid."""
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=420)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    content = []

    def line(x1, y1, x2, y2):
        content.append(f"{x1} {y1} m {x2} {y2} l S")

    def text(x, y, value):
        content.append(f"BT /F1 9 Tf {x} {y} Td ({value}) Tj ET")

    text(20, 390, "TEST ONLY Spring 2026 schedule")
    for x in [20, 100, 150, 280, 410, 580]:
        line(x, 280, x, 340)
    for y in [280, 310, 340]:
        line(20, y, 580, y)
    for x, value in [
        (25, "Day"),
        (105, "Room"),
        (155, "08:35-10:05"),
        (285, "10:15-11:45"),
        (415, "11:55-13:25"),
    ]:
        text(x, 320, value)
    code = "CS-104 PSP R" if programme == "BSCS" else "DS-606 PSDS"
    text(25, 290, "MONDAY")
    text(105, 290, room)
    text(155, 290, code)
    for x in [20, 170, 410, 580]:
        line(x, 140, x, 230)
    for y in [140, 170, 200, 230]:
        line(20, y, 580, y)
    text(25, 210, "Course Code")
    text(175, 210, "Course Title")
    text(415, 210, "Faculty Members")
    text(25, 180, "BS Semester I" if programme == "BSCS" else "MS-DS")
    text(25, 150, code)
    text(175, 150, "Problem Solving" if programme == "BSCS" else "Probability and Statistics")
    text(415, 150, "Test Instructor")
    stream = DecodedStreamObject()
    stream.set_data("\n".join(content).encode())
    page[NameObject("/Contents")] = writer._add_object(stream)
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def test_disjoint_programme_pointers_and_complete_room_occupancy(tmp_path):
    s = TimetableStore(tmp_path)
    a = stage(s, programme_pdf("BSCS", "201"), programmes=["BSCS"])
    s.publish(a, approve_test_fixture(s, a), "test-admin")
    b = stage(s, programme_pdf("MS-DS", "217"), programmes=["MS-DS"])
    s.publish(b, approve_test_fixture(s, b), "test-admin")
    bs = execute(s, TimetableQuery(academic_term="Spring 2026", programme="BSCS"))
    ms = execute(s, TimetableQuery(academic_term="Spring 2026", programme="MS-DS"))
    assert bs["version"]["id"] == a and ms["version"]["id"] == b
    all_dept = execute(
        s, TimetableQuery(academic_term="Spring 2026", operation="count_meetings", weekday="Monday")
    )
    assert all_dept["meeting_count"] == 2 and len(all_dept["version_snapshot"]) == 2
    assert {r.source_version_id for r in render(all_dept)[1]} == {a, b}
    rooms = execute(
        s,
        TimetableQuery(
            academic_term="Spring 2026",
            programme="BSCS",
            operation="free_room_intervals",
            weekday="Monday",
            at_time="09:00",
            until_time="09:30",
        ),
    )
    assert not rooms["free_rooms"]
    assert {r.source_version_id for r in render(rooms)[1]} == {a, b}


def test_section_correction_can_complete_without_repeated_academic_tasks():
    import asyncio

    from chatbot_v3.contracts import ChatRequest
    from chatbot_v3.understanding import understand

    class CorrectionModel:
        calls = 0

        async def structured(self, messages, schema):
            self.calls += 1
            if self.calls == 1:
                return {
                    "original": "correction",
                    "normalized": "I am self support",
                    "language": "english",
                    "mode": "university",
                    "tasks": [],
                }
            return TimetableQuery(
                academic_term="Spring 2026",
                programme="BSCS",
                semester=4,
                section="self support",
                weekday="Tuesday",
            ).model_dump(mode="json")

    state = {
        "timetable": TimetableQuery(
            academic_term="Spring 2026",
            programme="BSCS",
            semester=4,
            section="regular",
            weekday="Tuesday",
        ).model_dump(mode="json")
    }
    plan = asyncio.run(
        understand(
            CorrectionModel(), ChatRequest(message="No, I am self support, not regular."), [], state
        )
    )
    assert plan.timetable_query.section == "self support"
    assert plan.timetable_query.weekday == "Tuesday" and not plan.needs_clarification


def test_disjoint_programmes_respect_each_effective_date(tmp_path):
    s = TimetableStore(tmp_path)
    a = stage(s, programme_pdf("BSCS", "201"), programmes=["BSCS"])
    s.publish(a, approve_test_fixture(s, a), "test-admin")
    b = stage(
        s,
        programme_pdf("MS-DS", "217"),
        programmes=["MS-DS"],
        effective_from="2026-05-01",
    )
    s.publish(b, approve_test_fixture(s, b), "test-admin")
    dated = dict(academic_term="Spring 2026", on_date="2026-04-27")
    assert execute(s, TimetableQuery(**dated, programme="BSCS"))["meeting_count"] == 1
    assert execute(s, TimetableQuery(**dated))["clarification"] == "effective_date"
    availability = execute(
        s,
        TimetableQuery(
            **dated,
            programme="BSCS",
            operation="free_room_intervals",
            at_time="09:00",
            until_time="09:30",
        ),
    )
    assert availability["clarification"] == "effective_date"
    assert "free_rooms" not in availability
    assert execute(s, TimetableQuery(academic_term="Spring 2026", on_date="2026-05-04"))[
        "meeting_count"
    ] == 2

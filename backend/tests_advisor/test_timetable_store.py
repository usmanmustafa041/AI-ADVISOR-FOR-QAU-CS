import datetime as dt
import io
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from advisor.db import Database
from advisor.rag.timetable_qa import Timetable
from advisor.timetable_store import (
    TEMPLATE_CSV, TimetableError, TimetableStore, build_effective, canon_code, clean_session, default_overlay,
    parse_clock, parse_csv, parse_xlsx, sid_of,
)

MONDAY = dt.date(2026, 10, 12)
BASE = json.loads((Path(__file__).parent / "data" / "timetable_fall2026.json").read_text())


@pytest.fixture
def store(tmp_path):
    db = Database(tmp_path / "t.sqlite3")
    kb = SimpleNamespace(bundle=SimpleNamespace(timetable=Timetable.from_json(json.loads(json.dumps(BASE))), build_id="b1"))
    return TimetableStore(db, kb)


def ask(store, q, lang="en", history=None):
    tt = store.current()
    return tt.answer(q, lang, history or [], MONDAY) if tt else None


def session(**kw):
    base = {"day": "Monday", "start": "9:00", "end": "10:30", "room": "Seminar Hall", "program": "BS", "semester": 8,
            "section": "S", "code": "CS-499", "title": "Special Topics", "teacher": "Dr. Test Teacher"}
    return {**base, **kw}


# ------------------------------------------------------------------ validation
def test_clock_and_code_parsing():
    assert parse_clock("8:30") == (8, 30) and parse_clock("1:35 PM") == (13, 35) and parse_clock("08.30") == (8, 30)
    assert parse_clock("25:00") is None and parse_clock("abc") is None
    assert canon_code("cs 413") == "CS-413" and canon_code("CSC413") == "CSC-413" and canon_code("hello") == ""


@pytest.mark.parametrize("bad,expect", [
    ({"day": "Funday"}, "Day must be"), ({"start": "11:00", "end": "10:00"}, "end time must be after"),
    ({"start": "5:00", "end": "6:30"}, "between 6:00 and 23:00"), ({"room": ""}, "Room is required"),
    ({"semester": None}, "Semester is required"), ({"semester": 40}, "between 1 and 12"),
    ({"code": "", "title": ""}, "course code or the course title"), ({"section": "weekend"}, "Section must be"),
    ({"code": "413"}, "Course code must look like"),
])
def test_invalid_sessions_are_rejected_with_a_clear_reason(bad, expect):
    _clean, errors = clean_session(session(**bad))
    assert errors and expect in " ".join(errors)


def test_friendly_inputs_are_normalised():
    clean, errors = clean_session(session(day="mon", start="8.30", end="10:00 am", section="evening", code="cs 413", semester="8th"))
    assert not errors
    assert (clean["day"], clean["time"], clean["section"], clean["code"], clean["semester"]) == ("MONDAY", "8:30-10:00", "S", "CS-413", 8)


# ------------------------------------------------------------------ merge rules
def test_without_edits_the_pdf_timetable_is_used_unchanged(store):
    eff = build_effective(BASE, default_overlay())
    assert len(eff["sessions"]) == len(BASE["sessions"]) and not eff["orphans"] and eff["updated"] == ""
    assert "CS-413" in ask(store, "monday ko 8th semester ki classes", "roman-ur")["text"]


def test_adding_a_session_shows_up_in_answers_immediately_and_is_marked(store):
    res = store.add_session(session(day="Tuesday"), "admin")
    assert res["saved"] and res["id"]
    text = ask(store, "Tuesday classes for semester 8")["text"]
    assert "CS-499" in text and "Special Topics" in text and "Dr. Test Teacher" in text and "✎" in text
    assert "Updated by the department" in text
    assert "CS-499" not in ask(store, "monday ko 8th semester ki classes", "roman-ur")["text"]  # other days unaffected


def test_editing_a_pdf_cell_changes_only_that_cell_and_keeps_the_original(store):
    iis = next(s for s in BASE["sessions"] if s["day"] == "MONDAY" and "CS-413" in s["text"])
    sid = sid_of(iis)
    res = store.update_session(sid, {"day": "Monday", "start": "13:35", "end": "15:05", "room": "201"}, "admin", force=True)
    assert res["saved"]
    monday = ask(store, "Monday classes for semester 8")["text"]
    assert "1:35 – 3:05 PM" in monday and "201" in monday and "11:55 AM" not in monday and "CS-535" in monday
    view = store.admin_view()
    row = next(r for r in view["sessions"] if r["id"] == sid)
    assert row["src"] == "edited" and row["orig"]["room"] == "217" and view["counts"]["edited"] == 1
    store.restore_session(sid, "admin")
    assert "11:55 AM" in ask(store, "Monday classes for semester 8")["text"]


def test_hiding_a_cancelled_class_and_restoring_it(store):
    iis = next(s for s in BASE["sessions"] if s["day"] == "MONDAY" and "CS-413" in s["text"])
    store.delete_session(sid_of(iis), "admin")
    assert "CS-413" not in ask(store, "monday ko 8th semester ki classes", "roman-ur")["text"]
    assert store.admin_view()["counts"]["hidden"] == 1
    store.restore_session(sid_of(iis), "admin")
    assert "CS-413" in ask(store, "monday ko 8th semester ki classes", "roman-ur")["text"]


def test_changing_a_course_teacher_applies_to_every_session_of_that_course(store):
    group = next(c["group"] for c in BASE["classes"] if "VIII" in c["group"])
    label = next(c["label"] for c in next(c for c in BASE["classes"] if c["group"] == group)["courses"] if "413" in c["label"])
    store.set_course(group, label, "Dr. Newman Teacher", None, "admin")
    text = ask(store, "monday ko 8th semester ki classes", "roman-ur")["text"]
    assert "Dr. Newman Teacher" in text and "Muazzam" not in text
    assert "Dr. Newman Teacher" in ask(store, "Dr. Newman kab parhate hain?", "roman-ur")["text"]  # new names are searchable


def test_a_session_teacher_override_is_used_for_that_session_only(store):
    sid = sid_of(next(s for s in BASE["sessions"] if s["day"] == "MONDAY" and "CS-413" in s["text"]))
    store.update_session(sid, {"teacher": "Visiting Faculty"}, "admin", force=True)
    mon, wed = ask(store, "Monday classes for semester 8")["text"], ask(store, "Wednesday classes for semester 8")["text"]
    assert "Visiting Faculty" in mon and "Muazzam Khattak" in wed


def test_clashes_are_reported_and_need_force(store):
    busy = next(s for s in BASE["sessions"] if s["day"] == "MONDAY" and s["room"] == "217")
    start, end = busy["time"].split("-")
    res = store.add_session(session(room="217", start=start, end=end, code="CS-498", title="Clash Course", teacher="Dr. Other Person"), "admin")
    assert res["saved"] is False and any("Room 217 is already used" in w for w in res["warnings"])
    assert store.admin_view()["counts"]["manual"] == 0  # nothing was saved
    assert store.add_session(session(room="217", start=start, end=end, code="CS-498", title="Clash Course", teacher="Dr. Other Person"), "admin", force=True)["saved"]


def test_teacher_double_booking_is_warned(store):
    other = next(s for s in BASE["sessions"] if s["day"] == "MONDAY" and "CS-413" in s["text"])  # Dr. Muazzam Khattak
    start, end = other["time"].split("-")
    res = store.add_session(session(day="Monday", room="Seminar Hall", start=start, end=end, teacher="Dr. Muazzam Khattak"), "admin")
    assert res["saved"] is False and any("also teaching" in w for w in res["warnings"])


def test_modes_pdf_only_pauses_edits_and_manual_only_ignores_the_pdf(store):
    store.add_session(session(day="Tuesday"), "admin")
    store.set_settings("pdf_only", None, None, "admin")
    assert "CS-499" not in ask(store, "Tuesday classes for semester 8")["text"]
    store.set_settings("manual_only", "Spring 2027", "1 Feb 2027", "admin")
    text = ask(store, "Tuesday classes for semester 8")["text"]
    assert "CS-499" in text and "Spring 2027" in text and "department timetable" in text.lower()
    assert ask(store, "Monday classes for semester 3") is None or "No class" in ask(store, "Monday classes for semester 3")["text"] or "doesn't list" in ask(store, "Monday classes for semester 3")["text"]
    assert ask(store, "Monday classes for semester 8") is not None
    with pytest.raises(TimetableError):
        store.set_settings("nonsense", None, None, "admin")


def test_edits_to_a_pdf_cell_that_changed_in_a_new_pdf_become_orphans_not_wrong_data(store):
    sid = sid_of(next(s for s in BASE["sessions"] if s["day"] == "MONDAY" and "CS-413" in s["text"]))
    store.update_session(sid, {"room": "201", "day": "Monday", "start": "13:35", "end": "15:05"}, "admin", force=True)
    changed = json.loads(json.dumps(BASE))
    for s in changed["sessions"]:
        if sid_of(s) == sid:
            s["text"] = "CS-413 IIS (new)"  # the department re-issued the PDF with a different cell
    eff = build_effective(changed, store.overlay())
    assert [o["kind"] for o in eff["orphans"]] == ["edited"]
    assert all(s["src"] != "edited" for s in eff["sessions"])


def test_added_sessions_survive_a_new_pdf(store):
    store.add_session(session(day="Tuesday"), "admin")
    eff = build_effective({**BASE, "sessions": BASE["sessions"][:10], "classes": BASE["classes"]}, store.overlay())
    assert any(s["src"] == "manual" and s["code"] == "CS-499" for s in eff["sessions"])


# ------------------------------------------------------------------ audit / undo / reset
def test_undo_restores_the_previous_state_step_by_step(store):
    store.add_session(session(day="Tuesday"), "alice")
    store.add_session(session(day="Friday", code="CS-497", title="Second"), "bob")
    assert store.admin_view()["counts"]["manual"] == 2 and store.history()[0]["by"] == "bob"
    assert store.undo("bob")["undone"] == "add session"
    view = store.admin_view()
    assert view["counts"]["manual"] == 1 and view["can_undo"]
    store.undo("bob")
    assert store.admin_view()["counts"]["manual"] == 0 and not store.admin_view()["can_undo"]
    with pytest.raises(TimetableError):
        store.undo("bob")


def test_reset_returns_to_the_pdf_and_can_itself_be_undone(store):
    store.add_session(session(day="Tuesday"), "admin")
    store.set_settings("manual_only", None, None, "admin")
    store.reset("admin")
    view = store.admin_view()
    assert view["mode"] == "pdf_plus_edits" and view["counts"]["manual"] == 0
    store.undo("admin")
    assert store.admin_view()["mode"] == "manual_only"


def test_the_chat_picks_up_a_change_without_any_restart_or_rebuild(store):
    first = store.current()
    store.add_session(session(day="Tuesday"), "admin")
    assert store.current() is not first and store.current() is store.current()  # rebuilt once, then cached


# ------------------------------------------------------------------ import / export
def test_csv_template_round_trips_through_import_and_export(store):
    rows, errors = parse_csv(TEMPLATE_CSV)
    assert not errors and len(rows) == 2 and rows[0]["code"] == "CS-413" and rows[1]["section"] == "R"
    store.import_rows(rows, "admin", replace=False)
    exported = store.export_csv()
    assert "Introduction to Information Security" in exported and exported.splitlines()[0].startswith("day,start,end")
    again, errs = parse_csv(exported)
    total = len([r for r in store.admin_view()["sessions"] if r["src"] != "hidden"])
    assert len(again) + len(errs) == total and len(again) >= total - 3  # a few PDF cells have no class/code to export
    assert all("Semester is required" in e["message"] or "Course code" in e["message"] or "course code or the course title" in e["message"] for e in errs)


def test_import_reports_each_bad_row_and_a_missing_header():
    rows, errors = parse_csv("day,start,end,room,program,semester,section,course_code,course_title,teacher\n"
                             "Monday,9:00,10:30,F6,BS,8,S,CS-499,Topics,Dr X\n"
                             "Someday,9:00,10:30,F6,BS,8,S,CS-499,Topics,Dr X\n"
                             "Monday,11:00,10:30,F6,BS,8,S,CS-499,Topics,Dr X\n")
    assert len(rows) == 1 and [e["row"] for e in errors] == [3, 4]
    assert parse_csv("room,teacher\nF6,Dr X")[1][0]["row"] == 1


def test_import_accepts_a_combined_time_column_and_semicolons():
    rows, errors = parse_csv("Day;Time;Room;Semester;Section;Course Code;Course Title;Teacher\nMon;8:30-10:00;F6;5;regular;CS-414;AI;Dr Y\n")
    assert not errors and rows[0]["time"] == "8:30-10:00" and rows[0]["section"] == "R"


def _xlsx(rows):
    strings, sheet_rows = [], []
    for r_i, row in enumerate(rows, start=1):
        cells = []
        for c_i, value in enumerate(row):
            ref = f"{chr(65 + c_i)}{r_i}"
            if isinstance(value, float):
                cells.append(f'<c r="{ref}"><v>{value}</v></c>')
            else:
                strings.append(str(value))
                cells.append(f'<c r="{ref}" t="s"><v>{len(strings) - 1}</v></c>')
        sheet_rows.append(f'<row r="{r_i}">{"".join(cells)}</row>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        ns = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'
        z.writestr("xl/sharedStrings.xml", f'<sst {ns}>' + "".join(f"<si><t>{s}</t></si>" for s in strings) + "</sst>")
        z.writestr("xl/worksheets/sheet1.xml", f'<worksheet {ns}><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>')
    return buf.getvalue()


def test_excel_files_are_read_including_time_formatted_cells():
    data = _xlsx([["day", "start", "end", "room", "program", "semester", "section", "course_code", "course_title", "teacher"],
                  ["Monday", 0.375, 0.4375, "F6", "BS", "8", "S", "CS-499", "Topics", "Dr X"]])  # 9:00 and 10:30 as day fractions
    rows, errors = parse_xlsx(data)
    assert not errors and rows[0]["time"] == "9:00-10:30"
    assert parse_xlsx(b"not a zip")[1][0]["message"].startswith("This is not a valid .xlsx")


def test_import_replace_clears_earlier_manual_rows_but_never_touches_the_pdf(store):
    store.add_session(session(day="Tuesday"), "admin")
    rows, _ = parse_csv(TEMPLATE_CSV)
    store.import_rows(rows, "admin", replace=True)
    view = store.admin_view()
    assert view["counts"]["manual"] == 2 and view["counts"]["pdf"] == len(BASE["sessions"])


def test_exported_cells_cannot_run_as_spreadsheet_formulas_and_survive_a_round_trip(store):
    store.add_session(session(day="Friday", title="=HYPERLINK(\"http://evil\")", teacher="+cmd|calc", code="CS-496", note="@note"), "admin")
    exported = store.export_csv()
    assert "'=HYPERLINK" in exported and "'+cmd" in exported and "'@note" in exported
    rows, errors = parse_csv(exported)
    sample = next(r for r in rows if r["code"] == "CS-496")
    assert sample["title"].startswith("=HYPERLINK") and sample["teacher"].startswith("+cmd")  # the apostrophe is removed on import


def test_a_note_is_shown_to_students_next_to_the_class(store):
    store.add_session(session(day="Friday", note="make-up class"), "admin")
    assert "make-up class" in ask(store, "Friday classes for semester 8")["text"]


def test_manual_only_mode_tells_the_service_to_drop_pdf_timetable_text(store):
    assert store.pdf_ignored() is False
    store.set_settings("manual_only", None, None, "admin")
    assert store.pdf_ignored() is True

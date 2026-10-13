import datetime as dt
import json
from pathlib import Path

import pytest

from advisor.rag.timetable_qa import Timetable, fmt_range, ordinal

MONDAY = dt.date(2026, 10, 12)


@pytest.fixture(scope="module")
def tt():
    return Timetable.from_json(json.loads((Path(__file__).parent / "data" / "timetable_fall2026.json").read_text()))


def ask(tt, q, lang="en", history=None):
    return tt.answer(q, lang, history or [], MONDAY)


def test_the_reported_question_returns_only_eighth_semester_courses(tt):
    r = ask(tt, "monday ko 8th semester ki kon kon c classes hai", "roman-ur")
    text = r["text"]
    assert "CS-413" in text and "Introduction to Information Security" in text and "CS-535" in text
    for wrong in ("EN-100", "ST-101", "CSC-104", "PSP"):  # first/fifth semester courses seen in the bad answer
        assert wrong not in text
    assert "Dr. Muazzam Khattak" in text and "Dr. Imran" in text
    assert "sirf Self-support (evening)" in text  # the PDF lists semester VIII only for the evening programme
    assert r["passage"]["url"].startswith("http") and "[1]" in text
    assert [c["label"] for c in r["followups"]] == ["Wednesday", "Thursday"]


def test_formats_and_ordinals():
    assert fmt_range("11:55-13:25") == "11:55 AM – 1:25 PM"
    assert fmt_range("8:30-10:00") == "8:30 – 10:00 AM"
    assert [ordinal(n) for n in (1, 2, 3, 4, 11, 12, 13, 21)] == ["1st", "2nd", "3rd", "4th", "11th", "12th", "13th", "21st"]


@pytest.mark.parametrize("q", [
    "Monday classes for semester 3 regular", "semester III Monday regular classes", "monday ko third semester regular ki classes",
    "3rd sem monday regular ka timetable",
])
def test_class_day_section_in_many_phrasings(tt, q):
    text = ask(tt, q)["text"]
    assert "Human Computer Interaction" in text and "Introduction to Computer Organization" in text
    assert "Self-support" not in text.split("<sub>")[0].split("Other courses")[0].replace("Regular (morning)", "")


def test_number_words_and_regular_section_match_the_pdf_grid(tt):
    text = ask(tt, "monday ko semester five regular ki classes", "roman-ur")["text"].split("<sub>")[0]
    # Monday, BS Semester V Regular, read cell by cell from the PDF
    for expected in ("ST-101", "217", "CS-414", "Lab 234", "CS-324", "CS-226", "201"):
        assert expected in text
    for self_support_row in ("Moeen Tayyab", "Sagheer Ahmed", "Lab 3"):
        assert self_support_row not in text


def test_unknown_semester_lists_what_exists(tt):
    text = ask(tt, "6th semester timetable")["text"]
    assert "doesn't list BS Semester VI" in text and "Semester VII" in text


def test_teacher_room_time_and_course_lookups(tt):
    t1 = ask(tt, "Dr. Rabeeh kab parhate hain?", "roman-ur")["text"]
    assert "Dr. Rabeeh Abbasi" in t1 and "Data structures" in t1 and "Web Application Development" in t1
    t2 = ask(tt, "room 201 mein Tuesday ko kya hai", "roman-ur")["text"]
    assert "Data structures" in t2 and "room 201" in t2
    t3 = ask(tt, "10 baje kon si class hai monday ko", "roman-ur")["text"]
    assert "10:10" in t3 and "Operating Systems" in t3
    t4 = ask(tt, "OS class kab hoti hai")["text"]
    assert "CS-226" in t4 and "Dr. Khalid Saleem" in t4


def test_free_room_and_empty_day(tt):
    assert "booked all day" in ask(tt, "when is room 217 free on monday")["text"]
    assert "No classes are scheduled on Sunday" in ask(tt, "sunday ko classes")["text"]


def test_today_uses_the_given_date(tt):
    text = ask(tt, "aaj kon si classes hain")["text"]
    assert "**Monday**" in text and "Ye raha" in text  # Roman Urdu is recognised even though langdetect says English


def test_follow_up_borrows_the_class_from_the_previous_question(tt):
    hist = [("user", "Monday ko 8th semester ki classes"), ("assistant", "...")]
    text = ask(tt, "aur Wednesday?", "roman-ur", hist)["text"]
    assert "BS Semester VIII" in text and "ICT and Society" in text


@pytest.mark.parametrize("q", [
    "who is the chairperson", "when was Dr Khalid appointed", "who teaches Data Structures this semester",
    "what are the exam dates", "when do admissions close", "what is the fee for BSCS", "Dr. Rabeeh publications",
    "what are the prerequisites of Operating Systems", "how many credit hours is DSA", "when do classes start",
])
def test_non_timetable_questions_are_left_alone(tt, q):
    assert ask(tt, q) is None


def test_bare_timetable_request_gets_friendly_help(tt):
    text = ask(tt, "show me the timetable")["text"]
    assert "Monday classes for 8th semester" in text


def test_room_names_in_the_pdf_are_cleaned(tt):
    assert not any(r in ("Lab Lab 3", "234 Lab 3", "room BS Lab") for r in tt.rooms)


def test_no_class_on_that_day_names_the_days_it_does_meet_without_stray_wording(tt):
    text = ask(tt, "Tuesday ko 8th semester ki classes", "roman-ur")["text"]
    assert "poore hafte" not in text and "BS Semester VIII" in text and "Monday, Wednesday, Thursday" in text
    en = ask(tt, "Tuesday classes for semester 8")["text"]
    assert "whole week" not in en and "no class for" in en.lower()

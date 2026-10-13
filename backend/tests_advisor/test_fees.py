import json
from pathlib import Path

import pytest

from advisor.ingest.fees import core_rows, fee_documents, one_time_rows, parse_fee_page
from advisor.rag.fees_qa import Fees

DATA = Path(__file__).parent / "data"
PAGES = json.loads((DATA / "fees_fall2026.json").read_text())


@pytest.fixture(scope="module")
def fees():
    return Fees.from_json({"pages": PAGES})


def ask(fees, q, lang="en", history=None):
    return fees.answer(q, lang, history or [])


# ------------------------------------------------------------------ parsing the real pages
def test_bachelor_page_keeps_the_three_tables_apart_with_term_and_columns():
    page = parse_fee_page("https://qau.edu.pk/bachelor-fee-structure/", (DATA / "fees_bachelor.html").read_text())
    assert page["level"] == "BS" and [g["id"] for g in page["groups"]] == ["cs", "other", "foreign"]
    cs = page["groups"][0]
    assert cs["term"] == "Fall 2026" and cs["columns"] == ["R", "S"] and cs["currency"] == "PKR"
    core = core_rows(cs)
    assert core["admission"]["values"] == [38040, 38480]        # the Computer Science row, not "Except … Comp. Sc."
    assert core["per_semester"]["values"] == [68490, 142140]
    assert core["first_total"]["values"] == [106530, 180620]    # "Only for Law, Computer Sciences & IT"
    assert cs["summer"]["values"] == [10670, 11620]
    foreign = page["groups"][2]
    assert foreign["currency"] == "USD" and core_rows(foreign)["per_semester"]["values"] == [378]
    assert next(r for r in one_time_rows(cs) if r["head"].startswith("Degree Fee"))["values"] == [6800, 6800]


def test_phd_page_is_single_column_and_has_its_own_numbers():
    page = parse_fee_page("https://qau.edu.pk/phd-fee-structure/", (DATA / "fees_phd.html").read_text())
    cs = page["groups"][0]
    assert cs["columns"] == ["ALL"] and cs["term"] == "Fall 2025"
    assert core_rows(cs)["per_semester"]["values"] == [65390] and core_rows(cs)["first_total"]["values"] == [100600]


def test_a_non_fee_page_is_ignored():
    assert parse_fee_page("https://qau.edu.pk/admissions/", "<table><tr><td>Fee Heads</td></tr></table>") is None


def test_the_printed_totals_add_up_for_every_computer_science_table():
    for page in PAGES:
        cs = next(g for g in page["groups"] if g["id"] == "cs")
        core = core_rows(cs)
        for i in range(len(core["per_semester"]["values"])):
            assert core["admission"]["values"][i] + core["per_semester"]["values"][i] == core["first_total"]["values"][i], page["level"]


def test_indexed_text_labels_every_table_so_other_programmes_cannot_be_mistaken_for_cs():
    page = parse_fee_page("https://qau.edu.pk/bachelor-fee-structure/", (DATA / "fees_bachelor.html").read_text())
    blocks = fee_documents(page)[0].blocks
    cs = next(b for b in blocks if b.meta["variant"] == "fees-core-cs").text
    other = next(b for b in blocks if b.meta["variant"] == "fees-core-other").text
    assert "68,490 PKR" in cs and "Fee per semester (Category B, charged every semester)" in cs
    assert "NOT for Computer Science" in other and "foreign" not in other.lower().split("—")[1]
    assert "68,490" not in other


# ------------------------------------------------------------------ the reported question
def test_fee_structure_question_gives_semester_fees_not_the_summer_course_fee(fees):
    text = ask(fees, "fee structure kia hai?", "roman-ur")["text"]
    table = text.split("\n\n")[1]
    assert "68,490" in table and "142,140" in table and "38,040" in table and "106,530" in table  # BS morning + evening
    assert "40,040" in table and "65,390" in table                                                  # MPhil, PhD
    first_row = table.splitlines()[2]
    assert first_row.startswith("| Har semester ki fee") and "10,670" not in first_row
    assert "Summer semester" in text and "Rs. 10,670" in text                                         # summer is a separate, labelled line
    assert "MS" in text and "department office" in text                                               # MS page is not available: say so


def test_programme_and_shift_filters(fees):
    eve = ask(fees, "BS evening fee")["text"]
    assert "142,140" in eve and "68,490" not in eve and "BS · Regular" not in eve.split("\n\n")[1]
    reg = ask(fees, "BS morning semester fee")["text"]
    assert "68,490" in reg and "142,140" not in reg
    phd = ask(fees, "PhD fee")["text"]
    assert "65,390" in phd and "35,210" in phd and "100,600" in phd and "142,140" not in phd and "BS" not in phd.split("\n\n")[1]
    mphil = ask(fees, "mphil ki fee kitni hai", "roman-ur")["text"]
    assert "40,040" in mphil and "75,250" in mphil and "65,390" not in mphil


def test_what_exactly_is_asked_changes_the_rows(fees):
    per_sem = ask(fees, "per semester fee for BS")["text"]
    assert "Per semester" in per_sem and "Admission fee" not in per_sem
    adm = ask(fees, "BS admission fee")["text"]
    assert "Admission fee" in adm and "106,530" in adm and "Per semester" not in adm
    summer = ask(fees, "summer semester fee")["text"]
    assert "10,670" in summer and "9,880" in summer and "at least 12 students" in summer
    foreign = ask(fees, "fee for foreign students")["text"]
    assert "$378" in foreign and "$733" in foreign and "US dollars" in foreign
    degree = ask(fees, "degree fee kitni hai", "roman-ur")["text"]
    assert "6,800" in degree and "Degree Fee" in degree
    assert "13,600" in ask(fees, "duplicate degree fee")["text"]
    assert "Migration" in ask(fees, "migration certificate fee")["text"]


def test_ms_is_not_invented(fees):
    text = ask(fees, "MS fee kitni hai", "roman-ur")["text"]
    assert "MS" in text and "department office" in text
    assert not any(n in text for n in ("40,040", "65,390", "68,490"))


def test_urdu_script_questions_work(fees):
    assert "142,140" in ask(fees, "BS ایوننگ کی فیس", "ur")["text"]
    assert "فیس" in ask(fees, "فیس کتنی ہے؟", "ur")["text"]


def test_follow_ups_borrow_from_the_previous_fee_question(fees):
    hist = [("user", "BS morning fee"), ("assistant", "...")]
    assert "142,140" in ask(fees, "aur evening ki?", "roman-ur", hist)["text"]
    assert "65,390" in ask(fees, "and PhD?", "en", hist)["text"]
    assert ask(fees, "and PhD?", "en", []) is None  # no earlier fee question → not a fee lookup


@pytest.mark.parametrize("q", [
    "fee refund policy", "is there any scholarship or fee waiver", "how to pay the fee", "hostel fee", "late fee fine",
    "fee deadline", "last date to submit fee", "who is the chairperson", "when do classes start", "what is the prerequisite of DSA",
    "fee challan kaise banta hai", "bank account number for fee", "admission requirements for BS", "Monday classes",
])
def test_questions_that_are_not_fee_amounts_are_left_to_normal_answering(fees, q):
    assert ask(fees, q) is None


@pytest.mark.parametrize("lang", ["en", "roman-ur", "ur"])
def test_every_suggested_follow_up_chip_is_itself_answerable(fees, lang):
    first = ask(fees, {"en": "fee structure", "roman-ur": "fee structure kia hai", "ur": "فیس کتنی ہے"}[lang], lang)
    assert len(first["followups"]) >= 4
    for chip in first["followups"]:
        again = ask(fees, chip["text"], lang)
        assert again is not None and again["text"], chip


def test_sources_cover_every_page_used(fees):
    r = ask(fees, "fee structure")
    assert [p["url"].rsplit("/", 1)[1] for p in r["passages"]] == ["bachelor-fee-structure", "mphil-programme-fee-structure", "phd-fee-structure"]
    assert "[1]" in r["text"] and "[3]" in r["text"]
    assert "BS **Fall 2026**" in r["text"] and "MPhil / PhD **Fall 2025**" in r["text"]  # each programme's term is stated
    assert [p["url"] for p in ask(fees, "BS fee")["passages"]] == ["https://qau.edu.pk/bachelor-fee-structure"]


def test_roman_urdu_is_recognised_even_when_language_detection_says_english(fees):
    r = ask(fees, "fee structure kia hai?", "en")
    assert "Har semester ki fee" in r["text"] and r["followup_title"] == "Aap ye bhi pooch sakte hain"
    assert "Per semester (every semester)" in ask(fees, "what is the fee for BS", "en")["text"]

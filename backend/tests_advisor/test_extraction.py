from advisor.ingest.chunker import chunk_document, code_aliases, split_text
from advisor.ingest.htmlmd import html_to_markdown
from advisor.ingest.model import Block, Document
from advisor.ingest.web_extract import (
    extract_web,
    fix_mojibake,
    parse_faculty_listing,
    split_faq_blocks,
)

PAGE = """<html><head><title>X</title><base href="https://cs.qau.edu.pk/"></head><body>
<nav>menu junk</nav><div id="main-content">
<h1>Admissions</h1>
<div class="accordion"><div class="accordion-item"><h2 class="accordion-header"><button class="accordion-button">When do admissions open?</button></h2>
<div class="accordion-collapse collapse"><div class="accordion-body">In the Fall semester.</div></div></div></div>
<div class="scheme-panel" style="display:none"><h3>Hidden tab</h3><table><tr><th>Code</th><th>Name</th></tr><tr><td>CSC-104</td><td><a href="/course/csc-104">Problem Solving</a></td></tr></table></div>
<p>Rules: <a href="doc/Rules-BS.pdf">BS rules</a> and <a href="/course/csc-211">a course</a>. <a href="https://doi.org/10.1/x">doi</a></p>
<table><tr><td>PLO1</td><td>Education</td></tr></table>
</div><footer>footer junk</footer></body></html>"""


def test_markdown_keeps_faq_question_tab_panels_and_drops_chrome():
    _title, md = html_to_markdown(PAGE, "https://cs.qau.edu.pk/admissions")
    assert "**Q: When do admissions open?**" in md and "In the Fall semester." in md
    assert "| CSC-104 | Problem Solving |" in md  # tab panel with display:none was kept
    assert "menu junk" not in md and "footer junk" not in md


def test_link_policy_and_base_href():
    _t, md = html_to_markdown(PAGE, "https://cs.qau.edu.pk/programme/bs-cs")
    assert "[BS rules](https://cs.qau.edu.pk/doc/Rules-BS.pdf)" in md  # resolved against <base>
    assert "/course/csc-211" not in md  # internal page links add noise
    assert "doi.org" not in md


def test_headerless_table_is_not_given_a_fake_header():
    _t, md = html_to_markdown(PAGE, "https://x/")
    assert "PLO1 | Education" in md and "|---|" not in md.split("PLO1")[1][:30]


def test_faq_blocks_become_atomic_pairs():
    blocks = split_faq_blocks([Block("H", "intro\n**Q: A?**\nan a\n**Q: B?**\nan b")])
    assert [b.atomic for b in blocks] == [False, True, True]
    assert blocks[1].heading.endswith("FAQ: A?")


COURSE = """<html><head><title>CSC-211: Data Structures — CS QAU</title></head><body><div id="main-content">
<div>CSC-211</div><div>BS</div><h1>Data Structures</h1><p>(DC) Domain Core</p><p>Theory: 3 Cr. Hrs</p><p>Lab: 1 Cr. Hr</p><p>Total: 4 Cr. Hrs</p>
<p><b>Objectives:</b> Learn trees.</p><p><b>Contents:</b> stacks; queues</p>
<h5>Prerequisites</h5><div><a href="/course/csc-121">CSC-121: Object Oriented Programming</a></div>
<h5>In Programmes</h5><div>BS</div><div>BS (Computer Science)</div><div>Semester 3 —</div><div>Core</div><div>(Fall 2026 onwards)</div>
<h5>Taught By</h5><div><a>Dr. Ayyaz Hussain</a><br>Professor</div><div><a>Dr. Umer Rashid</a><br>Associate Professor</div>
<a>Back to Course Catalog</a></div></body></html>"""


def test_course_record_is_structured():
    (doc,) = extract_web("https://cs.qau.edu.pk/course/csc-211", COURSE)
    assert doc.kind == "course" and doc.meta["course_code"] == "CSC-211"
    text = doc.text()
    assert "Credit hours: 4 total (theory 3, lab 1)" in text
    assert "Prerequisites: CSC-121 — Object Oriented Programming" in text
    assert "Semester 3" in text and "Dr. Ayyaz Hussain (Professor)" in text


def test_missing_prerequisites_are_stated_not_invented():
    html = COURSE.replace("<h5>Prerequisites</h5><div><a href=\"/course/csc-121\">CSC-121: Object Oriented Programming</a></div>", "")
    (doc,) = extract_web("https://cs.qau.edu.pk/course/csc-211", html)
    assert "none listed on the course page" in doc.text()


def test_faculty_listing_supplies_room_and_position():
    md = """Dr. A B
Dr. A B
Professor, Chairperson
HEC Supervisor
a@qau.edu.pk
+92-51-9064-2059 (+925190642059)
Room 222
Dr. C D
Dr. C D
Lecturer
c@qau.edu.pk
"""
    entries = parse_faculty_listing(md)
    assert entries["dr. a b"]["position"] == "Professor, Chairperson"
    assert entries["dr. a b"]["room"] == "Room 222"
    assert entries["dr. c d"]["email"] == "c@qau.edu.pk"


def test_mojibake_repair():
    assert fix_mojibake("Bachelors of Science â€“ Nathia Gali") == "Bachelors of Science – Nathia Gali"


def test_course_code_aliases_cover_both_generations():
    forms = code_aliases("see CS-211 and CSC-104")
    assert {"CSC-211", "CS-211", "CS-104", "CSC-104"} <= set(forms)


def test_table_split_repeats_header():
    rows = "\n".join(f"| CSC-{i:03d} | Course number {i} with a longish name | 3 |" for i in range(100, 160))
    table = "| Code | Name | Cr |\n|---|---|---|\n" + rows
    parts = split_text(table, 800)
    assert len(parts) > 1 and all(p.startswith("| Code | Name | Cr |") for p in parts)


def test_atomic_blocks_are_never_merged_or_split_mid_record():
    doc = Document("https://x/", "T", "faq", [Block("A", "short one", atomic=True), Block("B", "short two", atomic=True)])
    assert [c.text for c in chunk_document(doc)] == ["short one", "short two"]

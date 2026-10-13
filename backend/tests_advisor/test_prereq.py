import json
from pathlib import Path

import pytest

from advisor.prereq.graph import Edge, Graph, Resolver, add_department_list, analyse, canon, conflicts, norm_title
from advisor.prereq.verify import verify

DATA = Path(__file__).resolve().parents[1] / "advisor" / "prereq" / "data"
LIST_JSON = DATA / "bscs_approved_list_2021.json"
LIST_DOCX = DATA / "bscs_approved_list_2021.docx"


@pytest.fixture(scope="module")
def dept():
    g = Graph()
    add_department_list(g, LIST_JSON)
    return g, Resolver(g)


def test_supplied_file_is_consistent_and_every_quote_is_in_the_original_document():
    r = verify(LIST_JSON, LIST_DOCX)
    assert r["errors"] == [] and r["stats"]["quotes_checked_against_source"]
    assert r["stats"]["prerequisite_rows"] == 19


def test_code_normalisation_across_printed_variants():
    assert canon("CS 103") == canon("CS-103") == "CSC-103"
    assert canon("BY:201") == "BY-201" and canon("MA 203") == "MA-203"


def test_chain_psp_oop_ds(dept):
    g, _ = dept
    anc = g.ancestors("CSC-211")
    assert anc == {"CSC-121": 1, "CSC-104": 2}
    assert g.path("CSC-104", "CSC-211") == ["CSC-104", "CSC-121", "CSC-211"]
    assert g.path("CSC-211", "CSC-105") is None  # direction matters


def test_dependents_and_transitive_blocking(dept):
    g, _ = dept
    assert set(g.children("CSC-322")) >= {"CSC-332", "CSC-474", "CSC-483", "CSC-486"}
    assert {"CSC-211", "CSC-311", "CSC-423"} <= set(g.descendants("CSC-104"))


def test_no_cycles(dept):
    assert dept[0].has_cycle() is None


def test_the_list_is_silent_about_projects_so_nothing_is_invented(dept):
    g, _ = dept
    assert g.parents("CSC-489") == [] and g.parents("CSC-490") == []
    assert "approved-list-2021" in g.silent["CSC-490"]


def ask(dept, q):
    g, r = dept
    return analyse(g, r, q)


def test_student_abbreviations_resolve(dept):
    a = ask(dept, "I haven't passed PSP, can I take DSA?")
    assert a and "Problem Solving and Programming must be passed before Data Structures (indirectly)" in a.text
    assert "Object Oriented Programming" in a.text.split("Chain:")[1].split("\n")[0]


@pytest.mark.parametrize("q", [
    "What do I need before Net Centric Programming?",
    "what should i pass first for software construction",
    "OOP ke liye pehle kya zaroori hai?",
    "what comes after Data Structures",
])
def test_natural_phrasings_trigger_the_analysis(dept, q):
    assert ask(dept, q) is not None


def test_unrelated_question_gets_no_analysis(dept):
    assert ask(dept, "When do terminal exams start?") is None
    assert ask(dept, "What is the prerequisite of cooking?") is None  # nothing resolved


def test_title_matching_handles_plurals(dept):
    a = ask(dept, "What are the prerequisites of Computer Communications and Networks?")
    assert a and "Assembly Language" in a.text and "Introduction to Computer Organization" in a.text


def test_two_unrelated_courses_say_so(dept):
    a = ask(dept, "Can I take Computer Graphics and Compiler Construction together, prerequisite?")
    assert a and "No prerequisite link is listed" in a.text


def test_blocked_list_is_complete_and_numbered(dept):
    a = ask(dept, "If I fail PSP which courses are blocked?")
    assert "list ALL of them" in a.text and "1) " in a.text


def test_conflicting_sources_are_reported_not_merged():
    g = Graph()
    g.sources["a"] = {"label": "Official list", "title": "A", "kind": "department_document"}
    g.sources["b"] = {"label": "Website", "title": "B", "kind": "website"}
    g.node("CSC-489", "Project-I", "a")
    g.node("CSC-490", "Project-II", "a")
    g.add_edge(Edge("CSC-490", "CSC-489", "b", quote="Project-II requires Project-I"))
    g.silent["CSC-490"].add("a")
    a = analyse(g, Resolver(g), "What is the prerequisite of FYP2?")
    assert a and "THE SOURCES DISAGREE" in a.text and "lists NO prerequisite" in a.text
    assert conflicts(g)[0]["silent_in"] == ["Official list"]


def test_equivalent_renumbered_codes_are_one_course():
    g = Graph()
    g.sources["a"] = {"label": "L", "title": "L", "kind": "x"}
    g.node("CSC-104", "Problem Solving and Programming", "a")
    g.node("CSC-105", "Problem Solving and Programming", "a")
    g.add_edge(Edge("CSC-121", "CSC-104", "a"))
    assert g.parents("CSC-121") == ["CSC-104"]  # CSC-104 (timetable code) is the representative


def test_graph_round_trips_through_json(dept):
    g, _ = dept
    g2 = Graph.from_json(json.loads(json.dumps(g.to_json())))
    assert g2.ancestors("CSC-211") == g.ancestors("CSC-211") and g2.silent == g.silent


def test_title_normalisation_tolerates_the_departments_own_typos():
    assert norm_title("Complier Construction") == norm_title("Compiler Construction")
    assert norm_title("Database System") == norm_title("Database Systems")
    assert norm_title("Project-I (Demonstration)") == "project i"


def test_verifier_rejects_bad_data(tmp_path):
    base = json.loads(LIST_JSON.read_text())

    def check(mutate):
        d = json.loads(json.dumps(base))
        mutate(d)
        p = tmp_path / "x.json"
        p.write_text(json.dumps(d))
        return verify(p, LIST_DOCX)["errors"]

    assert any("not found verbatim" in e for e in check(lambda d: d["prerequisites"][0].update(source_quote="Pre-Requisite CS-999: Invented")))
    assert any("own prerequisite" in e for e in check(lambda d: d["prerequisites"][0].update(prereq_code=d["prerequisites"][0]["course_code"])))
    assert any("missing source_quote" in e for e in check(lambda d: d["prerequisites"][0].update(source_quote="")))

    def cycle(d):
        d["prerequisites"].append({**d["prerequisites"][0], "course_code": "CS-105", "prereq_code": "CS-211",
                                   "source_quote": d["prerequisites"][0]["source_quote"]})

    assert any("cycle" in e for e in check(cycle))


def test_addendum_completes_omitted_list_items_and_always_reports_disagreements():
    g = Graph()
    g.sources["a"] = {"label": "Official list", "title": "A", "kind": "department_document"}
    g.sources["b"] = {"label": "Website", "title": "B", "kind": "website"}
    for code, title in (("CSC-322", "Software Construction"), ("CSC-332", "Net Centric Programming"),
                        ("CSC-474", "Software Testing Techniques"), ("CSC-312", "Computer Networks")):
        g.node(code, title, "a")
    g.add_edge(Edge("CSC-332", "CSC-322", "a"))
    g.add_edge(Edge("CSC-474", "CSC-322", "a"))
    g.add_edge(Edge("CSC-332", "CSC-312", "b"))
    a = analyse(g, Resolver(g), "Which courses need Software Construction?")
    out = a.addendum("Which courses need Software Construction?", "Software Testing Techniques needs it. [1]")
    assert "Net Centric Programming" in out  # omitted by the 'model', restored by code
    assert "Software Testing Techniques" not in out.split("complete the list:")[1].split("\n")[0]
    b = analyse(g, Resolver(g), "What do I need before Net Centric Programming?")
    assert "The sources differ" in b.addendum("What do I need before Net Centric Programming?", "It needs Computer Networks.")


def test_addendum_is_silent_when_the_answer_is_complete_and_sources_agree(dept):
    g, r = dept
    a = analyse(g, r, "What are the prerequisites of Data Structures?")
    assert a.addendum("What are the prerequisites of Data Structures?", "It requires Problem Solving and Programming → Object Oriented Programming.") == ""


def test_pair_question_always_shows_the_middle_of_the_chain(dept):
    g, r = dept
    q = "I did not pass PSP. Can I register for DSA?"
    a = analyse(g, r, q)
    out = a.addendum(q, "No — PSP is a prerequisite for DSA.")
    assert "Problem Solving and Programming → Object Oriented Programming → Data Structures" in out
    # when the model already named the intermediate course, nothing is added
    assert a.addendum(q, "PSP → Object Oriented Programming → Data Structures, so no.") == ""


def test_timetable_section_letters():
    from advisor.ingest.timetable import section_of

    assert section_of("CSC-104 PSP S") == "Self-support (evening)"
    assert section_of("CSC-104 PSP R") == "Regular (morning)"
    assert section_of("MA-101R") == "Regular (morning)"
    assert section_of("CS-211 DS R+S") == "Regular (morning) + Self-support (evening)"
    assert section_of("CS-104 PSP Rep") == "Repeaters"
    assert section_of("FQ-101 S/FQ-601") == "Self-support (evening)"
    assert section_of("CS-352 DSA") == ""


def test_everyday_words_do_not_trigger_the_prerequisite_list(dept):
    """A chat follow-up such as "what did I ask you first?" must not get a prerequisite list appended."""
    g, resolver = dept
    q = "What are the prerequisites of Data Structures?"
    a = analyse(g, resolver, q)
    assert a is not None
    assert a.addendum("what did I ask you first?", "You asked about Data Structures.", course_named=False) == ""
    # with a course named, "before" still means a prerequisite question and omitted items are restored
    assert "complete the list" in a.addendum("What do I need before Data Structures?", "Nothing special.", course_named=True)

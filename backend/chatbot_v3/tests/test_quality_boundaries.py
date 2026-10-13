"""Regressions for demonstrated false prerequisites and unsupported faculty matches."""

import pytest
from chatbot_v3.contracts import QueryUnderstanding, Task
from chatbot_v3.facts import faculty_view, resolve_entities, typed_view
from chatbot_v3.generation import AnswerBlock, GroundingError, answer_messages, validate_block


def test_official_course_rows_do_not_require_translation_but_prose_does():
    from chatbot_v3.generation import is_source_data_block, language_matches

    evidence = [
        {"content": "Semester 5\nCSC-322: Software Construction DC 2+1\nDomain Elective 1 DE 3"}
    ]
    block = AnswerBlock(
        text="1. CSC-322: Software Construction (DC 2+1)\n2. Domain Elective 1 (DE 3)",
        kind="university_fact",
        evidence_type="semester_courses",
        sources=[1],
    )
    assert not language_matches(block.text, "roman_urdu")
    assert is_source_data_block(block, evidence)
    assert not is_source_data_block(
        block.model_copy(update={"text": "Here are your subjects."}), evidence
    )
    assert not is_source_data_block(
        block.model_copy(update={"text": "CSC-322: Software Construction DC 4"}), evidence
    )


def test_interpreted_degree_reaches_policy_tool_without_leaking_cohort_into_fees():
    import asyncio

    from chatbot_v3.contracts import ChatRequest
    from chatbot_v3.understanding import understand

    class Model:
        async def structured(self, messages, schema):
            return {
                "original": "BSCS attendance and hostel fees?",
                "normalized": "attendance and fees",
                "language": "english",
                "mode": "university",
                "programme": "BSCS",
                "admission_batch": "Fall 2024",
                "tasks": [
                    {
                        "question": "Attendance?",
                        "search_query": "attendance",
                        "topic": "academic_policy",
                    },
                    {"question": "Hostel fees?", "search_query": "hostel fees", "topic": "fees"},
                ],
            }

    plan = asyncio.run(
        understand(Model(), ChatRequest(message="BSCS attendance and hostel fees?"), [], {})
    )
    assert plan.tasks[0].programme == "BSCS"
    assert plan.tasks[1].admission_batch is None and plan.tasks[1].programme is None


def test_nested_degree_card_keeps_eligibility_and_faq_under_its_own_heading(tmp_path):
    from chatbot_v3.parsing import parse

    page = tmp_path / "admissions.html"
    page.write_text("""<html><title>Admissions</title><main><div>
    <div><div class="admission-card"><div><h4>BS (Computer Science)</h4></div>
    <p>Intermediate with Mathematics with minimum 50% marks.</p></div>
    <div><h3>BS FAQs</h3><p>Apply through the central admission portal.</p></div></div>
    <div><div class="admission-card"><h4>MPhil (Computer Science)</h4>
    <p>16 years of education.</p></div><p>Admission test is 90 to 120 minutes.</p></div>
    </div></main></html>""")
    _, parts, _ = parse(page)
    bs = next(p for p in parts if p.heading == "BS (Computer Science)")
    assert "minimum 50%" in bs.content and "central admission portal" in bs.content
    assert "16 years" not in bs.content


def test_scheme_cannot_supply_prerequisite_evidence_even_if_both_codes_are_present():
    task = Task(
        question="its prerequisite?",
        search_query="CSC-104 prerequisite",
        topic="curriculum",
        course_codes=["CSC-104"],
        evidence_type="prerequisite",
    )
    chunk = {"topic": "curriculum", "content": "CSC-110 ICT 2+1\nCSC-104 Programming 3+1"}
    assert typed_view(chunk, task) is None
    block = AnswerBlock(
        text="CSC-110 is a prerequisite for CSC-104.",
        sources=[1],
        kind="university_fact",
        evidence_type="prerequisite",
        supporting_quotes=["CSC-110 ICT 2+1"],
    )
    with pytest.raises(GroundingError, match="type of fact"):
        validate_block(block, [{**chunk, "evidence_types": ["course_credits"]}], [task])


def test_prerequisite_request_cannot_be_answered_as_a_different_claim_type():
    task = Task(
        question="prerequisite?",
        search_query="prerequisite",
        topic="curriculum",
        evidence_type="prerequisite",
    )
    block = AnswerBlock(
        text="Requires CSC-110.",
        sources=[1],
        kind="university_fact",
        evidence_type="course_credits",
        supporting_quotes=["CSC-110 ICT 2+1"],
    )
    with pytest.raises(GroundingError, match="requested evidence type"):
        validate_block(
            block, [{"content": "CSC-110 ICT 2+1", "evidence_types": ["course_credits"]}], [task]
        )


def test_false_prerequisite_cannot_hide_as_an_uncited_limitation():
    task = Task(
        question="its prerequisite?",
        search_query="CSC-104 prerequisite",
        topic="curriculum",
        evidence_type="prerequisite",
        course_codes=["CSC-104"],
    )
    block = AnswerBlock(text="CSC-104 ka prerequisite CSC-103 hai.", kind="limitation")
    with pytest.raises(GroundingError, match="unsupported course identifier"):
        validate_block(block, [], [task])


def test_unique_catalogue_alias_resolves_but_multiple_identities_stay_ambiguous():
    class Catalogue:
        candidates = [{"code": "CSC-104", "title": "Problem Solving & Programming"}]

        def course_candidates(self, task):
            return self.candidates

    index = Catalogue()
    plan = QueryUnderstanding(
        original="cs104 credits?",
        normalized="credit hours",
        language="english",
        mode="university",
        tasks=[
            Task(
                question="credits?",
                search_query="CS104 credits",
                topic="curriculum",
                course_codes=["CS104"],
            )
        ],
    )
    resolution = resolve_entities(index, plan)
    assert resolution[0]["canonical"] == "CSC-104" and plan.course_codes == ["CSC-104"]
    index.candidates.append({"code": "CS-104", "title": "A different observed course"})
    plan.tasks[0].course_codes = ["CS 104"]
    resolve_entities(index, plan)
    assert plan.course_codes == ["CS-104"]  # Exact identity takes precedence over a prefix alias.
    plan.tasks[0].course_codes = ["C104"]
    resolve_entities(index, plan)
    assert plan.course_codes == ["C104"]


def test_courses_taught_do_not_become_research_interests_or_current_assignments():
    chunk = {
        "uri": "https://cs.qau.edu.pk/faculty/test",
        "title": "Dr. Example - Faculty Profile",
        "content": "Dr. Example\nResearch Interests\nComputer Vision\nEducation\nPhD\nCourses Taught\nNatural Language Processing\nCSC-104",
        "topic": "faculty",
    }
    task = Task(
        question="NLP researchers?",
        search_query="NLP",
        topic="faculty",
        evidence_type="research_interests",
        research_area="natural language processing",
    )
    assert faculty_view(chunk, task) is None
    task.evidence_type = "teaching_assignment"
    assert typed_view(chunk, task) is None


def test_lecture_and_lab_components_are_supported_when_the_source_prints_the_sum():
    from chatbot_v3.generation import validate_paragraph

    evidence = [
        {"content": "CSC-104: Problem Solving & Programming CC 3+1", "effective_term": "Fall 2025"}
    ]
    assert validate_paragraph(
        "CSC-104 has 3 lecture credits and 1 lab credit, 4 total. [1]", evidence, "credits?"
    ) == [1]


def test_urdu_percentage_word_matches_the_same_printed_percentage():
    from chatbot_v3.generation import validate_paragraph

    evidence = [{"content": "Mathematics with minimum 50% marks", "effective_term": None}]
    assert validate_paragraph(
        "ریاضی میں کم از کم ۵۰ فیصد نمبر ضروری ہیں۔ [1]", evidence, "داخلہ؟"
    ) == [1]
    with pytest.raises(GroundingError):
        validate_paragraph("کم از کم ۶۰ فیصد نمبر ضروری ہیں۔ [1]", evidence, "داخلہ؟")


def test_model_quote_must_occur_in_the_cited_evidence():
    evidence = [
        {
            "content": "Dr. Example\nResearch Interests\nComputer Vision",
            "evidence_types": ["research_interests"],
        }
    ]
    block = AnswerBlock(
        text="Dr. Example researches NLP.",
        sources=[1],
        kind="university_fact",
        evidence_type="research_interests",
        supporting_quotes=["Natural Language Processing"],
    )
    with pytest.raises(GroundingError, match="quotation"):
        validate_block(block, evidence)


def test_structured_lookup_reaches_the_generator_and_explicit_language_is_repeated():
    plan = QueryUnderstanding(
        original="cs104 credits",
        normalized="CSC-104 credit hours",
        language="roman_urdu",
        mode="university",
    )
    messages = answer_messages(
        plan, [], [], [], [{"records": [{"course_code": "CSC-104", "total_credits": 4}]}]
    )
    assert '"total_credits": 4' in messages[-1]["content"]
    assert messages[-1]["content"].endswith(
        "Do not switch to English-only paragraphs or Urdu script."
    )

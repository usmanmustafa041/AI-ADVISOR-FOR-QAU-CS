import dataclasses

import numpy as np
import pytest
from fastapi.testclient import TestClient

from advisor.api.app import create_app
from advisor.config import Settings
from advisor.context import build_context
from advisor.ingest.model import Chunk
from advisor.rag.grounding import ground, is_unsupported_university_claim
from advisor.retrieval.bundle import Bundle
from advisor.retrieval.retriever import Retriever

NF = "I couldn't find that."
EVIDENCE = "Dr. Onaiza Maqbool is a Professor. The Network and Information Security Lab does research. Office of the Controller of Examinations receives reports."


def run(answer, student="Who supervises my project?"):
    return ground(answer, EVIDENCE, student, not_found=NF)


def test_invented_institution_sentence_is_removed_but_the_rest_survives():
    r = run("The Faculty of Computing and Informatics (FCI) does not assign supervisors. Dr. Onaiza Maqbool is a Professor [1].")
    assert "Faculty of Computing" not in r.text and "FCI" not in r.text
    assert "Onaiza Maqbool is a Professor" in r.text and r.removed


def test_entities_present_in_the_sources_are_kept():
    r = run("Submit reports to the Office of the Controller of Examinations [1].")
    assert r.removed == [] and "Controller of Examinations" in r.text


def test_invented_person_is_removed():
    r = run("Your supervisor will be Dr. Zubair Hamid [1]. Dr. Onaiza Maqbool is a Professor [1].")
    assert "Zubair" not in r.text and "Onaiza" in r.text


def test_a_name_the_student_typed_is_not_treated_as_invented():
    r = run("Dr. Tariq Mahmood is not listed as a faculty member.", student="Is Dr. Tariq Mahmood a faculty member?")
    assert r.removed == []


def test_if_nothing_supported_remains_the_honest_message_replaces_it():
    r = run("The Faculty of Computing and Informatics (FCI) does not assign supervisors.")
    assert r.replaced_all and r.text == NF


def test_uncited_generalisations_about_the_university_are_removed():
    r = run("Supervision is typically arranged between students and faculty members. Dr. Onaiza Maqbool is a Professor [1].")
    assert "typically" not in r.text and "Onaiza" in r.text
    kept = run("Supervision is typically arranged by the department [1].")
    assert kept.removed == []  # the same wording is fine when it is cited


def test_plain_ordinary_answers_pass_untouched():
    text = "The prerequisite is **Object Oriented Programming** [1]. Contact cs@qau.edu.pk."
    assert run(text).text == text and run(text).removed == []


def test_uncited_university_claims_are_unsupported_but_general_explanations_are_not():
    assert is_unsupported_university_claim("The department usually assigns a supervisor.", False, False)
    assert not is_unsupported_university_claim("The department usually assigns a supervisor [1].", True, False)
    assert not is_unsupported_university_claim("A stack is last-in first-out; a queue is first-in first-out.", False, False)
    assert not is_unsupported_university_claim("The department does not publish that.", False, True)  # honest abstention


def test_a_correct_answer_with_a_missing_citation_is_kept_if_its_facts_are_in_the_evidence():
    evidence = "CSC-211 Data Structures: Tuesday, room 201, 8:30-10:00. Thursday, room 201, 8:30-10:00. Teacher Dr. Rabeeh Abbasi."
    good = "The department holds Data Structures (CSC-211) on Tuesday in room 201 at 8:30-10:00 and Thursday in room 201."
    assert not is_unsupported_university_claim(good, False, False, evidence)
    invented = "The department holds Data Structures on Friday in room 999 at 14:15."
    assert is_unsupported_university_claim(invented, False, False, evidence)


def test_citation_variants_are_normalised():
    from advisor.rag.service import AdvisorService

    text, cited = AdvisorService._check_citations("Held Tuesday [n.2] and Thursday [Source 3] and [S1].", 3)
    assert text == "Held Tuesday [2] and Thursday [3] and [1]." and cited == {1, 2, 3}


class Hallucinator:
    name, model = "fake", "fake-1"

    async def stream(self, messages, params):
        yield "The Faculty of Computing and Informatics (FCI) at QAU does not assign supervisors. "
        yield "Supervision is typically arranged by the department based on mutual interest."

    async def complete(self, messages, params):
        return "".join([c async for c in self.stream(messages, params)])


def test_service_never_shows_the_invented_institution(tmp_path):
    rows = [dataclasses.asdict(Chunk("c0", "d0", 0, "https://cs.qau.edu.pk/x", "Doc", "page", "h", "Final Year Project is a course.", "Final Year Project is a course.", {}, 5))]
    ctx = build_context(Settings(data_dir=tmp_path, rate_limit_per_minute=1000, rate_limit_burst=1000), load_kb=False)
    bundle = Bundle(None, rows, np.zeros((1, 4), dtype=np.float32), {"build_id": "t", "chunks": 1})
    ctx.kb.bundle, ctx.kb.retriever = bundle, Retriever(bundle, None, None)
    ctx.router.candidates = lambda: [Hallucinator()]  # type: ignore[method-assign]
    with TestClient(create_app(ctx)) as client:
        r = client.post("/api/v1/chat", json={"message": "Which professor will supervise my final year project?"}).json()
    assert "Faculty of Computing" not in r["answer"] and "FCI" not in r["answer"]
    assert "couldn't find" in r["answer"].lower()


def test_invented_course_code_in_parentheses_is_stripped_but_sentence_stays():
    ev = "Data Structures (CSC-211 / CS-211) requires Object Oriented Programming (CSC-121)."
    ans = "You cannot enroll in **DSA (CS-352 / CSC-352)** until you pass PSP. DSA is CSC-211 [1]."
    out = ground(ans, ev, "I have not passed PSP", not_found="NF")
    assert "352" not in out.text
    assert "cannot enroll in **DSA**" in out.text or "cannot enroll in **DSA" in out.text
    assert "CSC-211" in out.text and out.repaired == ["CS-352", "CSC-352"]


def test_sentence_built_on_an_invented_code_is_dropped():
    ev = "Data Structures is CSC-211."
    out = ground("CSC-352 is the course you need. Data Structures is offered as CSC-211 in the scheme.", ev, "q", not_found="NF")
    assert "352" not in out.text and "CSC-211" in out.text and out.removed


def test_codes_from_trusted_addendum_count_as_evidence():
    out = ground("See CSC-352 [1].", "unrelated", "q", not_found="NF", trusted="CSC-352 is listed")
    assert "CSC-352" in out.text

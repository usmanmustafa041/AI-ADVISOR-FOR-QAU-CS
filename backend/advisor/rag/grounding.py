"""Deterministic grounding guards applied to a finished answer.

Small language models sometimes invent institutions ("the Faculty of Computing and Informatics"),
acronyms or people, or describe how "the university usually does things" from memory. These guards
need no model: they compare what the answer *names* with what the sources and the student's own
message contain.

1. **Ungrounded entities** – a sentence that names an organisation/office, a bracketed acronym or a
   titled person which appears nowhere in the evidence is dropped.
2. **Uncited university claims** – an answer that talks about the university but cites nothing is
   not allowed to stand (general computing explanations are exempt).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

ORG = re.compile(
    r"\b(?:Faculty|School|Office|Directorate|Committee|Board|Council|Centre|Center|Institute|Cell|Bureau|"
    r"Section|Unit|Wing)\s+of\s+(?:[A-Z][\w&'’-]*(?:,?\s+(?:and|of|for|&)\s+|\s+))*[A-Z][\w&'’-]*"
)
ACRONYM = re.compile(r"\(([A-Z]{3,8})\)")
# Course codes such as CSC-211 / CS-211. A model that has the right course but the wrong number must
# not be believed: the number has to occur next to a department prefix somewhere in the evidence.
COURSE_CODE = re.compile(r"\b[A-Z]{2,5}[- ]?(\d{3})[A-Z]?\b")
CODE_PAREN = re.compile(r"\s*\(([^()]{0,80})\)")
PERSON = re.compile(r"\b(?:Dr|Prof|Professor|Mr|Ms|Mrs|Engr)\.?\s+((?:[A-Z][A-Za-z.'’-]*\s?){1,4})")
# Names that are always fine to mention (the assistant's own scope).
ALLOWED_ORG = re.compile(r"computer science|quaid|qau|information science|data science", re.I)
UNIVERSITY_TERMS = re.compile(
    r"\bQAU\b|Quaid|\bdepartment\b|\buniversity\b|\bfaculty\b|\bsemester\b|\bcredit hours?\b|\bsupervisor\b|"
    r"\bchairperson\b|\badmission\b|\bregulations?\b|\bdean\b",
    re.I,
)
# Split after . ! ? but not after titles or initials ("Dr.", "Prof.", "S. M. Naqi"), so a name stays
# attached to its sentence.
# "Typically/usually …" about the university is how models describe practice from memory.
GENERALISING = re.compile(r"\b(typically|usually|generally|normally|commonly|often|in most cases|as a rule)\b", re.I)
SENTENCE = re.compile(
    r"(?<=[.!?])(?<!\bDr\.)(?<!\bMr\.)(?<!\bMs\.)(?<!\bMrs\.)(?<!\bProf\.)(?<!\bEngr\.)"
    r"(?<!\bvs\.)(?<!\be\.g\.)(?<!\bi\.e\.)(?<!\b[A-Z]\.)\s+"
)


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s&]", " ", s.lower())).strip()


@dataclass
class GroundingResult:
    text: str
    removed: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    replaced_all: bool = False
    repaired: list[str] = field(default_factory=list)  # invented course codes stripped from a sentence that stays


def _known_code_numbers(evidence_cs: str) -> set[str]:
    """Any three-digit number the evidence contains (generous on purpose: "BS 130" must not be mistaken for a code)."""
    return set(re.findall(r"(?<!\d)(\d{3})(?!\d)", evidence_cs))


def _fix_codes(sentence: str, known: set[str]) -> tuple[str, list[str], bool]:
    """Strip course codes the sources never mention.

    Returns (sentence, invented codes, still_ungrounded). A parenthesis made only of invented codes
    ("DSA (CS-352 / CSC-352)") is removed and the sentence stays; any other use of an invented code
    means the sentence cannot be trusted.
    """
    invented: list[str] = []

    def paren(m: re.Match) -> str:
        inner = m.group(1)
        codes = list(COURSE_CODE.finditer(inner))
        if codes and all(c.group(1) not in known for c in codes) and not re.sub(COURSE_CODE, "", inner).strip(" /,;-"):
            invented.extend(c.group(0) for c in codes)
            return ""
        return m.group(0)

    fixed = CODE_PAREN.sub(paren, sentence)
    leftover = [m.group(0) for m in COURSE_CODE.finditer(fixed) if m.group(1) not in known]
    return fixed, invented + leftover, bool(leftover)


def _ungrounded(sentence: str, evidence: str, evidence_cs: str) -> list[str]:
    bad: list[str] = []
    for m in ORG.finditer(sentence):
        phrase = m.group(0).strip(" ,")
        if ALLOWED_ORG.search(phrase):
            continue
        if _norm(phrase) not in evidence:
            bad.append(phrase)
    for m in ACRONYM.finditer(sentence):
        if m.group(1) not in evidence_cs and m.group(1) not in {"QAU", "NCEAC", "HEC", "CGPA", "GPA"}:
            bad.append(m.group(0))
    for m in PERSON.finditer(sentence):
        tokens = [t.strip(".") for t in m.group(1).split() if len(t.strip(".")) >= 3]
        if tokens and not any(_norm(t) in evidence for t in tokens):
            bad.append(m.group(0).strip())
    return bad


def ground(answer: str, evidence_text: str, student_text: str, *, not_found: str, trusted: str = "") -> GroundingResult:
    """Return the answer with unsupported sentences removed (or replaced by ``not_found``).

    ``trusted`` is text produced by our own code (e.g. the computed prerequisite addendum); it counts
    as evidence for course codes.
    """
    evidence = _norm(evidence_text + " " + student_text)
    evidence_cs = evidence_text + " " + student_text
    known = _known_code_numbers(evidence_cs + " " + trusted)
    kept: list[str] = []
    removed: list[str] = []
    reasons: list[str] = []
    repaired: list[str] = []
    for part in re.split(r"(\n+)", answer):
        if part.strip() == "":
            kept.append(part)
            continue
        pieces = SENTENCE.split(part)
        good = []
        for sent in pieces:
            sent, invented, code_fatal = _fix_codes(sent, known)
            if invented and not code_fatal:
                repaired.extend(invented)
            bad = _ungrounded(sent, evidence, evidence_cs)
            if code_fatal:
                bad.append("course code not in the sources: " + ", ".join(invented))
            if not bad and GENERALISING.search(sent) and UNIVERSITY_TERMS.search(sent) and not re.search(r"\[\d+\]", sent):
                bad = ["uncited generalisation about how the university works"]
            if bad:
                removed.append(sent)
                reasons.append("names not found in the sources: " + "; ".join(bad))
            else:
                good.append(sent)
        if good:
            kept.append(" ".join(good))
    text = re.sub(r"\n{3,}", "\n\n", "".join(kept)).strip()
    if removed and len(re.sub(r"\W", "", text)) < 15:
        return GroundingResult(not_found, removed, reasons, replaced_all=True, repaired=repaired)
    return GroundingResult(text, removed, reasons, repaired=repaired)


SPECIFIC = re.compile(
    r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+|\b[A-Z]{2,5}-\d[0-9A-Za-z]{1,4}\b|\b\d[\d:,./-]*\d\b|\b\d\b|"
    r"(?<![.!?]\s)(?<!^)\b[A-Z][a-z]{3,}\b"
)
COMMON = {"quaid", "azam", "computer", "sciences", "science", "department", "university", "islamabad", "programme",
          "program", "course", "semester", "students", "student", "faculty", "regular", "morning", "evening",
          "self", "support", "yes", "note", "please", "however", "these", "this", "that", "contact", "office"}


def support_ratio(answer: str, evidence_text: str) -> tuple[float, int]:
    """Share of the answer's specific facts (numbers, codes, emails, proper names) found in the evidence."""
    evidence = _norm(evidence_text)
    tokens = [t for t in SPECIFIC.findall(re.sub(r"\[[^\]]*\]", " ", answer)) if _norm(t) not in COMMON]
    if not tokens:
        return 0.0, 0
    hits = sum(1 for t in tokens if _norm(t) and _norm(t) in evidence)
    return hits / len(tokens), len(tokens)


def is_unsupported_university_claim(
    answer: str, has_citation: bool, abstained: bool, evidence_text: str = ""
) -> bool:
    """True for an uncited answer about the university whose specifics the evidence does not back.

    A correct answer with a malformed or missing citation is kept (its facts are in the evidence);
    prose with no checkable specifics, or with specifics the sources do not contain, is rejected.
    """
    if has_citation or abstained or not UNIVERSITY_TERMS.search(answer):
        return False
    ratio, n = support_ratio(answer, evidence_text)
    return n < 3 or ratio < 0.7

"""Deterministic query planning. Conversation state selects scope, never facts."""

import re
from dataclasses import asdict, dataclass

from app.nlp.entities import extract_entities
from app.nlp.language import detect_language
from app.rag.evidence import normalize_query, query_programs
from app.response.conversation import conversational_reply

REFERENCE = re.compile(
    r"\b(it|its|this|that|their|them|those|iska|iski|uska|unke|same)\b|"
    r"^(and|what about|aur)\b|اس (?:کی|کا|کے)|ان (?:کی|کا|کے)|^اور",
    re.I,
)
TERM = re.compile(r"\b(Fall|Spring|Summer)\s*[- ]?\s*(20\d{2})\b", re.I)
PROGRAM_LABELS = {
    "bs": "BS Computer Science",
    "mphil": "MPhil Computer Science",
    "phd": "PhD Computer Science",
    "ms-ds": "MS Data Science",
    "ms-ist": "MS IST",
}


@dataclass
class QueryPlan:
    original: str
    rewritten: str
    language: str
    intent: str
    entities: dict
    scope: dict
    subquestions: list[str]
    stages: tuple = (
        "language",
        "intent",
        "entities",
        "conversation_scope",
        "rewrite",
        "structured_lookup",
        "hybrid_retrieval",
        "rerank",
        "verify",
        "generate",
    )

    def trace(self):
        # Trace includes no previous conversation transcript.
        return asdict(self)


def plan_query(message, history=(), course=None, language=None):
    normalized = normalize_query(message)
    explicit = query_programs(normalized)
    term = TERM.search(message)
    scope = {}
    previous = [
        h["content"]
        for h in history
        if h["role"] == "user" and conversational_reply(h["content"], "english") is None
    ][-4:]
    reference = bool(previous) or bool(REFERENCE.search(message))
    operational = bool(
        re.search(r"fee|tuition|timetable|schedule|deadline|admission|داخلہ|فیس", normalized)
    )
    if reference:
        for prior in reversed(previous):
            programs = query_programs(normalize_query(prior))
            if programs:
                scope["programs"] = sorted(programs)
                break
        for prior in reversed(previous):
            if (
                query_programs(normalize_query(prior))
                and explicit
                and not (query_programs(normalize_query(prior)) & explicit)
            ):
                break
            prior_term = TERM.search(prior)
            prior_operational = bool(
                re.search(
                    r"fee|tuition|timetable|schedule|deadline|admission|داخلہ|فیس",
                    normalize_query(prior),
                )
            )
            if prior_term and not operational and not prior_operational:
                scope["term"] = f"{prior_term[1].title()} {prior_term[2]}"
                break
    if explicit:
        scope["programs"] = sorted(explicit)
    if term:
        scope["term"] = f"{term[1].title()} {term[2]}"
    entities = extract_entities(message)
    codes = re.findall(r"\b[A-Za-z]{2,4}[ -]?\d{3}\b", message)
    if codes:
        scope["course"] = re.sub(r"[ -]?([0-9]{3})$", r"-\1", codes[-1].upper())
    elif reference and not operational and not explicit:
        for prior in reversed(previous):
            codes = re.findall(r"\b[A-Za-z]{2,4}[ -]?\d{3}\b", prior)
            if codes:
                scope["course"] = re.sub(r"[ -]?([0-9]{3})$", r"-\1", codes[-1].upper())
                break
        if course and not scope.get("course"):
            scope["course"] = course.upper()
    rewritten = message
    if REFERENCE.search(message) and previous and not operational:
        rewritten = previous[-1][-500:] + "\nFollow-up: " + message
    context = []
    if not explicit and scope.get("programs"):
        context.append("Programme: " + ", ".join(PROGRAM_LABELS[p] for p in scope["programs"]))
    if not term and scope.get("term"):
        context.append("Admission batch: " + scope["term"])
    if scope.get("course") and scope["course"].lower() not in rewritten.lower():
        context.append("Course: " + scope["course"])
    if scope.get("course"):
        entities["course_code"] = [scope["course"]]
    if context:
        rewritten += "\n" + "\n".join(context)
    intent = "academic_question"
    for name, pattern in (
        ("calculation", r"\bgpa\b|\bcgpa\b|calculate|حساب"),
        ("course_prerequisite", r"prereq|pre.?req|شرط|pehle.*course"),
        ("fees", r"fee|tuition|فیس"),
        ("timetable", r"timetable|schedule|شیڈول"),
        ("admissions", r"admission|dakhla|داخلہ"),
        ("faculty", r"faculty|professor|استاد|research interest"),
        ("curriculum", r"scheme|curriculum|credit|نصاب"),
    ):
        if re.search(pattern, normalized, re.I):
            intent = name
            break
    # Split independent interrogative clauses only; preserve prerequisite AND/OR wording.
    parts = re.split(
        r"[?؟;]\s*|\b(?:and|aur)\s+(?=what|how|when|who|which|kya|kitn)"
        r"|اور\s+(?=کیا|کتن|کب|کون)",
        message,
        flags=re.I,
    )
    parts = [p.strip() for p in parts if p.strip() and conversational_reply(p, "english") is None][
        :3
    ]
    subquestions = []
    for part in parts:
        part_context = []
        if scope.get("programs") and not query_programs(normalize_query(part)):
            part_context.append(
                "Programme: " + ", ".join(PROGRAM_LABELS[p] for p in scope["programs"])
            )
        if scope.get("term") and not TERM.search(part):
            part_context.append("Admission batch: " + scope["term"])
        subquestions.append(part + ("\n" + "\n".join(part_context) if part_context else ""))
    return QueryPlan(
        message,
        rewritten,
        language or detect_language(message),
        intent,
        entities,
        scope,
        subquestions or [rewritten],
    )

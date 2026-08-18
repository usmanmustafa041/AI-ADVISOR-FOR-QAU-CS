import re

from app.nlp.classifier import get_classifier
from app.nlp.entities import extract_entities
from app.nlp.language import detect_language


def _has(pattern: str, text: str) -> bool:
    return bool(re.search(pattern, text, re.I))


def analyze_query(text: str) -> dict:
    normalized = " ".join(text.strip().split())
    if not normalized:
        raise ValueError("Query cannot be empty")
    classifier = get_classifier()
    intent, confidence = classifier.predict(normalized)
    entities = extract_entities(normalized)
    language = detect_language(normalized)

    # Explicit academic vocabulary is safer than accepting an unrelated,
    # low-confidence statistical prediction. These rules cover the document's
    # English, Roman Urdu, and Urdu-script acceptance examples.
    routes = [
        (r"\bpre[- ]?requisites?\b|پری.?ریکوزٹ|لازمی کورس", "course_prerequisite", 0.90),
        (r"\bfees?\b|فیس", "fee_information", 0.95),
        (r"\btime\s*table\b|ٹائم\s*ٹیبل|کلاس.*(?:کب|وقت)", "timetable_query", 0.90),
        (r"\bexam(?:ination)?s?\b|date\s*sheet|امتحان|ڈیٹ\s*شیٹ", "exam_schedule", 0.90),
        (r"\bregistration\b.*\b(last|deadline|close|date)\b|رجسٹریشن.*(?:آخری|تاریخ)", "registration_deadline", 0.90),
        (r"\b(?:how|procedure|process|tareeqa|kaise)\b.*\bregister|\bregistration procedure\b|رجسٹریشن.*(?:کیسے|طریقہ)", "registration_process", 0.90),
        (r"\bexempt(?:ion|ed)?\b|معافی|استثنی", "course_exemption", 0.90),
        (r"\b(?:degree|graduation) requirements?\b|ڈگری.*شرائط", "degree_requirement", 0.90),
        (r"\bprobation\b|academic warning|پروبیشن", "probation_rule", 0.90),
        (r"\b(?:gpa|cgpa)\b", "gpa_requirement", 0.90),
        (r"\battendance\b|\bpolic(?:y|ies)\b|\brules?\b|حاضری|پالیسی|قواعد", "policy_information", 0.90),
        (r"\b(?:thesis|fyp|final year project|research)\b|تھیسس|تحقیق", "thesis_information", 0.90),
        (r"\b(?:program|programme|bscs|mphil|phd)\b.*\b(?:information|duration|semesters?)\b", "program_information", 0.85),
        (r"\bsemester planning\b|\bwhich semester\b|سمسٹر.*منصوب", "semester_information", 0.85),
    ]
    for pattern, routed_intent, minimum in routes:
        if _has(pattern, normalized):
            intent, confidence = routed_intent, max(confidence, minimum)
            break

    # UC3/UC4/UC10 require clarification rather than a confident-looking wrong answer.
    if confidence < 0.55:
        intent = "fallback"

    return {
        "text": normalized,
        "language": language,
        "intent": intent,
        "confidence": round(confidence, 4),
        "entities": entities,
        "model_backend": classifier.backend,
        "model_name": classifier.model_name,
    }

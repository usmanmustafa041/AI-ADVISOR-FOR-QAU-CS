"""Minimize opt-in diagnostics; owner history remains a separate authenticated feature."""

import re

FREE_TEXT = {
    "original",
    "normalized",
    "question",
    "search_query",
    "answer",
    "clarification_question",
    "followup_question",
}
PERSONAL = re.compile(
    r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}|\b\d{5}-\d{7}-\d\b|"
    r"(?<!\w)(?:\+92[-\s]?|0)3\d{2}[-\s]?\d{7}(?!\w)|\b\d{10,}\b"
)


def diagnostic_copy(value, *, private=False, key=""):
    if isinstance(value, dict):
        return {k: diagnostic_copy(v, private=private, key=k) for k, v in value.items()}
    if isinstance(value, list):
        if private and key == "person_names":
            return ["[redacted]"] if value else []
        return [diagnostic_copy(v, private=private, key=key) for v in value]
    if isinstance(value, str) and key in FREE_TEXT:
        return "[redacted private text]" if private else PERSONAL.sub("[redacted]", value)
    return value

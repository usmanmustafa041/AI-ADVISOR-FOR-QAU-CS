"""Last-resort answerer used when no language model is reachable.

It never invents text: it returns the most relevant passages verbatim, with sources, so a
student still gets the facts (and the exact wording) even during a model outage.
"""

from __future__ import annotations

import re


def extractive_answer(question: str, passages: list[dict], limit: int = 3) -> str:
    if not passages:
        return ""
    q_terms = {t for t in re.findall(r"[a-z0-9]{3,}", question.lower())}
    parts = ["The AI assistant is temporarily unavailable, so here are the most relevant passages from the department's official pages:"]
    for i, p in enumerate(passages[:limit], 1):
        text = re.sub(r"\s+", " ", p["text"]).strip()
        if len(text) > 700:
            sentences = re.split(r"(?<=[.!?])\s+", text)
            scored = sorted(
                range(len(sentences)),
                key=lambda j: -len(q_terms & set(re.findall(r"[a-z0-9]{3,}", sentences[j].lower()))),
            )[:4]
            text = " ".join(sentences[j] for j in sorted(scored))[:700]
        parts.append(f"**[{i}] {p['title']}**\n{text}")
    return "\n\n".join(parts)

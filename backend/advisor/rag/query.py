"""Question preparation: follow-up resolution without an LLM (fallback) and intent hints."""

from __future__ import annotations

import re

FOLLOWUP = re.compile(
    r"\b(it|its|that|this|they|them|their|his|her|he|she|those|these|there|same)\b|^(and|also|what about|how about|then|ok)\b",
    re.I,
)
SMALLTALK = re.compile(
    r"^\s*(hi+|hello+|hey+|salam|assalam[\w\s-]*|aoa|good (morning|evening|afternoon|night)|bye|goodbye|see you|"
    r"who are you\??|what are you\??|what can you do\??|what do you do\??|help( me)?|(what is|what's|whats) your name\??|"
    r"your name\??|introduce yourself|tell me about yourself|who (made|created|built|developed) you\??|"
    r"آپ کون ہیں\??)\W*$",
    re.I,
)
THANKS_RE = re.compile(
    r"^\s*(thanks?( you)?( (so|very))?( much| a lot)?|thank you( so| very)?( much| a lot)?|thx|ty|shukriya|shukria|jazak\w*|"
    r"bohat shukriya|شکریہ)(\s+(bro|buddy|man|yaar|advisor))?\W*$",
    re.I,
)
HOW_ARE_YOU = re.compile(
    r"^\s*((hi+|hello+|hey+|salam|assalam[\w\s-]*)[\s,!.]*)?"
    r"(how\s+(are|r)\s+(you|u|ya)(\s+doing)?(\s+today)?|how(['’]?s|\s+is)\s+it\s+going|how\s+do\s+you\s+do|"
    r"what['’]?s\s+up|whats\s+up|wassup|sup|kaise\s+ho|kaisay\s+ho|kese\s+ho|kaisy\s+ho|aap\s+kaise\s+hain?|"
    r"(kya|kia)\s+haal\s+(hai|he|chaal)|haal\s+chaal|آپ\s+کیسے\s+ہیں|کیسے\s+ہیں|کیا\s+حال(\s+ہے)?)"
    r"(\s+(bro|buddy|there|sir|madam|mam|advisor|bot|yaar|dost|today))?\W*$",
    re.I,
)
ACK = re.compile(
    r"^\s*(ok(ay)?|okk+|cool|nice|great|good|fine|awesome|perfect|got it|i see|alright|well done|good job|nice work|great job|"
    r"you(['’]?re| are) (great|good|awesome|helpful|smart|amazing|the best)|i(['’]?m| am) (fine|good|ok(ay)?|great|well)|"
    r"theek hai|thik hai|acha|achha|shabash|zabardast|ٹھیک ہے|اچھا)(\s+(bro|buddy|man|yaar|advisor))?\W*$",
    re.I,
)
# Words that mean a question is about the department or studying; anything short without them is conversation.
DOMAIN = re.compile(
    r"course|class|fee|semester|credit|admission|admit|exam|faculty|prof|teach|dr\b|dean|chair|hod|department|scheme|"
    r"time\s?table|schedule|deadline|scholarship|degree|\bbs\b|\bms\b|phd|mphil|cgpa|gpa|attendance|thesis|fyp|project|lab\b|"
    r"hostel|prereq|syllabus|result|merit|seat|campus|qau|quaid|\bcs\b|csc|office|contact|email|phone|calendar|event|research|"
    r"supervisor|policy|rule|register|enrol|section|grade|marks|notice|form|degree|subject|program|library|transport|"
    r"فیس|داخلہ|کورس|امتحان|سمسٹر",
    re.I,
)


def smalltalk_kind(q: str) -> str | None:
    """'how' (how are you), 'thanks', 'ack' (ok / great), 'hello' (greeting, who are you, help) or None."""
    q = q.strip()
    if HOW_ARE_YOU.match(q):
        return "how"
    if THANKS_RE.match(q):
        return "thanks"
    if ACK.match(q) and not SMALLTALK.match(q):
        return "ack"
    if SMALLTALK.match(q):
        return "hello"
    return None


def is_smalltalk(q: str) -> bool:
    return smalltalk_kind(q) is not None


def is_conversational(q: str) -> bool:
    """A short message with nothing academic in it (so an uncited reply is chit-chat, not a university claim)."""
    q = q.strip()
    return len(q.split()) <= 7 and not DOMAIN.search(q) and not re.search(r"\d", q)


def rule_contextualize(question: str, history: list[tuple[str, str]]) -> str:
    """Cheap follow-up resolution: prepend the previous user question when the new one
    is short or leans on pronouns. The LLM rewriter replaces this when a model is available."""
    prev = [t for role, t in history if role == "user"]
    if not prev:
        return question
    words = question.split()
    if len(words) <= 9 or FOLLOWUP.search(question):
        return f"{prev[-1]} {question}"
    return question

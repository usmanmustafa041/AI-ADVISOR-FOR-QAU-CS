"""Tokenisation, code normalisation and language detection shared by indexing and querying."""

from __future__ import annotations

import re

STOPWORDS = frozenset(
    """a an the of in on at to for from by with and or is are was were be been being it its this that
    these those as do does did can could should would will shall may might what which who whom whose
    when where why how i me my we our you your he she they them their there here about into than then
    so if but not no any all some tell please give show list me kindly hai hain ka ki ke ko se mein
    main kya kab kahan kaun kitna kitni kitne hota hoti hotay hay ho""".split()
)

CODE_RE = re.compile(r"\b([A-Za-z]{2,5})[-\s_]?(\d{3}[A-Za-z]?|\d[xX]{2}|\d{2}[xX])\b")
TOKEN_RE = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*", re.I)
URDU_RE = re.compile(r"[؀-ۿ]")
ROMAN_URDU_HINTS = frozenset(
    """kya hai hain kab kahan kaun kitna kitni kitne mujhe mera meri hum ap aap batao bataiye
    chahiye karna karni krna ka ki ke ko se mein main nahi nahin hota hoti lagta""".split()
)


def stem(tok: str) -> str:
    if len(tok) <= 4 or tok.isdigit() or any(c.isdigit() for c in tok):
        return tok
    for suf, rep in (("ies", "y"), ("sses", "ss"), ("ing", ""), ("ed", ""), ("es", ""), ("s", "")):
        if tok.endswith(suf) and len(tok) - len(suf) >= 3 and not tok.endswith("ss"):
            return tok[: len(tok) - len(suf)] + rep
    return tok


def norm_code(prefix: str, number: str) -> str:
    """CS-211 and CSC-211 are the same course across the site's naming generations."""
    prefix = prefix.upper()
    if prefix == "CS":
        prefix = "CSC"
    return f"{prefix}-{number.upper()}"


def extract_codes(text: str) -> list[str]:
    out = []
    for prefix, number in CODE_RE.findall(text):
        if prefix.upper() in {"SEM", "ROOM", "TOP"}:
            continue
        out.append(norm_code(prefix, number))
    return list(dict.fromkeys(out))


def tokenize(text: str, *, drop_stop: bool = True) -> list[str]:
    toks: list[str] = []
    for raw in TOKEN_RE.findall(text.lower()):
        parts = raw.split("-")
        if len(parts) > 1:
            toks.append(norm_code(parts[0], parts[1]).lower() if parts[1][:1].isdigit() else raw)
            parts_iter = parts
        else:
            parts_iter = [raw]
        for p in parts_iter:
            if drop_stop and p in STOPWORDS:
                continue
            toks.append(stem(p))
    # compact forms such as "csc211" / "cs 211"
    for prefix, number in CODE_RE.findall(text):
        toks.append(norm_code(prefix, number).lower())
    return toks


def detect_language(text: str) -> str:
    """'ur' (Urdu script), 'roman-ur' (Urdu in Latin script), or 'en'."""
    letters = [c for c in text if c.isalpha()]
    if letters and sum(1 for c in letters if URDU_RE.match(c)) / len(letters) > 0.3:
        return "ur"
    words = re.findall(r"[a-z]+", text.lower())
    if len(words) >= 2 and sum(w in ROMAN_URDU_HINTS for w in words) >= 2:
        return "roman-ur"
    return "en"


# Student wording -> wording used by the department's pages and regulations. Applied to the
# *lexical* query only (dense retrieval already generalises); each entry appends, never replaces.
SYNONYMS: list[tuple[str, str]] = [
    (r"\b(start|starts|starting|begin|begins|beginning)\b", "commence commences commencement"),
    (r"\b(end|ends|ending|finish)\b", "ends conclude"),
    (r"\b(final|finals|final exams?)\b", "terminal examination exams"),
    (r"\b(mid ?terms?|mids?)\b", "sessional mid-term"),
    (r"\b(exam|exams)\b", "examination"),
    (r"\b(deadline|last day)\b", "last date"),
    (r"\b(hod|head of (the )?department|chairman|chair)\b", "chairperson"),
    (r"\b(teacher|teachers|sir|madam|lecturer|instructor)\b", "faculty instructor taught"),
    (r"\b(subject|subjects)\b", "course courses"),
    (r"\b(pre ?req|pre-?requisites?|prereqs?)\b", "prerequisites"),
    (r"\b(cgpa|gpa)\b", "grade point average cgpa"),
    (r"\b(freeze|freezing|defer|deferment)\b", "freezing semester"),
    (r"\b(drop|withdraw)\b", "dropping change courses"),
    (r"\b(fail|failed|failing)\b", "repeat probation"),
    (r"\b(credit hours?|cr\.? ?hrs?|credits)\b", "credit hours"),
    (r"\b(fees?|tuition)\b", "fee structure dues"),
    (r"\b(apply|applying|application)\b", "admission apply online"),
    (r"\b(eligib\w+|requirements?|qualif\w+)\b", "eligibility minimum admission requirements"),
    (r"\b(phone|call|number)\b", "phone contact"),
    (r"\b(mail|email|e-mail)\b", "email"),
    (r"\b(office|room|sit|sits|sitting)\b", "office room"),
    (r"\b(timetable|time ?table|schedule)\b", "timetable schedule"),
    (r"\b(bscs|bs cs|bs\s*\(?cs\)?|undergrad\w*)\b", "BS Computer Science"),
    (r"\b(mphil|m\.phil)\b", "MPhil"),
    (r"\b(ms ?ds|data science masters?)\b", "MS Data Science"),
    (r"\b(ist)\b", "Information Science Technology"),
    (r"\b(ai)\b", "Artificial Intelligence"),
    (r"\b(ml)\b", "Machine Learning"),
    (r"\b(nlp)\b", "Natural Language Processing"),
    (r"\b(os)\b", "Operating Systems"),
    (r"\b(dbs|dbms|database)\b", "Database Systems"),
    (r"\b(oop)\b", "Object Oriented Programming"),
    (r"\b(ds)\b", "Data Structures"),
    (r"\b(hci)\b", "Human Computer Interaction"),
    (r"\b(fyp|final year project)\b", "Final Year Project"),
    (r"\b(coa|coal)\b", "Computer Organization Assembly Language"),
]


ORDINALS = {"first": 1, "1st": 1, "second": 2, "2nd": 2, "third": 3, "3rd": 3, "fourth": 4, "4th": 4,
            "fifth": 5, "5th": 5, "sixth": 6, "6th": 6, "seventh": 7, "7th": 7, "eighth": 8, "8th": 8,
            "final": 8, "last": 8}
ROMAN_SEM = {"i": 1, "ii": 2, "iii": 3, "iv": 4, "v": 5, "vi": 6, "vii": 7, "viii": 8}


def expand_query(query: str) -> str:
    extra = []
    for m in re.finditer(r"\b(first|second|third|fourth|fifth|sixth|seventh|eighth|[1-8](?:st|nd|rd|th))\s+(?:semester|sem)\b", query, re.I):
        extra.append(f"semester {ORDINALS[m.group(1).lower()]}")
    for m in re.finditer(r"\b(?:semester|sem)\s+(one|two|three|four|five|six|seven|eight|viii|vii|vi|iv|v|iii|ii|i)\b", query, re.I):
        w = m.group(1).lower()
        words = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
        extra.append(f"semester {words.get(w) or ROMAN_SEM[w]}")
    for pat, add in SYNONYMS:
        if re.search(pat, query, re.I):
            extra.append(add)
    return f"{query} {' '.join(extra)}" if extra else query

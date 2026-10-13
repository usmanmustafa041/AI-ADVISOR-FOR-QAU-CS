"""Read narrowly identified rules verbatim; values always come from evidence.

Unrecognized wording falls back to grounded generation. This does not establish
current applicability or personal eligibility and never infers prerequisites.
"""

import re

from app.rag.corpus import is_official_url
from app.rag.evidence import normalize_query, query_programs
from app.response.grounded import GroundedAnswer, evidence_notices


def policy_excerpt_answer(query, hits, language):
    question = normalize_query(query)
    if query_programs(question) != {"bs"}:
        return None
    pattern = None
    if re.search(r"probation", question):
        pattern = (
            r"A student shall be allowed [^\n]+chances[^\n]+probation[^\n]*"
            if re.search(r"chance|kitne|how many|مواقع", question)
            else r"Whenever[^\n]+CGPA[^\n]+placed on probation[^\n]*"
        )
    elif re.search(r"drop|اخراج", question) and re.search(r"cgpa|grade point", question):
        pattern = r"If a student scores[^\n]+shall be dropped[^\n]*"
    elif re.search(r"attendance|حاضری", question):
        pattern = r"A student must have attended at least [^\n]+terminal[^\n]*"
    elif re.search(r"exempt|transfer", question):
        if re.search(r"fee|cost|tuition", question):
            pattern = r"[^\n]*Rs\.\s*[\d,]+[^\n]+per course[^\n]*"
        elif re.search(r"grade|minimum", question):
            pattern = r"Only the courses with at least[^\n]+exempted[^\n]*"
        elif re.search(r"maximum|kitne|how many", question):
            pattern = r"The maximum exemption[^\n]+credit hours[^\n]*"
        elif re.search(r"gpa|grade point", question):
            pattern = r"GPA and CGPA will be computed[^\n]+QAU only[^\n]*"
    elif re.search(r"freez|frozen|freeze", question):
        if re.search(r"refund|deduct|واپسی|کٹوتی", question):
            pattern = r"[^\n]*University shall deduct[^\n]+reimbursed[^\n]*"
        elif re.search(r"application|period|days|din|درخواست", question):
            pattern = r"The application must be submitted within[^\n]+commencement of classes[^\n]*"
        else:
            pattern = r"A student shall be allowed to apply for freezing[^\n]+semesters[^\n]*"
    elif re.search(r"maximum", question) and re.search(r"complet|duration|muddat|مدت", question):
        pattern = r"A student shall have to complete the BS Programme within[^\n]*"
    elif re.search(r"registration", question) and re.search(r"dues|paid|pay|واجبات", question):
        pattern = r"Registration shall be allowed if[^\n]+paid all[^\n]*"
    elif re.search(r"credit", question) and re.search(r"usual|normal|load|بوجھ|عام", question):
        if not re.search(r"maximum|allowed|can i", question):
            pattern = (
                r"A student is required to take[^\n]+credit hours coursework "
                r"per regular semester[^\n]*"
            )
    elif re.search(r"\d+\s*\+\s*\d+", question) and re.search(r"credit", question):
        pattern = r"For a course that includes both theory[^\n]+T\s*\+\s*P[^\n]*"
    elif re.search(r"semester", question) and re.search(
        r"week|duration|teaching|how long", question
    ):
        pattern = r"Each regular semester shall be spread over[^\n]*"
    elif re.search(r"duration|muddat|how long", question) and not re.search(
        r"maximum|minimum", question
    ):
        pattern = r"The programs leading to BS shall be of[^\n]+duration[^\n]*"
    if not pattern:
        return None
    candidates = []
    for hit in hits:
        chunk = hit.chunk
        if chunk.category != "academic_policy" or not is_official_url(chunk.source_url):
            continue
        if re.search(r"\b20\d{2}\b", question) and not chunk.effective_term:
            continue
        if ("lateral" in question) != ("lateral" in chunk.title.lower()):
            continue
        if not re.search(r"BS (?:Program|Lateral)", chunk.title, re.I):
            continue
        match = re.search(pattern, chunk.content, re.I)
        if match and len(match[0]) <= 1200:
            candidates.append((hit, match[0].strip()))
    if not candidates or len({quote for _, quote in candidates}) != 1:
        return None
    hit, quote = candidates[0]
    scope = "BS Lateral Entry" if "lateral" in question else "BS Morning/Evening"
    prefix = {
        "english": f"Archived {scope} rule (published wording):",
        "roman_urdu": f"Archived {scope} rule ke asal alfaaz:",
        "urdu": f"محفوظ شدہ {scope} قواعد کے اصل الفاظ:",
    }.get(language, f"Archived {scope} rule:")
    return GroundedAnswer(
        prefix + "\n\n" + quote + " [1]",
        [{**hit.citation(1), "quotes": [quote]}],
        engine="rag",
        grounding_status="cited_lookup",
        notices=evidence_notices([hit]),
        model="source-rule",
    )

"""Source-driven procedure tool output. No question-specific answers or inferred steps.

Navigation and course outcomes have weaker capabilities than an instruction. Keep
that distinction in the final answer even when the generator ignores its prompt.
"""

import re
from urllib.parse import urlsplit

from chatbot_v3.generation import AnswerBlock


def procedure_blocks(plan, evidence):
    tasks = [t for t in plan.tasks if t.topic != "general"]
    if plan.mode != "university" or not tasks or any(t.topic != "procedures" for t in tasks):
        return None
    language = plan.language
    labels = {
        "english": {
            "resource": "Published official resource",
            "course_description": "Published course information (deliverables, not submission instructions)",
            "procedure": "Published instructions",
            "service_contact": "Published department contact for inquiries (not a verified submission destination)",
            "gap": "I found the information below, but could not verify the complete submission procedure, required attachments/signatures or submission destination. A form title or course description does not establish those requirements or permission to apply a rule to your case.",
            "empty": "I could not verify a relevant official form or submission procedure from the available sources.",
        },
        "roman_urdu": {
            "resource": "Yeh published official resource hai",
            "course_description": "Course mein yeh deliverables likhe hain; yeh submission ka tareeqa nahi hai",
            "procedure": "Source mein yeh instructions likhi hain",
            "service_contact": "Sawal poochne ke liye department ka published contact; yahan submission ki tasdeeq nahi hui",
            "gap": "Neeche ki maloomat mil gayi hai, lekin mukammal submission ka tareeqa, attachments/signatures aur jama karane ki jagah verify nahi hui. Sirf form ke naam ya course description se yeh requirements ya aap ke case par rule lagne ki ijazat sabit nahi hoti.",
            "empty": "Available sources se relevant official form ya submission ka tareeqa verify nahi ho saka.",
        },
        "urdu": {
            "resource": "شائع شدہ سرکاری ماخذ",
            "course_description": "کورس میں درج کام؛ یہ جمع کرانے کی ہدایات نہیں ہیں",
            "procedure": "ماخذ میں شائع شدہ ہدایات",
            "service_contact": "سوال پوچھنے کے لیے شعبے کا شائع شدہ رابطہ؛ یہاں جمع کرانے کی تصدیق نہیں ہوئی",
            "gap": "ذیل کی معلومات مل گئی ہیں، لیکن جمع کرانے کا مکمل طریقہ، ضروری منسلکات، دستخط اور جمع کرانے کی جگہ کی تصدیق نہیں ہوئی۔ صرف فارم کے نام یا کورس کی تفصیل سے یہ شرائط یا آپ کے معاملے پر کسی ضابطے کے اطلاق کی اجازت ثابت نہیں ہوتی۔",
            "empty": "دستیاب ماخذ سے متعلقہ سرکاری فارم یا جمع کرانے کے طریقے کی تصدیق نہیں ہو سکی۔",
        },
    }[language]
    facts, seen, counts = [], set(), {}
    for n, source in enumerate(evidence, 1):
        types = source.get("evidence_types", [])
        kind = next(
            (
                k
                for k in ("procedure", "course_description", "resource", "service_contact")
                if k in types
            ),
            None,
        )
        if (
            not kind
            or counts.get(kind, 0)
            >= {"procedure": 3, "course_description": 2, "resource": 3, "service_contact": 1}[kind]
        ):
            continue
        if kind == "resource":
            # A generic index URL does not identify a form. Keep the printed
            # section's real asset links; never manufacture a download address.
            links = source.get("resources", [])
            links = [
                r
                for r in links
                if urlsplit(r["url"]).path
                not in {"/", "/examinations-download/", "/download-category/examinations/"}
            ]
            if not links:
                continue
            names = list(
                dict.fromkeys(
                    r["title"].removesuffix(" — Download").removesuffix(" – QAU") for r in links
                )
            )
            body = "; ".join(names)
            identity = (kind, re.sub(r"\W+", " ", body.lower()).strip())
        elif kind == "course_description":
            # Quote the printed Contents field instead of turning deliverables
            # into invented administrative steps. A future course may lack it.
            match = re.search(r"(?:^|\n)Contents:\s*\n?(.*)", source["content"], re.S | re.I)
            body = match[1].strip() if match else source["content"].strip()
            identity = (kind, " ".join(body.split()).lower())
        else:
            body = source["content"].strip()
            identity = (kind, " ".join(body.split()).lower())
        if not body or identity in seen:
            continue
        seen.add(identity)
        counts[kind] = counts.get(kind, 0) + 1
        facts.append(
            AnswerBlock(
                text=f"{labels[kind]}:\n{body}",
                sources=[n],
                kind="university_fact",
                evidence_type=kind,
            )
        )
    asks_for_process = any(t.evidence_type == "procedure" or t.high_stakes for t in tasks)
    substantive = counts.get("procedure", 0)
    if not substantive and (
        asks_for_process
        or not facts
        or all(b.evidence_type == "service_contact" for b in facts)
        and any(t.evidence_type != "service_contact" for t in tasks)
    ):
        facts.insert(
            0, AnswerBlock(text=labels["gap"] if facts else labels["empty"], kind="limitation")
        )
    return facts or [AnswerBlock(text=labels["empty"], kind="limitation")]

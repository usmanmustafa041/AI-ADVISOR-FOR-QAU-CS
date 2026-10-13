"""Source-check multilingual engineering cases; never fabricate departmental review.

These cases are reviewed by an AI coding agent against exact archived passages.
They are distinct from independently human-approved release ground truth.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.ingestion.archive import atomic_write, utc_now
from app.rag.corpus import load_corpus
from app.response.grounded import normalized

RULES = "https://qau.edu.pk/rules-regulations-relating-to-bs-program-morning-evening"
POLICIES = [
    (
        "How long is a regular BS semester under the archived rules?",
        "BS ka regular semester kitne hafton ka hai?",
        "بی ایس کا عام سمسٹر کتنے ہفتوں کا ہوتا ہے؟",
        "Each regular semester shall be spread over eighteen weeks",
        ["eighteen|18", "week|ہفت"],
    ),
    (
        "How many teaching weeks are in a BS semester?",
        "BS semester mein teaching kitne weeks hoti hai?",
        "بی ایس سمسٹر میں تدریس کے کتنے ہفتے ہوتے ہیں؟",
        "sixteen weeks for teaching",
        ["sixteen|16", "week|ہفت"],
    ),
    (
        "What is the normal BS duration under the archived university rules?",
        "Archived rules ke mutabiq BS ki muddat kya hai?",
        "محفوظ یونیورسٹی قواعد کے مطابق بی ایس کی عام مدت کیا ہے؟",
        (
            "The programs leading to BS shall be of four years duration, equally "
            "divided into eight regular semesters excluding summer semesters."
        ),
        ["four|4|چار", "eight|8|آٹھ"],
    ),
    (
        "At what BS CGPA does the archived rule drop a student from the rolls?",
        "Archived BS rules mein kis CGPA se neeche student drop hota hai?",
        "محفوظ بی ایس قواعد میں کس سی جی پی اے سے کم پر اخراج ہوتا ہے؟",
        "CGPA) less than 1.0",
        ["1\\.0|1", "less|below|kam|کم"],
    ),
    (
        "What CGPA range triggers BS probation in the archived rules?",
        "BS probation ke liye CGPA range kya hai?",
        "بی ایس میں پروبیشن کی سی جی پی اے حد کیا ہے؟",
        "CGPA is 1.0 and or more but less than 2.0",
        ["1", "2"],
    ),
    (
        "How many probation chances are allowed in the archived BS rules?",
        "BS mein probation ke kitne chances hain?",
        "بی ایس قواعد میں پروبیشن کے کتنے مواقع ہیں؟",
        (
            "A student shall be allowed three chances to remain on probation during "
            "the entire BS Programme of Studies."
        ),
        ["three|3|تین"],
    ),
    (
        "What is the maximum BS completion period in the archived rules?",
        "BS complete karne ki maximum muddat kya hai?",
        "محفوظ قواعد میں بی ایس مکمل کرنے کی زیادہ سے زیادہ مدت کیا ہے؟",
        (
            "A student shall have to complete the BS Programme within twelve (12) "
            "regular semesters or six years."
        ),
        ["six|6|چھ", "twelve|12|بارہ"],
    ),
    (
        "Do BS course registration rules require dues to be paid?",
        "BS course registration se pehle dues pay karna zaroori hai?",
        "کیا بی ایس کورس رجسٹریشن سے پہلے واجبات ادا کرنا ضروری ہے؟",
        "Registration shall be allowed if the student/ has paid all the required dues.",
        ["paid|pay|ادا"],
    ),
    (
        "What is the maximum credit exemption under the archived BS transfer rules?",
        "BS transfer mein maximum kitne credits exempt ho sakte hain?",
        "بی ایس منتقلی کے محفوظ قواعد میں زیادہ سے زیادہ کتنے کریڈٹ کی چھوٹ ہے؟",
        "The maximum exemption for course work shall be upto 51 credit hours.",
        ["51"],
    ),
    (
        "What minimum grade is considered for BS credit exemption?",
        "BS credit exemption ke liye minimum grade kya hai?",
        "بی ایس کریڈٹ کی چھوٹ کے لیے کم از کم گریڈ کیا ہے؟",
        (
            "Only the courses with at least C grade or GPA 2 out of 4 will be "
            "considered to be exempted."
        ),
        ["\\bC\\b|سی", "2"],
    ),
    (
        "What per-course transfer exemption fee appears in the archived BS rules?",
        "Archived BS rules mein per course exemption fee kitni hai?",
        "محفوظ بی ایس قواعد میں فی کورس چھوٹ کی فیس کتنی درج ہے؟",
        "Rs. 2000/- (Rupees two thousand) per course.",
        ["2,?000|two thousand|دو ہزار"],
    ),
    (
        "Are exempted transfer courses included in QAU GPA calculations?",
        "Exempted transfer courses QAU GPA mein count hote hain?",
        "کیا منتقل شدہ مستثنیٰ کورسز قاعو کے جی پی اے میں شامل ہوتے ہیں؟",
        (
            "GPA and CGPA will be computed on the basis of the courses that are "
            "registered at QAU only."
        ),
        ["QAU|قاعو", "only|sirf|صرف"],
    ),
    (
        "How many semesters can be frozen during BS under the archived rules?",
        "BS mein kitne semesters freeze kar sakte hain?",
        "بی ایس میں کتنے سمسٹر منجمد کیے جا سکتے ہیں؟",
        (
            "A student shall be allowed to apply for freezing of at the most two "
            "semesters in his/her entire program of studies."
        ),
        ["two|2|دو"],
    ),
    (
        "What is the standard BS semester freeze application period?",
        "BS semester freeze application kitne din mein deni hoti hai?",
        "بی ایس سمسٹر منجمد کرنے کی درخواست کی عام مدت کتنے دن ہے؟",
        "The application must be submitted within 45 days from the commencement of classes.",
        ["45"],
    ),
    (
        "What tuition deduction applies to the frozen BS semester refund in the archived rule?",
        "Archived BS freeze refund mein kitni tuition fee deduct hoti hai?",
        "محفوظ بی ایس قواعد میں منجمد سمسٹر کی فیس واپسی پر کتنی کٹوتی ہے؟",
        (
            "the University shall deduct 25% of the tuition fee deposited and the "
            "remaining 75% shall be reimbursed to the student."
        ),
        ["25", "75"],
    ),
    (
        "What is the usual BS credit load per regular semester in the archived rules?",
        "BS regular semester ka normal credit load kya hai?",
        "محفوظ قواعد میں بی ایس کے عام سمسٹر کا کریڈٹ بوجھ کیا ہے؟",
        "A student is required to take 15-18 credit hours coursework per regular semester.",
        ["15", "18"],
    ),
    (
        "What attendance percentage is required for BS terminal exams in the archived rules?",
        "Archived BS rules mein exam ke liye attendance kitni chahiye?",
        "محفوظ بی ایس قواعد میں امتحان کے لیے کتنی حاضری ضروری ہے؟",
        (
            "A student must have attended at least 80% of the classes held in a "
            "course in order to be allowed to sit in the terminal semester "
            "examination of that course."
        ),
        ["80"],
    ),
    (
        "What does 3+1 mean for a course's credit hours in the BS rules?",
        "Course credits mein 3+1 ka kya matlab hai?",
        "بی ایس قواعد میں کورس کے کریڈٹ 3+1 کا کیا مطلب ہے؟",
        (
            "For a course that includes both theory (T) and practical (P) "
            "components, the credit hours would be indicated as T + P, for example, "
            "3+1=4."
        ),
        ["3", "1", "4"],
    ),
]


def create(corpus):
    chunks = load_corpus(corpus)
    facts = []

    def add(questions, url, quote, patterns, category, reference=None):
        matches = [
            c
            for c in chunks
            if c.source_url.rstrip("/") == url.rstrip("/")
            and normalized(quote) in normalized(c.content)
        ]
        if not matches:
            raise ValueError(f"Unverified source label: {url}: {quote}")
        source = max(matches, key=lambda c: (bool(c.source_version_id), c.captured_at or ""))
        facts.append((questions, source, quote, patterns, category, reference or quote))

    for en, roman, urdu, quote, patterns in POLICIES:
        add([en, roman, urdu], RULES, quote, patterns, "academic_policies")
    # Faculty names and public emails are checked against exact source passages.
    faculty = {}
    for c in chunks:
        if c.category == "faculty" and "Faculty Profile" in c.title:
            email = re.search(r"[\w.+-]+@qau\.edu\.pk", c.content)
            if email and c.document_id not in faculty:
                name = c.title.split(" - ")[0]
                faculty[c.document_id] = (name, email[0], c)
    people = {}
    for name, email, c in faculty.values():
        people[name] = (email, c)
    for name, (email, c) in sorted(people.items()):
        add(
            [
                f"What is {name}'s published university email?",
                f"{name} ka official email kya hai?",
                f"{name} کا شائع شدہ یونیورسٹی ای میل کیا ہے؟",
            ],
            c.source_url,
            email,
            [re.escape(email)],
            "faculty",
            f"{name}: {email}",
        )
    # Manually inspected code/name/category/credit layout; no prerequisite inference.
    scheme = "https://cs.qau.edu.pk/doc/scheme-2025.pdf"
    course_facts = [
        ("EN-100", 3),
        ("EN-200", 3),
        ("PK-100", 2),
        ("IS-100", 2),
        ("MA-101", 3),
        ("CSC-110", 3),
        ("PH-110", 3),
        ("FQ-101", 1),
        ("FQ-102", 1),
        ("CSC-104", 4),
        ("MA-202", 3),
        ("CSC-121", 4),
        ("MA-203", 3),
        ("SW-100", 2),
        ("PS-101", 2),
        ("EN-299", 3),
        ("MA-104", 3),
    ]
    for code, credits in course_facts:
        source = next(
            c
            for c in chunks
            if c.source_url == scheme
            and c.evidence_type == "source"
            and re.search(re.escape(code) + r":", c.content)
        )
        line = next(line for line in source.content.splitlines() if code + ":" in line)
        add(
            [
                f"How many credit hours does {code} carry in the BSCS Fall 2025 scheme?",
                f"BSCS Fall 2025 scheme mein {code} ke kitne credit hours hain?",
                f"بی ایس سی ایس Fall 2025 نصاب میں {code} کے کتنے کریڈٹ آورز ہیں؟",
            ],
            scheme,
            line,
            [rf"\b{credits}\b"],
            "curriculum",
            f"{code}: {credits} credit hours, Fall 2025.",
        )
    add(
        [
            "What is the CS department's official office email?",
            "CS department office ka email kya hai?",
            "کمپیوٹر سائنس شعبے کے دفتر کا سرکاری ای میل کیا ہے؟",
        ],
        "https://cs.qau.edu.pk/contact",
        "cs@qau.edu.pk",
        [r"cs@qau\.edu\.pk"],
        "contacts",
    )
    add(
        [
            "What are the CS department office opening hours?",
            "CS department office kis waqt khulta hai?",
            "کمپیوٹر سائنس شعبے کے دفتر کے اوقات کیا ہیں؟",
        ],
        "https://cs.qau.edu.pk/contact",
        "Monday – Friday: 08:30 AM – 04:30 PM",
        ["08:30|8:30", "04:30|4:30"],
        "contacts",
    )
    academics = "https://cs.qau.edu.pk/academics"
    add(
        [
            "How long is the MS Data Science programme?",
            "MS Data Science ki muddat kitni hai?",
            "ایم ایس ڈیٹا سائنس پروگرام کی مدت کتنی ہے؟",
        ],
        academics,
        "MS Two years (4 semesters) 30 Credit Hours Admissions: Spring",
        ["two|2|دو", "four|4|چار"],
        "programmes",
    )
    add(
        [
            (
                "How many course-work credits does MPhil Computer Science require "
                "according to the academics page?"
            ),
            "Academics page ke mutabiq MPhil CS coursework ke kitne credits hain?",
            "تعلیمی صفحے کے مطابق ایم فل کمپیوٹر سائنس کے کورس ورک کے کتنے کریڈٹ ہیں؟",
        ],
        academics,
        "24 credit hours for the course work and 26 credit hours for research work.",
        ["24"],
        "programmes",
    )
    add(
        [
            "What is the minimum PhD Computer Science programme duration on the academics page?",
            "Academics page par PhD CS ki minimum muddat kya hai?",
            "تعلیمی صفحے پر پی ایچ ڈی کمپیوٹر سائنس کی کم از کم مدت کیا ہے؟",
        ],
        academics,
        "PhD Minimum 3 years 18 Credit Hours Admissions: Both",
        ["3|three|تین"],
        "programmes",
    )
    cases = []
    for i, (questions, source, quote, patterns, category, reference) in enumerate(facts):
        # Fact groups, including all translations, remain in the same split.
        split = "held_out" if i % 4 == 3 else "development"
        for language, question in zip(("english", "roman_urdu", "urdu"), questions, strict=True):
            cases.append(
                {
                    "id": f"source-{i + 1:03d}-{language}",
                    "fact_group": f"fact-{i + 1:03d}",
                    "split": split,
                    "question": question,
                    "language": language,
                    "category": category,
                    "expected_behavior": "answer",
                    "review_status": "agent_source_checked",
                    "reviewer": "Codex source verification",
                    "reviewed_at": utc_now(),
                    "review_kind": (
                        "AI source check; not independent human or departmental approval"
                    ),
                    "reference_answer": reference,
                    "required_patterns": patterns,
                    "relevant_sources": [
                        {
                            "source_url": source.source_url,
                            "source_version_id": source.source_version_id,
                            "source_sha256": source.source_sha256,
                            "page_number": source.page_number,
                            "quote": quote,
                        }
                    ],
                    "source_label_sha256": hashlib.sha256(quote.encode()).hexdigest(),
                }
            )
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument(
        "--output", type=Path, default=Path("backend/evaluation/source_checked_questions.json")
    )
    args = parser.parse_args()
    cases = create(args.corpus)
    atomic_write(args.output, json.dumps(cases, ensure_ascii=False, indent=2).encode())
    print(f"{len(cases)} AI source-checked cases; independent human approval remains outstanding")


if __name__ == "__main__":
    main()

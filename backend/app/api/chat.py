import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import optional_current_user
from app.nlp.service import analyze_query
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(tags=["chat"])


def _language_text(result: dict, english: str, roman: str, urdu: str) -> str:
    return urdu if result["language"] == "urdu" else roman if result["language"] == "roman_urdu" else english


def _safe_answer(result: dict, db: Session) -> tuple[str, str, bool, list[dict]]:
    intent = result["intent"]
    entities = result["entities"]
    roman_urdu = result["language"] == "roman_urdu"
    citations: list[dict] = []
    rule_categories = {
        "registration_process": ["registration"],
        "course_exemption": ["exemption"],
        "degree_requirement": ["graduation"],
        "gpa_requirement": ["progression", "graduation"],
        "probation_rule": ["progression"],
        "policy_information": ["attendance", "examination", "registration", "progression"],
    }
    if intent == "gpa_requirement" and any(word in result["text"].lower() for word in ("grading", "marks", "grade point")):
        rows = db.execute(text("""SELECT minimum_marks, maximum_marks, letter_grade, grade_points,
            s.source_code, s.title AS source_title, s.source_url, s.verification_status
            FROM grading_bands g JOIN source_records s ON s.id=g.source_id
            WHERE g.effective_from<=CURRENT_DATE AND (g.effective_to IS NULL OR g.effective_to>=CURRENT_DATE)
            ORDER BY minimum_marks DESC""")).mappings().all()
        if rows:
            citations.append({"source_code": rows[0]["source_code"], "title": rows[0]["source_title"], "source_url": rows[0]["source_url"]})
            scale = "; ".join(f"{row['minimum_marks']:.0f}-{row['maximum_marks']:.0f}: {row['letter_grade']} ({row['grade_points']:.2f})" for row in rows)
            demo = any(row["source_code"].startswith("MOCK-") for row in rows)
            return (("DEMO DATA - replace with an approved grading table. " if demo else "") + scale,
                    "sql", not demo, citations)
    if intent in rule_categories:
        categories = rule_categories[intent]
        question = result["text"].lower()
        pattern = None
        if intent == "registration_process":
            pattern = "%registration procedure%"
        elif intent == "probation_rule":
            pattern = "%probation%"
        elif intent == "gpa_requirement":
            pattern = "%cgpa%"
        elif intent == "policy_information" and "attendance" in question:
            pattern = "%attendance%"
            categories = ["attendance", "examination"]
        rows = db.execute(text("""SELECT r.title, r.description, r.category, s.source_code,
            s.title AS source_title, s.source_url, s.verification_status FROM academic_rules r
            JOIN source_records s ON s.id=r.source_id WHERE r.active=TRUE
              AND r.category=ANY(:categories)
              AND r.effective_from<=CURRENT_DATE
              AND (r.effective_to IS NULL OR r.effective_to>=CURRENT_DATE)
              AND (CAST(:pattern AS text) IS NULL OR r.title ILIKE CAST(:pattern AS text)
                   OR r.description ILIKE CAST(:pattern AS text))
            ORDER BY CASE WHEN s.verification_status='verified' THEN 0 ELSE 1 END, r.priority LIMIT 5"""),
            {"categories": categories, "pattern": pattern}).mappings().all()
        if rows:
            citations.append({"source_code": rows[0]["source_code"], "title": rows[0]["source_title"], "source_url": rows[0]["source_url"]})
            verified = all(row["verification_status"] == "verified" for row in rows)
            details = " ".join(f"{row['title']}: {row['description']}" for row in rows)
            intro = _language_text(
                result,
                "The applicable academic guidance is: ",
                "Is sawal ke liye available academic guidance yeh hai: ",
                "اس سوال کے لیے دستیاب تعلیمی رہنمائی یہ ہے: ",
            )
            return intro + details, "sql", verified, citations
        return _language_text(
            result,
            "No matching academic policy is stored. Please contact the department.",
            "Is sawal ke liye policy record nahi mila. Department se rabta karein.",
            "اس سوال کے لیے کوئی پالیسی ریکارڈ نہیں ملا۔ شعبے سے رابطہ کریں۔",
        ), "fallback", False, citations

    if intent == "program_information":
        program = (entities.get("program") or ["BSCS"])[0]
        if "programs" in result["text"].lower() or "offer" in result["text"].lower():
            rows = db.execute(text("SELECT code,name FROM programs WHERE active ORDER BY level,name")).mappings().all()
            return "Available stored programs are: " + "; ".join(f"{row['code']} - {row['name']}" for row in rows) + ".", "sql", True, citations
        row = db.execute(text("""SELECT code,name,normal_semesters,maximum_semesters,minimum_cgpa
            FROM programs WHERE upper(code)=upper(:code) AND active"""), {"code": program}).mappings().one_or_none()
        if row:
            answer = _language_text(
                result,
                f"{row['name']} ({row['code']}) normally has {row['normal_semesters']} semesters, a maximum of {row['maximum_semesters']} semesters, and minimum CGPA {row['minimum_cgpa']}.",
                f"{row['name']} ({row['code']}) aam tor par {row['normal_semesters']} semesters ka program hai; maximum {row['maximum_semesters']} semesters aur minimum CGPA {row['minimum_cgpa']} hai.",
                f"{row['name']} ({row['code']}) عام طور پر {row['normal_semesters']} سمسٹر کا پروگرام ہے، زیادہ سے زیادہ {row['maximum_semesters']} سمسٹر اور کم از کم CGPA {row['minimum_cgpa']} ہے۔",
            )
            return answer, "sql", True, citations
        return "Program record was not found.", "fallback", False, citations

    if intent == "semester_information":
        semester = (entities.get("semester") or [None])[0]
        if semester:
            rows = db.execute(text("""SELECT c.code,c.title,c.total_credit_hours FROM curriculum_courses cc
                JOIN courses c ON c.id=cc.course_id JOIN curriculum_schemes cs ON cs.id=cc.curriculum_id
                WHERE cs.name='Fall 2025 onward' AND cc.semester_number=:semester ORDER BY cc.display_order"""),
                {"semester": int(semester)}).mappings().all()
            if rows:
                courses = ", ".join(f"{r['code']} {r['title']}" for r in rows)
                return _language_text(result, f"Semester {semester} includes: {courses}.",
                    f"Semester {semester} mein yeh courses hain: {courses}.",
                    f"سمسٹر {semester} میں یہ کورسز شامل ہیں: {courses}۔"), "sql", True, citations
        row = db.execute(text("SELECT normal_semesters, maximum_semesters FROM programs WHERE code='BSCS'")).mappings().one()
        return _language_text(result, f"BSCS normally takes {row['normal_semesters']} semesters; the stored maximum is {row['maximum_semesters']} semesters. Open Study Plan for semester details.",
            f"BSCS aam tor par {row['normal_semesters']} semesters ka hai; stored maximum {row['maximum_semesters']} semesters hai. Tafseel ke liye Study Plan kholein.",
            f"بی ایس سی ایس عام طور پر {row['normal_semesters']} سمسٹر کا ہے؛ درج شدہ زیادہ سے زیادہ مدت {row['maximum_semesters']} سمسٹر ہے۔"), "sql", True, citations
    if intent == "course_prerequisite":
        course = (entities.get("course_code") or entities.get("course_name") or ["the requested course"])[0]
        if entities.get("course_code"):
            rows = db.execute(text("""SELECT pc.code, pc.title, cp.minimum_grade, cp.verified, cp.waiver_condition, s.source_code,
                s.title AS source_title, s.source_url, s.verification_status FROM course_prerequisites cp
                JOIN courses c ON c.id=cp.course_id JOIN courses pc ON pc.id=cp.prerequisite_course_id
                JOIN source_records s ON s.id=cp.source_id WHERE upper(c.code)=upper(:code) ORDER BY pc.code"""),
                {"code": course}).mappings().all()
            if rows:
                demo = any(r["source_code"].startswith("MOCK-") for r in rows)
                formally_verified = all(r["verified"] for r in rows)
                citations.extend({"source_code": r["source_code"], "title": r["source_title"], "source_url": r["source_url"]} for r in rows[:1])
                needed = ", ".join(f"{r['code']} ({r['title']})" + (f", minimum grade {r['minimum_grade']}" if r["minimum_grade"] else "") for r in rows)
                if formally_verified:
                    if roman_urdu:
                        return (f"{course} ke published prerequisites yeh hain: {needed}.", "sql", True, citations)
                    return (f"The published prerequisites for {course} are: {needed}.", "sql", True, citations)
                prefix = ("DEMO DATA - not official QAU guidance. " if demo else
                          "PROGRESSION GUIDANCE - inferred from the official Fall 2025 semester sequence, not a formally published prerequisite rule. ")
                if roman_urdu:
                    roman_prefix = ("DEMO DATA - yeh official QAU guidance nahi hai. " if demo else
                                    "PROGRESSION GUIDANCE - yeh Fall 2025 study sequence se andaza hai, official prerequisite rule nahi. ")
                    return (f"{roman_prefix}{course} se pehle yeh course parhna recommend kiya gaya hai: {needed}. Registration se pehle department se confirm kar lein.", "sql", False, citations)
                return (f"{prefix}Recommended prior course(s) for {course}: {needed}. Confirm registration eligibility with the department.", "sql", False, citations)
            placement = db.execute(text("""SELECT cc.semester_number, s.source_code,
                s.title AS source_title, s.source_url FROM curriculum_courses cc
                JOIN courses c ON c.id=cc.course_id
                JOIN curriculum_schemes cs ON cs.id=cc.curriculum_id
                JOIN source_records s ON s.id=cs.source_id
                WHERE upper(c.code)=upper(:code) AND cs.name='Fall 2025 onward'
                ORDER BY cc.semester_number LIMIT 1"""), {"code": course}).mappings().one_or_none()
            if placement and placement["semester_number"] == 1:
                citations.append({"source_code": placement["source_code"], "title": placement["source_title"], "source_url": placement["source_url"]})
                if roman_urdu:
                    return (f"{course} Fall 2025 onward BSCS study plan mein Semester 1 ka course hai, is liye scheme mein is se pehle koi course nahi diya gaya. Formal prerequisite record publish nahi mila; registration ke liye department se confirm kar lein.", "sql", False, citations)
                return (f"{course} is placed in Semester 1 of the Fall 2025 onward BSCS study plan, so the scheme lists no earlier course. No formal published prerequisite record was found; confirm registration eligibility with the department.", "sql", False, citations)
        if roman_urdu:
            return (
                f"Mujhe {course} ka prerequisite sawal samajh aya, lekin complete official prerequisite matrix mojood nahi. Department se confirm kiye baghair main eligibility confirm nahi kar sakta.",
                "fallback", False, citations,
            )
        return (
            f"I identified a prerequisite question about {course}. The complete departmental prerequisite "
            "matrix is not available yet, so I cannot safely confirm eligibility.",
            "fallback",
            False,
            citations,
        )
    if intent == "course_information":
        code = (entities.get("course_code") or [None])[0]
        if code:
            try:
                row = db.execute(text("""
                    SELECT c.code, c.title, c.description, c.total_credit_hours,
                           s.source_code, s.title AS source_title, s.source_url
                    FROM courses c
                    LEFT JOIN source_records s ON s.id = c.source_id
                    WHERE upper(replace(c.code, ' ', '')) = upper(replace(:code, ' ', ''))
                """), {"code": code}).mappings().one_or_none()
            except SQLAlchemyError:
                row = None
            if row:
                citations.append({"source_code": row["source_code"], "title": row["source_title"], "source_url": row["source_url"]})
                return (
                    f"{row['code']}: {row['title']} ({row['total_credit_hours']} credit hours). "
                    f"{row['description'] or 'No fuller description is stored in the verified catalogue.'}",
                    "verified_catalogue",
                    True,
                    citations,
                )
        return ("I could not match that course to the verified QAU catalogue.", "fallback", False, citations)
    if intent == "registration_deadline":
        row = db.execute(text("""SELECT d.title, d.closes_at::text, s.source_code, s.title AS source_title,
            s.source_url FROM deadlines d JOIN source_records s ON s.id=d.source_id
            WHERE d.closes_at >= NOW() ORDER BY d.closes_at LIMIT 1""")).mappings().one_or_none()
        if row:
            demo = row["source_code"].startswith("MOCK-"); citations.append({"source_code": row["source_code"], "title": row["source_title"], "source_url": row["source_url"]})
            return (_language_text(result,
                f"{'DEMO DATA - not an official QAU deadline. ' if demo else ''}{row['title']} closes at {row['closes_at']}.",
                f"{'DEMO DATA - yeh official deadline nahi hai. ' if demo else ''}{row['title']} ki last date {row['closes_at']} hai.",
                f"{'ڈیمو ڈیٹا - یہ سرکاری آخری تاریخ نہیں ہے۔ ' if demo else ''}{row['title']} کی آخری تاریخ {row['closes_at']} ہے۔"), "sql", not demo, citations)
        return (_language_text(result, "No current registration deadline is stored. Please contact the department office.",
            "Current registration deadline record nahi mila; department office se rabta karein.",
            "موجودہ رجسٹریشن کی آخری تاریخ دستیاب نہیں۔ شعبے کے دفتر سے رابطہ کریں۔"), "fallback", False, citations)
    if intent == "timetable_query":
        code = (entities.get("course_code") or [None])[0]
        semester = (entities.get("semester") or [None])[0]
        row = db.execute(text("""SELECT c.code, t.day_of_week, t.starts_at::text, t.ends_at::text,
            t.room, o.instructor, at.term, at.academic_year, s.source_code, s.title AS source_title, s.source_url
            FROM timetable_entries t JOIN course_offerings o ON o.id=t.offering_id JOIN courses c ON c.id=o.course_id
            JOIN academic_terms at ON at.id=o.term_id JOIN source_records s ON s.id=o.source_id
            WHERE at.active=TRUE AND (CAST(:code AS text) IS NULL OR upper(c.code)=upper(CAST(:code AS text)))
              AND (CAST(:semester AS integer) IS NULL OR EXISTS (SELECT 1 FROM curriculum_courses cc
                  JOIN curriculum_schemes cs ON cs.id=cc.curriculum_id
                  WHERE cc.course_id=c.id AND cc.semester_number=CAST(:semester AS integer)
                    AND cs.name='Fall 2025 onward'))
            ORDER BY t.day_of_week,t.starts_at LIMIT 1"""), {"code": code, "semester": semester}).mappings().one_or_none()
        if row:
            demo = row["source_code"].startswith("MOCK-"); days = ["", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
            citations.append({"source_code": row["source_code"], "title": row["source_title"], "source_url": row["source_url"]})
            if roman_urdu:
                return (f"{'DEMO DATA - yeh official QAU timetable nahi hai. ' if demo else ''}{row['code']} ki class {days[row['day_of_week']]} ko {row['starts_at']} se {row['ends_at']} tak {row['room']} mein hai; instructor: {row['instructor']}.", "sql", not demo, citations)
            if result["language"] == "urdu":
                return (f"{'ڈیمو ڈیٹا - یہ سرکاری QAU ٹائم ٹیبل نہیں ہے۔ ' if demo else ''}{row['code']} کی کلاس {days[row['day_of_week']]} کو {row['starts_at']} سے {row['ends_at']} تک {row['room']} میں ہے؛ استاد: {row['instructor']}۔", "sql", not demo, citations)
            return (f"{'DEMO DATA - not an official QAU timetable. ' if demo else ''}{row['code']} meets on {days[row['day_of_week']]} from {row['starts_at']} to {row['ends_at']} in {row['room']}; instructor: {row['instructor']}.", "sql", not demo, citations)
        return (_language_text(result, "No current timetable record matches that course or semester.",
            "Is course ya semester ka timetable record nahi mila.",
            "اس کورس یا سمسٹر کا ٹائم ٹیبل ریکارڈ نہیں ملا۔"), "fallback", False, citations)
    if intent == "exam_schedule":
        code = (entities.get("course_code") or [None])[0]
        semester = (entities.get("semester") or [None])[0]
        row = db.execute(text("""SELECT c.code, e.exam_type, e.exam_date::text, e.starts_at::text, e.room,
            s.source_code, s.title AS source_title, s.source_url FROM exam_schedules e
            JOIN course_offerings o ON o.id=e.offering_id JOIN courses c ON c.id=o.course_id
            JOIN source_records s ON s.id=e.source_id WHERE (CAST(:code AS text) IS NULL OR upper(c.code)=upper(CAST(:code AS text)))
              AND (CAST(:semester AS integer) IS NULL OR EXISTS (SELECT 1 FROM curriculum_courses cc
                  JOIN curriculum_schemes cs ON cs.id=cc.curriculum_id
                  WHERE cc.course_id=c.id AND cc.semester_number=CAST(:semester AS integer)
                    AND cs.name='Fall 2025 onward'))
            ORDER BY e.exam_date,e.starts_at LIMIT 1"""), {"code": code, "semester": semester}).mappings().one_or_none()
        if row:
            demo = row["source_code"].startswith("MOCK-"); citations.append({"source_code": row["source_code"], "title": row["source_title"], "source_url": row["source_url"]})
            return (_language_text(result,
                f"{'DEMO DATA - not an official QAU datesheet. ' if demo else ''}{row['code']} {row['exam_type']} exam: {row['exam_date']} at {row['starts_at']} in {row['room']}.",
                f"{'DEMO DATA - yeh official datesheet nahi hai. ' if demo else ''}{row['code']} ka {row['exam_type']} exam {row['exam_date']} ko {row['starts_at']} baje {row['room']} mein hai.",
                f"{'ڈیمو ڈیٹا - یہ سرکاری ڈیٹ شیٹ نہیں ہے۔ ' if demo else ''}{row['code']} کا {row['exam_type']} امتحان {row['exam_date']} کو {row['starts_at']} بجے {row['room']} میں ہے۔"), "sql", not demo, citations)
        return (_language_text(result, "No matching examination schedule is stored.",
            "Is course ya semester ka exam schedule nahi mila.",
            "اس کورس یا سمسٹر کا امتحانی شیڈول نہیں ملا۔"), "fallback", False, citations)
    if intent == "thesis_information":
        rows = db.execute(text("""SELECT r.title,r.description,s.source_code,s.title AS source_title,s.source_url
            FROM academic_rules r JOIN source_records s ON s.id=r.source_id WHERE r.active=TRUE AND r.category IN ('fyp','thesis')
            ORDER BY r.priority LIMIT 3""")).mappings().all()
        if rows:
            demo = any(r["source_code"].startswith("MOCK-") for r in rows); citations.append({"source_code": rows[0]["source_code"], "title": rows[0]["source_title"], "source_url": rows[0]["source_url"]})
            return (("DEMO DATA - not official QAU guidance. " if demo else "") + " ".join(f"{r['title']}: {r['description']}" for r in rows), "sql", not demo, citations)
        return ("No departmental thesis or FYP guideline is stored.", "fallback", False, citations)
    if intent == "fee_information":
        rows = db.execute(text("""SELECT f.shift,f.fee_type,f.amount,f.currency,s.source_code,s.title AS source_title,s.source_url
            FROM fee_structures f JOIN programs p ON p.id=f.program_id JOIN source_records s ON s.id=f.source_id
            WHERE p.code='BSCS' AND f.official_fee_category='BS Computer Science - National Students'
            AND f.fee_type IN ('admission_fee','semester_total','initial_total_a_plus_b')
            AND f.effective_from<=CURRENT_DATE AND (f.effective_to IS NULL OR f.effective_to>=CURRENT_DATE)
            ORDER BY f.shift,f.fee_type LIMIT 6""")).mappings().all()
        if rows:
            demo = any(r["source_code"].startswith("MOCK-") for r in rows); citations.append({"source_code": rows[0]["source_code"], "title": rows[0]["source_title"], "source_url": rows[0]["source_url"]})
            labels = {"admission_fee": "admission fee", "semester_total": "per-semester fee", "initial_total_a_plus_b": "initial total (A+B)"}
            details = "; ".join(f"{r['shift']} {labels.get(r['fee_type'], r['fee_type'])}: {r['currency']} {r['amount']:,.0f}" for r in rows)
            prefix = _language_text(result,
                "DEMO DATA - example amounts, not an official QAU fee notice. " if demo else "",
                "DEMO DATA - yeh official fee notice nahi hai. " if demo else "Fee details: ",
                "ڈیمو ڈیٹا - یہ سرکاری فیس نوٹس نہیں ہے۔ " if demo else "فیس کی تفصیل: ")
            return (prefix + details, "sql", not demo, citations)
        return (_language_text(result, "No currently effective fee record is stored.",
            "Current fee record nahi mila.", "موجودہ فیس ریکارڈ دستیاب نہیں۔"), "fallback", False, citations)
    if intent == "credit_hour_limit":
        return ("The published BSCS scheme lists semester loads of 15–18 credit hours. Exceptions require the applicable official approval; I cannot approve an individual registration from this chat.", "verified_policy", True, citations)
    if intent == "greeting":
        return _language_text(result, "Wa Alaikum Assalam. I can help with verified QAU CS academic information.",
            "Wa Alaikum Assalam. Main QAU CS ki academic maloomat mein madad kar sakta hoon.",
            "وعلیکم السلام۔ میں QAU CS کی تعلیمی معلومات میں مدد کر سکتا ہوں۔"), "fallback", True, citations
    if intent == "help":
        return _language_text(result, "You can ask about courses, prerequisites, registration, fees, timetables, exams, thesis rules, or progression.",
            "Aap courses, prerequisites, registration, fees, timetable, exams, thesis ya progression pooch sakte hain.",
            "آپ کورسز، شرائط، رجسٹریشن، فیس، ٹائم ٹیبل، امتحانات، تھیسس یا تعلیمی پیش رفت پوچھ سکتے ہیں۔"), "fallback", True, citations
    return (_language_text(result,
        "I could not understand that clearly. Please rephrase the academic question or mention a course code; you may also contact the department.",
        "Mujhe sawal wazeh samajh nahi aya. Dobara asaan alfaaz mein poochein ya course code batayein; zarurat par department se rabta karein.",
        "میں سوال واضح طور پر نہیں سمجھ سکا۔ براہ کرم آسان الفاظ میں دوبارہ پوچھیں یا کورس کوڈ لکھیں؛ ضرورت پر شعبے سے رابطہ کریں۔"),
        "fallback", False, citations)


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    user: dict | None = Depends(optional_current_user),
) -> dict:
    started = time.perf_counter()
    result = analyze_query(request.message)
    if request.context_course_code and not result["entities"].get("course_code"):
        normalized_context = request.context_course_code.upper()
        if "-" not in normalized_context:
            normalized_context = f"{normalized_context[:-3]}-{normalized_context[-3:]}"
        result["entities"]["course_code"] = [normalized_context]
    try:
        answer, engine, verified, citations = _safe_answer(result, db)
    except SQLAlchemyError:
        db.rollback()
        if result["intent"] == "course_prerequisite":
            course = (result["entities"].get("course_code") or ["the requested course"])[0]
            answer = (f"I identified a prerequisite question about {course}. The complete departmental prerequisite "
                      "matrix is not available yet, so I cannot safely confirm eligibility.")
        else:
            answer = "The academic database is temporarily unavailable. Please try again or contact the department."
        engine, verified, citations = "fallback", False, []
    session_id: str | None = None
    if user:
        try:
            if request.session_id:
                try:
                    UUID(request.session_id)
                except ValueError:
                    raise HTTPException(status_code=422, detail="Invalid chat session id") from None
                session = db.execute(text("""
                    SELECT id::text FROM chat_sessions
                    WHERE id=:session_id AND user_id=:user_id AND ended_at IS NULL
                """), {"session_id": request.session_id, "user_id": user["id"]}).mappings().one_or_none()
                if not session:
                    raise HTTPException(status_code=404, detail="Chat session was not found")
                session_id = session["id"]
            else:
                session_id = db.execute(text("""
                    INSERT INTO chat_sessions (user_id, language)
                    VALUES (:user_id, :language) RETURNING id::text
                """), {"user_id": user["id"], "language": result["language"]}).scalar_one()

            elapsed_ms = int((time.perf_counter() - started) * 1000)
            db.execute(text("""
                INSERT INTO chat_messages
                    (session_id, role, content, intent, intent_confidence, entities, response_engine)
                VALUES (:session_id, 'user', :content, :intent, :confidence,
                        CAST(:entities AS jsonb), NULL)
            """), {
                "session_id": session_id, "content": request.message,
                "intent": result["intent"], "confidence": result["confidence"],
                "entities": json.dumps(result["entities"]),
            })
            db.execute(text("""
                INSERT INTO chat_messages
                    (session_id, role, content, intent, intent_confidence, entities,
                     response_engine, response_time_ms)
                VALUES (:session_id, 'assistant', :content, :intent, :confidence,
                        CAST(:entities AS jsonb), :engine, :elapsed_ms)
            """), {
                "session_id": session_id, "content": answer, "intent": result["intent"],
                "confidence": result["confidence"], "entities": json.dumps(result["entities"]),
                "engine": engine if engine in {"sql", "rule", "rag", "fallback"} else "fallback",
                "elapsed_ms": elapsed_ms,
            })
            db.commit()
        except HTTPException:
            db.rollback()
            raise
        except SQLAlchemyError:
            db.rollback()
            # Academic guidance remains available if history storage is temporarily unavailable.
            session_id = None
    return {
        "answer": answer,
        "intent": result["intent"],
        "language": result["language"],
        "confidence": result["confidence"],
        "entities": result["entities"],
        "model_backend": result["model_backend"],
        "model_name": result["model_name"],
        "response_engine": engine,
        "citations": citations,
        "verified": verified,
        "session_id": session_id,
    }

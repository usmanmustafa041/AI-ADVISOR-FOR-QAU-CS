from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.academic import (
    CourseDetail,
    FeeResponse,
    PrerequisiteResponse,
    ProgramSummary,
    TimetableResponse,
)

router = APIRouter(tags=["academic data"])

SOURCE_COLUMNS = """
    s.source_code,
    s.title AS source_title,
    s.source_url,
    s.last_verified_at::text AS last_verified_at,
    s.verification_status
"""


def _source(row: dict) -> dict | None:
    if row.get("source_code") is None:
        return None
    return {
        "source_code": row["source_code"],
        "title": row["source_title"],
        "source_url": row["source_url"],
        "last_verified_at": row["last_verified_at"],
        "verification_status": row["verification_status"],
    }


@router.get("/programs", response_model=list[ProgramSummary])
def list_programs(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.execute(
        text("""
            SELECT id, code, name, level, study_mode, normal_semesters,
                   maximum_semesters, minimum_cgpa
            FROM programs
            WHERE active = TRUE
            ORDER BY level, name
        """)
    ).mappings()
    return [dict(row) for row in rows]


@router.get("/programs/{program_code}/study-plan")
def study_plan(
    program_code: str,
    curriculum: str = Query(default="Fall 2025 onward"),
    db: Session = Depends(get_db),
) -> dict:
    scheme = db.execute(text("""SELECT cs.id, cs.name, cs.total_credit_hours, s.source_code,
        s.title AS source_title, s.source_url, s.verification_status
        FROM curriculum_schemes cs JOIN programs p ON p.id=cs.program_id
        JOIN source_records s ON s.id=cs.source_id
        WHERE upper(p.code)=upper(:program_code) AND cs.name=:curriculum"""),
        {"program_code": program_code, "curriculum": curriculum}).mappings().one_or_none()
    if not scheme:
        raise HTTPException(status_code=404, detail="Curriculum scheme was not found")
    rows = db.execute(text("""SELECT cc.semester_number, c.code, c.title,
        cc.requirement_type, c.total_credit_hours, cc.display_order
        FROM curriculum_courses cc JOIN courses c ON c.id=cc.course_id
        WHERE cc.curriculum_id=:curriculum_id
        UNION ALL
        SELECT cs.semester_number, NULL AS code, cs.title, cs.requirement_type,
        cs.credit_hours AS total_credit_hours, cs.display_order
        FROM curriculum_slots cs WHERE cs.curriculum_id=:curriculum_id
        ORDER BY semester_number, display_order NULLS LAST, code NULLS LAST"""),
        {"curriculum_id": scheme["id"]}).mappings().all()
    semesters = []
    for number in range(1, 9):
        courses = [dict(row) for row in rows if row["semester_number"] == number]
        semesters.append({"semester": number, "courses": courses,
                          "credit_hours": float(sum(row["total_credit_hours"] for row in courses))})
    return {"program_code": program_code.upper(), "curriculum": scheme["name"],
            "total_credit_hours": float(scheme["total_credit_hours"]), "semesters": semesters,
            "internship": "Six to eight weeks during the degree, coordinated by the internship coordinator.",
            "source": {"source_code": scheme["source_code"], "title": scheme["source_title"],
                       "source_url": scheme["source_url"], "verification_status": scheme["verification_status"]}}


@router.get("/courses", response_model=list[CourseDetail])
def list_courses(
    search: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(
        text(f"""
            SELECT c.id, c.code, c.title, c.description, c.theory_credit_hours,
                   c.lab_credit_hours, c.total_credit_hours, c.active,
                   {SOURCE_COLUMNS}
            FROM courses c
            LEFT JOIN source_records s ON s.id = c.source_id
            WHERE (CAST(:search AS text) IS NULL OR c.code ILIKE :pattern OR c.title ILIKE :pattern)
            ORDER BY c.code
            LIMIT :limit
        """),
        {"search": search, "pattern": f"%{search}%" if search else None, "limit": limit},
    ).mappings()
    results = []
    for row in rows:
        item = dict(row)
        item["source"] = _source(item)
        results.append(item)
    return results


@router.get("/courses/{course_code}", response_model=CourseDetail)
def get_course(course_code: str, db: Session = Depends(get_db)) -> dict:
    row = db.execute(
        text(f"""
            SELECT c.id, c.code, c.title, c.description, c.theory_credit_hours,
                   c.lab_credit_hours, c.total_credit_hours, c.active,
                   {SOURCE_COLUMNS}
            FROM courses c
            LEFT JOIN source_records s ON s.id = c.source_id
            WHERE UPPER(REPLACE(c.code, ' ', '')) = UPPER(REPLACE(:code, ' ', ''))
        """),
        {"code": course_code},
    ).mappings().one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Course code was not found in verified data")
    result = dict(row)
    result["source"] = _source(result)
    return result


@router.get("/courses/{course_code}/prerequisites", response_model=PrerequisiteResponse)
def get_prerequisites(
    course_code: str,
    curriculum: str = Query(default="Fall 2025 onward"),
    db: Session = Depends(get_db),
) -> dict:
    course = db.execute(
        text("SELECT id, code, title FROM courses WHERE UPPER(code)=UPPER(:code)"),
        {"code": course_code},
    ).mappings().one_or_none()
    if course is None:
        raise HTTPException(status_code=404, detail="Course code was not found in verified data")

    rows = db.execute(
        text(f"""
            SELECT pc.code AS course_code, pc.title AS course_title,
                   cp.relation_type, cp.minimum_grade, cp.waiver_condition,
                   cp.verified, {SOURCE_COLUMNS}
            FROM course_prerequisites cp
            JOIN curriculum_schemes cs ON cs.id = cp.curriculum_id
            JOIN courses pc ON pc.id = cp.prerequisite_course_id
            JOIN source_records s ON s.id = cp.source_id
            WHERE cp.course_id = :course_id AND cs.name = :curriculum
            ORDER BY pc.code
        """),
        {"course_id": course["id"], "curriculum": curriculum},
    ).mappings()

    items = []
    for row in rows:
        item = dict(row)
        item["source"] = _source(item)
        items.append(item)

    has_unverified_guidance = any(not item["verified"] for item in items)
    return {
        "course_code": course["code"],
        "course_title": course["title"],
        "curriculum": curriculum,
        "prerequisites": items,
        "dataset_complete": False,
        "notice": (
            "Some listed links are planning guidance inferred from semester placement and are not formal published prerequisites; confirm eligibility with the department."
            if has_unverified_guidance else
            "The public QAU CS website does not publish a complete prerequisite matrix. An empty list means no verified public record is stored; it does not prove that the course has no prerequisite."
        ),
    }


@router.get("/fees", response_model=FeeResponse)
def list_fees(
    program_code: str | None = None,
    official_category: str | None = None,
    as_of: date = Query(default_factory=date.today),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.execute(
        text(f"""
            SELECT p.code AS program_code, p.name AS program_name,
                   f.official_fee_category, f.shift, f.fee_type, f.amount,
                   f.currency, f.effective_from, f.effective_to,
                   {SOURCE_COLUMNS}
            FROM fee_structures f
            LEFT JOIN programs p ON p.id = f.program_id
            JOIN source_records s ON s.id = f.source_id
            WHERE (CAST(:program_code AS text) IS NULL OR UPPER(p.code)=UPPER(CAST(:program_code AS text)))
              AND (CAST(:official_category AS text) IS NULL OR f.official_fee_category ILIKE CAST(:official_category AS text))
              AND f.effective_from <= :as_of
              AND (f.effective_to IS NULL OR f.effective_to >= :as_of)
            ORDER BY f.official_fee_category, f.shift, f.fee_type
        """),
        {
            "program_code": program_code,
            "official_category": official_category,
            "as_of": as_of,
        },
    ).mappings()
    fees = []
    for row in rows:
        item = dict(row)
        item["source"] = _source(item)
        fees.append(item)

    demo_data = any(item["source"]["source_code"].startswith("MOCK-") for item in fees)
    stale = any(item["source"]["source_code"] == "SRC-FEES-F2025" for item in fees)
    notice = None
    if stale and as_of > date(2026, 1, 31):
        notice = "These are Fall 2025 fee-table records and should be re-verified for the requested date."
    if demo_data:
        notice = "DEMO DATA - synthetic fee examples for project testing; not an official QAU fee notice."
    return {"as_of": as_of, "fees": fees, "notice": notice, "demo_data": demo_data}


@router.get("/timetable", response_model=TimetableResponse)
def timetable(
    academic_year: int = Query(ge=2000, le=2200),
    term: str = Query(pattern="^(Spring|Summer|Fall|Winter)$"),
    course_code: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    rows = db.execute(
        text(f"""
            SELECT c.code AS course_code, c.title AS course_title, o.section,
                   o.instructor, t.session_type, t.day_of_week, t.starts_at,
                   t.ends_at, t.room, t.lab_group, {SOURCE_COLUMNS}
            FROM timetable_entries t
            JOIN course_offerings o ON o.id = t.offering_id
            JOIN courses c ON c.id = o.course_id
            JOIN academic_terms at ON at.id = o.term_id
            JOIN source_records s ON s.id = o.source_id
            WHERE at.academic_year = :academic_year AND at.term = :term
              AND (CAST(:course_code AS text) IS NULL OR UPPER(c.code)=UPPER(CAST(:course_code AS text)))
            ORDER BY t.day_of_week, t.starts_at, c.code
        """),
        {"academic_year": academic_year, "term": term, "course_code": course_code},
    ).mappings()
    entries = []
    for row in rows:
        item = dict(row)
        item["source"] = _source(item)
        entries.append(item)
    return {
        "academic_year": academic_year,
        "term": term,
        "entries": entries,
        "verified_data_available": bool(entries),
        "notice": None if entries else "No verified timetable has been supplied for this term.",
        "demo_data": any(item["source"]["source_code"].startswith("MOCK-") for item in entries),
    }


@router.get("/policies")
def list_policies(
    category: str | None = None,
    search: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """Search currently effective, source-backed academic policies and guidelines."""
    rows = db.execute(text(f"""
        SELECT r.rule_code, r.category, r.title, r.description, r.effective_from,
               r.effective_to, {SOURCE_COLUMNS}
        FROM academic_rules r JOIN source_records s ON s.id=r.source_id
        WHERE r.active=TRUE AND (CAST(:category AS text) IS NULL OR r.category ILIKE CAST(:category AS text))
          AND (CAST(:search AS text) IS NULL OR r.title ILIKE :pattern OR r.description ILIKE :pattern)
          AND r.effective_from <= CURRENT_DATE
          AND (r.effective_to IS NULL OR r.effective_to >= CURRENT_DATE)
        ORDER BY r.priority, r.title
    """), {"category": category, "search": search, "pattern": f"%{search}%" if search else None}).mappings()
    result = []
    for row in rows:
        item = dict(row); item["source"] = _source(item); result.append(item)
    return result


@router.get("/deadlines")
def list_deadlines(
    program_code: str | None = None,
    include_expired: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    rows = db.execute(text(f"""
        SELECT d.deadline_type, d.title, d.opens_at::text, d.closes_at::text,
               d.expires_at::text, d.notes, p.code AS program_code, at.term,
               at.academic_year, {SOURCE_COLUMNS}
        FROM deadlines d LEFT JOIN programs p ON p.id=d.program_id
        LEFT JOIN academic_terms at ON at.id=d.term_id JOIN source_records s ON s.id=d.source_id
        WHERE (CAST(:program_code AS text) IS NULL OR upper(p.code)=upper(CAST(:program_code AS text)))
          AND (:include_expired OR d.expires_at >= NOW()) ORDER BY d.closes_at
    """), {"program_code": program_code, "include_expired": include_expired}).mappings()
    result = []
    for row in rows:
        item = dict(row); item["source"] = _source(item); result.append(item)
    return result


@router.get("/exams")
def list_exams(
    academic_year: int = Query(ge=2000, le=2200),
    term: str = Query(pattern="^(Spring|Summer|Fall|Winter)$"),
    course_code: str | None = None,
    db: Session = Depends(get_db),
) -> dict:
    rows = db.execute(text(f"""
        SELECT c.code AS course_code, c.title AS course_title, e.exam_type,
               e.exam_date, e.starts_at, e.ends_at, e.room, {SOURCE_COLUMNS}
        FROM exam_schedules e JOIN course_offerings o ON o.id=e.offering_id
        JOIN courses c ON c.id=o.course_id JOIN academic_terms at ON at.id=o.term_id
        JOIN source_records s ON s.id=e.source_id
        WHERE at.academic_year=:academic_year AND at.term=:term
          AND (CAST(:course_code AS text) IS NULL OR upper(c.code)=upper(CAST(:course_code AS text)))
        ORDER BY e.exam_date, e.starts_at, c.code
    """), {"academic_year": academic_year, "term": term, "course_code": course_code}).mappings()
    entries = []
    for row in rows:
        item = dict(row); item["source"] = _source(item); entries.append(item)
    return {"academic_year": academic_year, "term": term, "entries": entries,
            "notice": None if entries else "No verified examination schedule is available for this term."}

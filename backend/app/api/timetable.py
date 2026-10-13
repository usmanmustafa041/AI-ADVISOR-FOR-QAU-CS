"""
Timetable API endpoints for Spring 2026 schedule queries.
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlalchemy.orm import Session
from typing import Optional

from app.core.database import get_db
from app.schemas.timetable import (
    TimetableEntry,
    TimetableResponse,
    InstructorSchedule,
    RoomSchedule,
    CourseScheduleDetail,
    SessionInfo,
)

router = APIRouter(prefix="/timetable", tags=["timetable"])


@router.get("/sessions", response_model=list[SessionInfo])
def get_academic_sessions(
    current_only: bool = False,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Get all academic sessions or just the current one.
    """
    query = """
        SELECT 
            id,
            session_name,
            effective_from,
            effective_to,
            is_current,
            created_at,
            updated_at
        FROM academic_sessions
        WHERE (:current_only = FALSE OR is_current = TRUE)
        ORDER BY effective_from DESC
    """
    
    rows = db.execute(
        text(query),
        {"current_only": current_only}
    ).mappings()
    
    return [dict(row) for row in rows]


@router.get("/schedule", response_model=TimetableResponse)
def get_schedule(
    session_name: str = Query(default="Spring 2026", description="Academic session"),
    day: Optional[str] = Query(default=None, description="Filter by day (Monday, Tuesday, etc.)"),
    course_code: Optional[str] = Query(default=None, description="Filter by course code"),
    room: Optional[str] = Query(default=None, description="Filter by room"),
    program: Optional[str] = Query(default=None, description="Filter by program (BS, MPhil, etc.)"),
    semester: Optional[str] = Query(default=None, description="Filter by semester"),
    instructor: Optional[str] = Query(default=None, description="Filter by instructor name"),
    shift: Optional[str] = Query(default=None, description="Filter by shift (Morning, Afternoon, Evening)"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get timetable schedule with optional filters.
    Supports querying by day, course, room, program, semester, instructor, and shift.
    """
    
    # Build dynamic WHERE clause
    conditions = ["asess.session_name = :session_name", "cs.is_active = TRUE"]
    params = {"session_name": session_name}
    
    if day:
        conditions.append("cs.day_of_week = :day")
        params["day"] = day
    
    if course_code:
        conditions.append("UPPER(cs.course_code) = UPPER(:course_code)")
        params["course_code"] = course_code
    
    if room:
        conditions.append("cs.room ILIKE :room")
        params["room"] = f"%{room}%"
    
    if program:
        conditions.append("cs.program ILIKE :program")
        params["program"] = f"%{program}%"
    
    if semester:
        conditions.append("cs.semester ILIKE :semester")
        params["semester"] = f"%{semester}%"
    
    if instructor:
        conditions.append("EXISTS (SELECT 1 FROM course_schedule_instructors csi JOIN instructors i ON i.id = csi.instructor_id WHERE csi.course_schedule_id = cs.id AND i.name ILIKE :instructor)")
        params["instructor"] = f"%{instructor}%"
    
    if shift:
        conditions.append("cs.shift = :shift")
        params["shift"] = shift
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
        SELECT 
            cs.id,
            asess.session_name,
            cs.day_of_week,
            cs.time_slot,
            cs.shift,
            cs.room,
            cs.course_code,
            cs.course_abbreviation,
            cs.course_name,
            cs.credit_hours,
            cs.program,
            cs.semester,
            cs.section_type,
            COALESCE(
                array_agg(DISTINCT i.name ORDER BY i.name) FILTER (WHERE i.name IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) as instructors,
            COALESCE(
                array_agg(DISTINCT ta.name ORDER BY ta.name) FILTER (WHERE ta.name IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) as teaching_assistants
        FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
        LEFT JOIN instructors i ON csi.instructor_id = i.id
        LEFT JOIN course_schedule_tas csta ON cs.id = csta.course_schedule_id
        LEFT JOIN teaching_assistants ta ON csta.ta_id = ta.id
        WHERE {where_clause}
        GROUP BY 
            cs.id, asess.session_name, cs.day_of_week, cs.time_slot, cs.shift,
            cs.room, cs.course_code, cs.course_abbreviation, cs.course_name,
            cs.credit_hours, cs.program, cs.semester, cs.section_type
        ORDER BY 
            CASE cs.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END,
            cs.time_slot
    """
    
    rows = db.execute(text(query), params).mappings()
    entries = [dict(row) for row in rows]
    
    return {
        "session_name": session_name,
        "filters": {
            "day": day,
            "course_code": course_code,
            "room": room,
            "program": program,
            "semester": semester,
            "instructor": instructor,
            "shift": shift,
        },
        "total_entries": len(entries),
        "entries": entries,
    }


@router.get("/course/{course_code}", response_model=CourseScheduleDetail)
def get_course_schedule(
    course_code: str,
    session_name: str = Query(default="Spring 2026"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get complete schedule for a specific course including all sections.
    """
    
    query = """
        SELECT 
            cs.id,
            asess.session_name,
            cs.day_of_week,
            cs.time_slot,
            cs.shift,
            cs.room,
            cs.course_code,
            cs.course_abbreviation,
            cs.course_name,
            cs.credit_hours,
            cs.program,
            cs.semester,
            cs.section_type,
            COALESCE(
                array_agg(DISTINCT i.name ORDER BY i.name) FILTER (WHERE i.name IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) as instructors,
            COALESCE(
                array_agg(DISTINCT ta.name ORDER BY ta.name) FILTER (WHERE ta.name IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) as teaching_assistants
        FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
        LEFT JOIN instructors i ON csi.instructor_id = i.id
        LEFT JOIN course_schedule_tas csta ON cs.id = csta.course_schedule_id
        LEFT JOIN teaching_assistants ta ON csta.ta_id = ta.id
        WHERE UPPER(cs.course_code) = UPPER(:course_code)
            AND asess.session_name = :session_name
            AND cs.is_active = TRUE
        GROUP BY 
            cs.id, asess.session_name, cs.day_of_week, cs.time_slot, cs.shift,
            cs.room, cs.course_code, cs.course_abbreviation, cs.course_name,
            cs.credit_hours, cs.program, cs.semester, cs.section_type
        ORDER BY 
            CASE cs.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END,
            cs.time_slot
    """
    
    rows = db.execute(
        text(query),
        {"course_code": course_code, "session_name": session_name}
    ).mappings()
    
    entries = [dict(row) for row in rows]
    
    if not entries:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule found for course {course_code} in {session_name}"
        )
    
    return {
        "course_code": course_code,
        "course_name": entries[0]["course_name"],
        "credit_hours": entries[0]["credit_hours"],
        "session_name": session_name,
        "schedules": entries,
    }


@router.get("/instructor/{instructor_name}", response_model=InstructorSchedule)
def get_instructor_schedule(
    instructor_name: str,
    session_name: str = Query(default="Spring 2026"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get complete teaching schedule for a specific instructor.
    """
    
    # First verify instructor exists
    instructor = db.execute(
        text("SELECT id, name, title FROM instructors WHERE name ILIKE :name"),
        {"name": f"%{instructor_name}%"}
    ).mappings().first()
    
    if not instructor:
        raise HTTPException(
            status_code=404,
            detail=f"Instructor '{instructor_name}' not found"
        )
    
    query = """
        SELECT 
            cs.day_of_week,
            cs.time_slot,
            cs.shift,
            cs.room,
            cs.course_code,
            cs.course_name,
            cs.program,
            cs.semester,
            cs.section_type
        FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
        JOIN instructors i ON csi.instructor_id = i.id
        WHERE i.id = :instructor_id
            AND asess.session_name = :session_name
            AND cs.is_active = TRUE
        ORDER BY 
            CASE cs.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END,
            cs.time_slot
    """
    
    rows = db.execute(
        text(query),
        {"instructor_id": instructor["id"], "session_name": session_name}
    ).mappings()
    
    schedules = [dict(row) for row in rows]
    
    return {
        "instructor_name": instructor["name"],
        "instructor_title": instructor["title"],
        "session_name": session_name,
        "total_classes": len(schedules),
        "schedules": schedules,
    }


@router.get("/room/{room_name}", response_model=RoomSchedule)
def get_room_schedule(
    room_name: str,
    session_name: str = Query(default="Spring 2026"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get utilization schedule for a specific room.
    """
    
    query = """
        SELECT 
            cs.day_of_week,
            cs.time_slot,
            cs.shift,
            cs.course_code,
            cs.course_name,
            cs.program,
            cs.section_type,
            COALESCE(
                array_agg(DISTINCT i.name ORDER BY i.name) FILTER (WHERE i.name IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) as instructors
        FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
        LEFT JOIN instructors i ON csi.instructor_id = i.id
        WHERE cs.room ILIKE :room
            AND asess.session_name = :session_name
            AND cs.is_active = TRUE
        GROUP BY 
            cs.day_of_week, cs.time_slot, cs.shift, cs.course_code,
            cs.course_name, cs.program, cs.section_type
        ORDER BY 
            CASE cs.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END,
            cs.time_slot
    """
    
    rows = db.execute(
        text(query),
        {"room": f"%{room_name}%", "session_name": session_name}
    ).mappings()
    
    schedules = [dict(row) for row in rows]
    
    if not schedules:
        raise HTTPException(
            status_code=404,
            detail=f"No schedule found for room '{room_name}' in {session_name}"
        )
    
    return {
        "room": room_name,
        "session_name": session_name,
        "total_slots": len(schedules),
        "schedules": schedules,
    }


@router.get("/day/{day_name}")
def get_day_schedule(
    day_name: str,
    session_name: str = Query(default="Spring 2026"),
    program: Optional[str] = None,
    db: Session = Depends(get_db),
) -> dict:
    """
    Get all classes scheduled for a specific day.
    """
    
    # Validate day name
    valid_days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    if day_name not in valid_days:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid day name. Must be one of: {', '.join(valid_days)}"
        )
    
    conditions = [
        "cs.day_of_week = :day",
        "asess.session_name = :session_name",
        "cs.is_active = TRUE"
    ]
    params = {"day": day_name, "session_name": session_name}
    
    if program:
        conditions.append("cs.program ILIKE :program")
        params["program"] = f"%{program}%"
    
    where_clause = " AND ".join(conditions)
    
    query = f"""
        SELECT 
            cs.time_slot,
            cs.shift,
            cs.room,
            cs.course_code,
            cs.course_name,
            cs.program,
            cs.semester,
            cs.section_type,
            COALESCE(
                array_agg(DISTINCT i.name ORDER BY i.name) FILTER (WHERE i.name IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) as instructors
        FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
        LEFT JOIN instructors i ON csi.instructor_id = i.id
        WHERE {where_clause}
        GROUP BY 
            cs.time_slot, cs.shift, cs.room, cs.course_code,
            cs.course_name, cs.program, cs.semester, cs.section_type
        ORDER BY cs.time_slot
    """
    
    rows = db.execute(text(query), params).mappings()
    schedules = [dict(row) for row in rows]
    
    return {
        "day": day_name,
        "session_name": session_name,
        "program_filter": program,
        "total_classes": len(schedules),
        "schedules": schedules,
    }


@router.get("/search")
def search_schedule(
    q: str = Query(description="Search query (course code, name, instructor, or room)"),
    session_name: str = Query(default="Spring 2026"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Search timetable by course code, course name, instructor name, or room.
    """
    
    query = """
        SELECT 
            cs.day_of_week,
            cs.time_slot,
            cs.shift,
            cs.room,
            cs.course_code,
            cs.course_abbreviation,
            cs.course_name,
            cs.program,
            cs.semester,
            cs.section_type,
            COALESCE(
                array_agg(DISTINCT i.name ORDER BY i.name) FILTER (WHERE i.name IS NOT NULL),
                ARRAY[]::VARCHAR[]
            ) as instructors
        FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
        LEFT JOIN instructors i ON csi.instructor_id = i.id
        WHERE asess.session_name = :session_name
            AND cs.is_active = TRUE
            AND (
                cs.course_code ILIKE :search
                OR cs.course_name ILIKE :search
                OR cs.course_abbreviation ILIKE :search
                OR cs.room ILIKE :search
                OR EXISTS (
                    SELECT 1 FROM course_schedule_instructors csi2
                    JOIN instructors i2 ON i2.id = csi2.instructor_id
                    WHERE csi2.course_schedule_id = cs.id
                        AND i2.name ILIKE :search
                )
            )
        GROUP BY 
            cs.day_of_week, cs.time_slot, cs.shift, cs.room, cs.course_code,
            cs.course_abbreviation, cs.course_name, cs.program, cs.semester, cs.section_type
        ORDER BY 
            CASE cs.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END,
            cs.time_slot
        LIMIT 50
    """
    
    rows = db.execute(
        text(query),
        {"session_name": session_name, "search": f"%{q}%"}
    ).mappings()
    
    results = [dict(row) for row in rows]
    
    return {
        "query": q,
        "session_name": session_name,
        "results_count": len(results),
        "results": results,
    }


@router.get("/instructors")
def list_instructors(
    active_only: bool = True,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Get list of all instructors.
    """
    
    query = """
        SELECT 
            id,
            name,
            title,
            email,
            department,
            is_active
        FROM instructors
        WHERE (:active_only = FALSE OR is_active = TRUE)
        ORDER BY name
    """
    
    rows = db.execute(text(query), {"active_only": active_only}).mappings()
    return [dict(row) for row in rows]


@router.get("/rooms")
def list_rooms(
    session_name: str = Query(default="Spring 2026"),
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    Get list of all rooms in use for a session with utilization count.
    """
    
    query = """
        SELECT 
            cs.room,
            COUNT(*) as class_count,
            array_agg(DISTINCT cs.shift ORDER BY cs.shift) as shifts_used
        FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        WHERE asess.session_name = :session_name
            AND cs.is_active = TRUE
        GROUP BY cs.room
        ORDER BY cs.room
    """
    
    rows = db.execute(text(query), {"session_name": session_name}).mappings()
    return [dict(row) for row in rows]


@router.get("/stats")
def get_timetable_stats(
    session_name: str = Query(default="Spring 2026"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Get statistics about the timetable.
    """
    
    stats_query = """
        SELECT 
            COUNT(DISTINCT cs.course_code) as unique_courses,
            COUNT(*) as total_schedule_entries,
            COUNT(DISTINCT cs.room) as rooms_used,
            COUNT(DISTINCT csi.instructor_id) as instructors_count,
            COUNT(DISTINCT cs.program) as programs_count,
            COUNT(CASE WHEN cs.shift = 'Morning' THEN 1 END) as morning_classes,
            COUNT(CASE WHEN cs.shift = 'Afternoon' THEN 1 END) as afternoon_classes,
            COUNT(CASE WHEN cs.shift = 'Evening' THEN 1 END) as evening_classes
        FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        LEFT JOIN course_schedule_instructors csi ON cs.id = csi.course_schedule_id
        WHERE asess.session_name = :session_name
            AND cs.is_active = TRUE
    """
    
    stats = db.execute(text(stats_query), {"session_name": session_name}).mappings().first()
    
    # Get per-day breakdown
    day_query = """
        SELECT 
            cs.day_of_week,
            COUNT(*) as class_count
        FROM course_schedules cs
        JOIN academic_sessions asess ON cs.academic_session_id = asess.id
        WHERE asess.session_name = :session_name
            AND cs.is_active = TRUE
        GROUP BY cs.day_of_week
        ORDER BY 
            CASE cs.day_of_week
                WHEN 'Monday' THEN 1
                WHEN 'Tuesday' THEN 2
                WHEN 'Wednesday' THEN 3
                WHEN 'Thursday' THEN 4
                WHEN 'Friday' THEN 5
                WHEN 'Saturday' THEN 6
                WHEN 'Sunday' THEN 7
            END
    """
    
    day_breakdown = db.execute(text(day_query), {"session_name": session_name}).mappings()
    
    return {
        "session_name": session_name,
        "statistics": dict(stats),
        "by_day": [dict(row) for row in day_breakdown],
    }

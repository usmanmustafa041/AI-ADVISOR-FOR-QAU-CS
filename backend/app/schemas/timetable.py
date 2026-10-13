"""
Pydantic schemas for timetable API responses.
"""

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class SessionInfo(BaseModel):
    """Academic session information."""

    id: UUID
    session_name: str
    effective_from: date
    effective_to: Optional[date] = None
    is_current: bool
    created_at: datetime
    updated_at: datetime


class TimetableEntry(BaseModel):
    """Single timetable schedule entry."""

    id: UUID
    session_name: str
    day_of_week: str
    time_slot: str
    shift: str
    room: str
    course_code: str
    course_abbreviation: Optional[str] = None
    course_name: str
    credit_hours: str
    program: str
    semester: str
    section_type: str
    instructors: list[str] = Field(default_factory=list)
    teaching_assistants: list[str] = Field(default_factory=list)


class TimetableResponse(BaseModel):
    """Response for timetable queries with filters."""

    session_name: str
    filters: dict
    total_entries: int
    entries: list[dict]


class CourseScheduleDetail(BaseModel):
    """Complete schedule details for a course."""

    course_code: str
    course_name: str
    credit_hours: str
    session_name: str
    schedules: list[dict]


class InstructorSchedule(BaseModel):
    """Complete teaching schedule for an instructor."""

    instructor_name: str
    instructor_title: Optional[str] = None
    session_name: str
    total_classes: int
    schedules: list[dict]


class RoomSchedule(BaseModel):
    """Room utilization schedule."""

    room: str
    session_name: str
    total_slots: int
    schedules: list[dict]


class InstructorInfo(BaseModel):
    """Instructor information."""

    id: UUID
    name: str
    title: Optional[str] = None
    email: Optional[str] = None
    department: str
    is_active: bool


class RoomInfo(BaseModel):
    """Room information with usage statistics."""

    room: str
    class_count: int
    shifts_used: list[str]


class TimetableStats(BaseModel):
    """Timetable statistics."""

    session_name: str
    statistics: dict
    by_day: list[dict]

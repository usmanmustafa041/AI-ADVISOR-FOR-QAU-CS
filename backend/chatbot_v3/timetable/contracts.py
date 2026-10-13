from datetime import date, time, timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UploadMetadata(Contract):
    department: str = Field(default="CS", min_length=1, max_length=60)
    campus: str = Field(default="QAU", min_length=1, max_length=60)
    academic_term: str = Field(pattern=r"^(Spring|Summer|Fall) 20\d{2}$")
    kind: Literal["classes", "exams"] = "classes"
    programmes: list[str] = Field(min_length=1, max_length=12)
    time_zone: Literal["Asia/Karachi"] = "Asia/Karachi"
    effective_from: date
    effective_until: date | None = None
    origin: Literal["admin provided", "official URL"] = "admin provided"
    source_url: str | None = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def valid_dates(self):
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("Effective end precedes start")
        allowed = {"BSCS", "MPhil", "PhD", "MS-DS", "MS-IST", "deficiency"}
        if not set(self.programmes) <= allowed:
            raise ValueError("Unknown programme coverage")
        self.programmes = sorted(set(self.programmes))
        if self.origin == "official URL":
            from urllib.parse import urlsplit

            u = urlsplit(self.source_url or "")
            if u.scheme != "https" or u.hostname not in {
                "qau.edu.pk",
                "cs.qau.edu.pk",
                "www.qau.edu.pk",
            }:
                raise ValueError("Official URL must identify a configured university host")
        return self


class TimetableQuery(Contract):
    operation: Literal[
        "list_classes",
        "count_meetings",
        "next_class",
        "class_details",
        "teacher_schedule",
        "course_schedule",
        "room_schedule",
        "free_room_intervals",
        "days_with_classes",
        "compare_sections",
        "weekly_load",
        "find_conflicts",
        "historical_comparison",
    ] = "list_classes"
    department: str = "CS"
    campus: str = "QAU"
    kind: Literal["classes", "exams"] = "classes"
    academic_term: str | None = None
    version_id: str | None = None
    compare_version_id: str | None = None
    historical: bool = False
    programme: str | None = None
    semester: int | None = Field(default=None, ge=1, le=12)
    section: Literal["regular", "self support", "combined", "unknown"] | None = None
    weekday: (
        Literal["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] | None
    ) = None
    on_date: date | None = None
    relative_day: Literal["today", "tomorrow"] | None = None
    at_time: time | None = None
    until_time: time | None = None
    ongoing: bool = False
    course: str | None = Field(default=None, max_length=150)
    teacher: str | None = Field(default=None, max_length=150)
    room: str | None = Field(default=None, max_length=80)
    mode: Literal["online", "physical"] | None = None

    @field_validator("at_time", "until_time")
    @classmethod
    def local_time(cls, value):
        if value and value.tzinfo:
            if value.utcoffset() != timedelta(hours=5):
                raise ValueError("Timetable clock times use Asia/Karachi (+05:00)")
            value = value.replace(tzinfo=None)
        return value


class ReviewAction(Contract):
    expected_revision: int
    reason: str = Field(min_length=5, max_length=2000)


class PublishAction(ReviewAction):
    expected_active_version: str | None = None
    reviewed_pages: list[int] = Field(min_length=1)
    confirm_complete: bool


class RowEdit(ReviewAction):
    changes: dict


class CurrentTerm(Contract):
    department: str = "CS"
    campus: str = "QAU"
    academic_term: str = Field(pattern=r"^(Spring|Summer|Fall) 20\d{2}$")
    valid_from: date
    valid_until: date
    reason: str = Field(min_length=5)

    @model_validator(mode="after")
    def ordered(self):
        if self.valid_until < self.valid_from:
            raise ValueError("Invalid current-term interval")
        return self

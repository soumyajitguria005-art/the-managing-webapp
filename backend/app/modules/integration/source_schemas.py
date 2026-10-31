"""Strict Pydantic contract for the organiser's cit_public.json source format.

This models the source contract; it intentionally does not infer fields from CSVs.
"""
from __future__ import annotations
from datetime import datetime, time
from pydantic import BaseModel, ConfigDict, Field, model_validator

class SourceModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

class Period(SourceModel):
    id: int = Field(gt=0)
    start: time
    end: time
    teaching: bool

class Lunch(SourceModel):
    after_period: int = Field(gt=0)
    start: time
    end: time

class ExamSession(SourceModel):
    id: str
    start: time
    end: time

class ExamWeek(SourceModel):
    days: list[str]
    sessions: list[ExamSession]

class Calendar(SourceModel):
    days: list[str]
    periods: list[Period]
    lunch: Lunch
    lab_start_periods: list[int]
    event_only_periods: list[int]
    fest_week: str
    exam_week: ExamWeek

class Room(SourceModel):
    id: str
    name: str
    building: str | None
    type: str
    capacity: int = Field(gt=0)
    features: list[str]
    accessible: bool
    allowed_uses: list[str]

class PeriodUnavailability(SourceModel):
    day: str
    periods: list[int]
    reason: str | None = None

class RoomUnavailability(SourceModel):
    room_id: str
    day: str
    periods: list[int]
    reason: str | None = None

class Preference(SourceModel):
    type: str
    note: str | None = None
    days: list[str] = Field(default_factory=list)
    periods: list[int] = Field(default_factory=list)

class Faculty(SourceModel):
    id: str
    name: str
    department: str
    max_hours_per_day: float = Field(gt=0)
    needs_accessible: bool
    unavailable: list[PeriodUnavailability]
    preferences: list[Preference]

class StudentGroup(SourceModel):
    id: str
    name: str
    year: int | None
    department: str
    size: int = Field(gt=0)
    needs_accessible: bool

class Course(SourceModel):
    id: str
    title: str
    department: str
    year: int | None
    lecture_hours: float = Field(ge=0)
    tutorial_hours: float = Field(ge=0)
    lab_blocks: float = Field(ge=0)

class FixedSlot(SourceModel):
    day: str
    start_period: int = Field(gt=0)

class TeachingSessionSource(SourceModel):
    id: str
    course_id: str
    kind: str
    groups: list[str]
    faculty_id: str
    size: int = Field(gt=0)
    duration: int = Field(gt=0)
    room_types: list[str]
    needs_accessible: bool
    basket_slot: str | None
    fixed_slot: FixedSlot | None

class BookingWindow(SourceModel):
    day: str
    from_period: int = Field(gt=0)
    to_period: int = Field(gt=0)

class BookingRequest(SourceModel):
    id: str
    submitted_at: datetime
    requester: str
    role: str
    department: str | None
    requested_category: str
    title: str
    attendance: int = Field(gt=0)
    duration_periods: int = Field(gt=0)
    windows: list[BookingWindow]
    room_types: list[str]
    needs: list[str]
    requested_room: str | None
    mandatory_for_groups: list[str]
    series_id: str | None
    raw_text: str

class Cancellation(SourceModel):
    request_id: str
    cancelled_at: datetime
    by: str
    note: str

class Exam(SourceModel):
    id: str
    course_ids: list[str]
    groups: list[str]
    size: int = Field(gt=0)
    duration_hours: float = Field(gt=0)

class SourceDataset(SourceModel):
    dataset_id: str
    institute: str
    calendar: Calendar
    priority_order: list[str]
    role_category_cap: dict[str, str]
    rooms: list[Room]
    room_unavailability: list[RoomUnavailability]
    faculty: list[Faculty]
    student_groups: list[StudentGroup]
    courses: list[Course]
    sessions: list[TeachingSessionSource]
    booking_requests: list[BookingRequest]
    cancellations: list[Cancellation]
    exams: list[Exam]

    @model_validator(mode="after")
    def validate_references_and_uniqueness(self):
        def unique(values: list[str], label: str):
            if len(values) != len(set(values)):
                raise ValueError(f"duplicate {label} identifiers")
        unique([x.id for x in self.rooms], "room")
        unique([x.id for x in self.faculty], "faculty")
        unique([x.id for x in self.student_groups], "student group")
        unique([x.id for x in self.courses], "course")
        unique([x.id for x in self.sessions], "session")
        unique([x.id for x in self.booking_requests], "booking request")
        unique([x.id for x in self.exams], "exam")
        room_ids = {x.id for x in self.rooms}
        faculty_ids = {x.id for x in self.faculty}
        group_ids = {x.id for x in self.student_groups}
        course_ids = {x.id for x in self.courses}
        request_ids = {x.id for x in self.booking_requests}
        day_codes = set(self.calendar.days)
        period_ids = {x.id for x in self.calendar.periods}
        if self.calendar.lunch.after_period not in period_ids:
            raise ValueError(f"lunch after_period {self.calendar.lunch.after_period} is not in calendar periods")
        if set(self.calendar.lab_start_periods) - period_ids:
            raise ValueError(f"lab_start_periods {set(self.calendar.lab_start_periods) - period_ids} not in calendar periods")
        if set(self.calendar.event_only_periods) - period_ids:
            raise ValueError(f"event_only_periods {set(self.calendar.event_only_periods) - period_ids} not in calendar periods")
        for role, cap in self.role_category_cap.items():
            if cap not in self.priority_order:
                raise ValueError(f"role {role} cap '{cap}' not found in priority_order {self.priority_order}")
        for item in self.sessions:
            if item.course_id not in course_ids: raise ValueError(f"session {item.id}: unknown course {item.course_id}")
            if item.faculty_id not in faculty_ids: raise ValueError(f"session {item.id}: unknown faculty {item.faculty_id}")
            missing = set(item.groups) - group_ids
            if missing: raise ValueError(f"session {item.id}: unknown groups {sorted(missing)}")
            if item.fixed_slot and item.fixed_slot.day not in day_codes: raise ValueError(f"session {item.id}: invalid fixed day")
            if item.fixed_slot and item.fixed_slot.start_period not in period_ids: raise ValueError(f"session {item.id}: invalid fixed start period")
        for item in self.room_unavailability:
            if item.room_id not in room_ids: raise ValueError(f"room unavailability: unknown room {item.room_id}")
            if item.day not in day_codes: raise ValueError(f"room unavailability: invalid day {item.day}")
            if set(item.periods) - period_ids: raise ValueError(f"room unavailability: invalid periods for {item.room_id}")
        for item in self.faculty:
            for u in item.unavailable:
                if u.day not in day_codes or set(u.periods) - period_ids: raise ValueError(f"faculty {item.id}: invalid unavailability")
            for p in item.preferences:
                if p.days and (set(p.days) - day_codes): raise ValueError(f"faculty {item.id}: invalid preference days")
                if p.periods and (set(p.periods) - period_ids): raise ValueError(f"faculty {item.id}: invalid preference periods")
        for item in self.booking_requests:
            for w in item.windows:
                if w.day not in day_codes or w.to_period < w.from_period: raise ValueError(f"booking {item.id}: invalid window")
            missing = set(item.mandatory_for_groups) - group_ids
            if missing: raise ValueError(f"booking {item.id}: unknown mandatory groups {sorted(missing)}")
        for item in self.cancellations:
            if item.request_id not in request_ids: raise ValueError(f"cancellation: unknown booking {item.request_id}")
        exam_days = set(self.calendar.exam_week.days)
        for item in self.exams:
            if set(item.course_ids) - course_ids: raise ValueError(f"exam {item.id}: unknown courses")
            if set(item.groups) - group_ids: raise ValueError(f"exam {item.id}: unknown groups")
        return self

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ClassCreate(BaseModel):
    grade: str = Field(min_length=1, max_length=20, examples=["5"])
    section: str = Field(default="", max_length=10, examples=["A"])
    academic_year: str = Field(pattern=r"^\d{4}-\d{2}$", examples=["2026-27"])


class ClassOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    grade: str
    section: str
    academic_year: str
    student_count: int = 0
    created_at: datetime


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_id: int
    upload_id: int | None
    upload_row: int | None
    first_name: str
    last_name: str
    date_of_birth: date | None
    parent_email: str | None
    created_at: datetime


class FlaggedRowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    row_number: int
    reason: str
    values: dict[str, Any]


class UploadSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    class_id: int
    filename: str
    status: str
    total_rows: int
    inserted_count: int
    flagged_count: int
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class UploadOut(UploadSummary):
    agent_stats: dict[str, Any] | None
    columns: list[str]
    preview: list[dict[str, Any]]
    flagged_rows: list[FlaggedRowOut]


class ProcessRequest(BaseModel):
    instructions: str | None = Field(
        default=None,
        max_length=1000,
        description="Optional notes for the AI, e.g. 'dates are month/day/year'.",
    )

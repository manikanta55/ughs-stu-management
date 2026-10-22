from datetime import date, datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class SchoolClass(Base):
    """A class (grade + section) for one academic year, e.g. Grade 5-A, 2026-27."""

    __tablename__ = "classes"
    __table_args__ = (UniqueConstraint("grade", "section", "academic_year"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    grade: Mapped[str] = mapped_column(String(20))
    section: Mapped[str] = mapped_column(String(10), server_default="")
    academic_year: Mapped[str] = mapped_column(String(9))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # passive_deletes="all": let the DB's ON DELETE RESTRICT decide, never null out students.
    students: Mapped[list["Student"]] = relationship(
        back_populates="school_class", passive_deletes="all"
    )


class Student(Base):
    __tablename__ = "students"
    # A spreadsheet row can produce at most one student (NULLs are distinct, so manual adds are fine).
    __table_args__ = (UniqueConstraint("upload_id", "upload_row"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    # RESTRICT: a class with students cannot be deleted by accident.
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="RESTRICT"), index=True)
    # Which roster upload created this student (None for students added another way).
    upload_id: Mapped[int | None] = mapped_column(
        ForeignKey("roster_uploads.id", ondelete="SET NULL"), index=True
    )
    upload_row: Mapped[int | None] = mapped_column(Integer)  # spreadsheet row it came from
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    date_of_birth: Mapped[date | None] = mapped_column(Date)
    parent_email: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    school_class: Mapped[SchoolClass] = relationship(back_populates="students")


class UploadStatus(StrEnum):
    PARSED = "parsed"  # file read; waiting for the agent
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class RosterUpload(Base):
    """One uploaded roster file. Parsed rows are kept here so the file itself is never stored."""

    __tablename__ = "roster_uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(20), default=UploadStatus.PARSED)
    # Headers as written in the file, and rows as [{"row": <spreadsheet row>, "values": {...}}].
    columns: Mapped[list[str]] = mapped_column(JSONB)
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    total_rows: Mapped[int] = mapped_column(Integer)
    inserted_count: Mapped[int] = mapped_column(Integer, default=0)
    flagged_count: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[str | None] = mapped_column(Text)
    # Turns, tool calls and token usage of the last agent run, for cost tracking.
    agent_stats: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    school_class: Mapped[SchoolClass] = relationship()
    flagged_rows: Mapped[list["FlaggedRow"]] = relationship(
        back_populates="upload",
        cascade="all, delete-orphan",
        order_by="FlaggedRow.row_number",
    )

    @property
    def preview(self) -> list[dict[str, Any]]:
        return self.rows[:5]


class FlaggedRow(Base):
    """A row the agent could not turn into a valid student, with the reason shown to the teacher."""

    __tablename__ = "flagged_rows"
    __table_args__ = (UniqueConstraint("upload_id", "row_number"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    upload_id: Mapped[int] = mapped_column(
        ForeignKey("roster_uploads.id", ondelete="CASCADE"), index=True
    )
    row_number: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str] = mapped_column(Text)
    values: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    upload: Mapped[RosterUpload] = relationship(back_populates="flagged_rows")

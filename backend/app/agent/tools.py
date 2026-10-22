"""The tools the roster agent may call (plan section 3).

The agent never touches the database directly. It can read the target schema, insert one
validated student for a spreadsheet row, or flag a row it can't salvage. Every input is
validated here; a failure is returned to the agent as data so it can correct itself.
"""

import re
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field, ValidationError, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import FlaggedRow, RosterUpload, Student

ToolResult = dict[str, Any]

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_EARLIEST_DOB = date(1950, 1, 1)


class StudentRecord(BaseModel):
    """The shape the agent must produce for each student. Also drives get_class_schema()."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    first_name: str = Field(min_length=1, max_length=100, description="Given name, e.g. 'Asha'.")
    last_name: str = Field(
        min_length=1, max_length=100, description="Family name / surname, e.g. 'Rao'."
    )
    date_of_birth: date | None = Field(
        default=None, description="Date of birth as YYYY-MM-DD. null if missing."
    )
    parent_email: EmailStr | None = Field(
        default=None, description="Parent or guardian email address. null if missing."
    )

    @field_validator("parent_email", mode="before")
    @classmethod
    def _blank_email_is_none(cls, value: Any) -> Any:
        return None if isinstance(value, str) and not value.strip() else value

    @field_validator("date_of_birth", mode="before")
    @classmethod
    def _iso_date_only(cls, value: Any) -> Any:
        if isinstance(value, str) and not value.strip():
            return None
        # Pydantic would also accept timestamps and datetimes; insist on the agreed format.
        if value is not None and not (isinstance(value, str) and _ISO_DATE.match(value.strip())):
            raise ValueError("must be a YYYY-MM-DD string")
        return value

    @field_validator("date_of_birth")
    @classmethod
    def _plausible_date(cls, value: date | None) -> date | None:
        if value is not None and not (_EARLIEST_DOB <= value < date.today()):
            raise ValueError(f"{value.isoformat()} is not a plausible date of birth")
        return value

    @field_validator("parent_email")
    @classmethod
    def _lowercase_email(cls, value: str | None) -> str | None:
        return value.lower() if value else value


_NULLABLE_STRING = {"type": ["string", "null"]}

# Definitions sent to Claude. strict=True guarantees the arguments match these schemas;
# StudentRecord still validates the values (formats, real dates, valid emails).
TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "name": "get_class_schema",
        "description": (
            "Get the target class and the student fields the database requires, "
            "with their formats. Call this before inserting anything."
        ),
        "strict": True,
        "input_schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "insert_student_record",
        "description": (
            "Insert one student built from one spreadsheet row. Returns ok=false with details "
            "if a value is invalid; nothing is written in that case."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "row_number": {"type": "integer", "description": "The row's _row value."},
                "student_data": {
                    "type": "object",
                    "properties": {
                        "first_name": {"type": "string"},
                        "last_name": {"type": "string"},
                        "date_of_birth": {**_NULLABLE_STRING, "description": "YYYY-MM-DD"},
                        "parent_email": _NULLABLE_STRING,
                    },
                    "required": ["first_name", "last_name", "date_of_birth", "parent_email"],
                    "additionalProperties": False,
                },
            },
            "required": ["row_number", "student_data"],
            "additionalProperties": False,
        },
    },
    {
        "name": "flag_invalid_row",
        "description": (
            "Mark a row that cannot become a valid student. The reason is shown to the teacher, "
            "so make it specific and actionable."
        ),
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "row_number": {"type": "integer", "description": "The row's _row value."},
                "error_reason": {"type": "string"},
            },
            "required": ["row_number", "error_reason"],
            "additionalProperties": False,
        },
    },
]


def _validation_messages(exc: ValidationError) -> list[str]:
    return [f"{'.'.join(map(str, e['loc'])) or 'student_data'}: {e['msg']}" for e in exc.errors()]


class RosterToolbox:
    """Tools bound to one upload. Writes are flushed, not committed; the caller commits."""

    def __init__(self, db: Session, upload: RosterUpload):
        self.db = db
        self.upload = upload
        self._rows: dict[int, dict[str, str]] = {r["row"]: r["values"] for r in upload.rows}

    # --- Tool 1 -------------------------------------------------------------------------
    def get_class_schema(self) -> ToolResult:
        school_class = self.upload.school_class
        fields = {
            name: {
                "required": info.is_required(),
                "description": info.description,
            }
            for name, info in StudentRecord.model_fields.items()
        }
        return {
            "ok": True,
            "class": {
                "grade": school_class.grade,
                "section": school_class.section,
                "academic_year": school_class.academic_year,
            },
            "fields": fields,
            "rules": [
                "Every student in this file belongs to the class above; do not set a class.",
                "Handle each row exactly once: insert it or flag it.",
                "Do not include any fields other than those listed.",
            ],
        }

    # --- Tool 2 -------------------------------------------------------------------------
    def insert_student_record(self, row_number: int, student_data: dict[str, Any]) -> ToolResult:
        if error := self._check_row(row_number):
            return error
        if not isinstance(student_data, dict):
            return self._error(row_number, "student_data must be an object")
        try:
            record = StudentRecord.model_validate(student_data)
        except ValidationError as exc:
            return self._error(
                row_number,
                "student_data failed validation; fix the values or flag the row",
                _validation_messages(exc),
            )

        student = Student(
            class_id=self.upload.class_id,
            upload_id=self.upload.id,
            upload_row=row_number,
            **record.model_dump(),
        )
        self.db.add(student)
        self.upload.inserted_count += 1
        self.db.flush()
        return {"ok": True, "row_number": row_number, "student_id": student.id}

    # --- Tool 3 -------------------------------------------------------------------------
    def flag_invalid_row(self, row_number: int, error_reason: str) -> ToolResult:
        if error := self._check_row(row_number):
            return error
        reason = error_reason.strip() if isinstance(error_reason, str) else ""
        if not reason:
            return self._error(row_number, "error_reason must explain why the row is invalid")

        self.db.add(
            FlaggedRow(
                upload_id=self.upload.id,
                row_number=row_number,
                reason=reason,
                values=self._rows[row_number],
            )
        )
        self.upload.flagged_count += 1
        self.db.flush()
        return {"ok": True, "row_number": row_number, "flagged": True}

    # --- Used by the agent loop ---------------------------------------------------------
    def call(self, name: str, tool_input: dict[str, Any]) -> ToolResult:
        """Dispatch a tool call by name. Bad names or arguments come back as errors, not raises."""
        tools = {
            "get_class_schema": self.get_class_schema,
            "insert_student_record": self.insert_student_record,
            "flag_invalid_row": self.flag_invalid_row,
        }
        tool = tools.get(name)
        if tool is None:
            return {"ok": False, "error": f"Unknown tool '{name}'"}
        try:
            return tool(**tool_input)
        except TypeError as exc:
            return {"ok": False, "error": f"Invalid arguments for {name}: {exc}"}

    def handled_rows(self) -> set[int]:
        inserted = self.db.scalars(
            select(Student.upload_row).where(Student.upload_id == self.upload.id)
        )
        flagged = self.db.scalars(
            select(FlaggedRow.row_number).where(FlaggedRow.upload_id == self.upload.id)
        )
        return {*inserted, *flagged}

    def unhandled_rows(self) -> list[int]:
        return sorted(self._rows.keys() - self.handled_rows())

    def _check_row(self, row_number: Any) -> ToolResult | None:
        if not isinstance(row_number, int) or isinstance(row_number, bool):
            return {"ok": False, "error": "row_number must be an integer"}
        if row_number not in self._rows:
            return self._error(row_number, "no such row in this upload")
        if row_number in self.handled_rows():
            return self._error(row_number, "row was already inserted or flagged")
        return None

    @staticmethod
    def _error(row_number: int, message: str, details: list[str] | None = None) -> ToolResult:
        result: ToolResult = {"ok": False, "row_number": row_number, "error": message}
        if details:
            result["details"] = details
        return result

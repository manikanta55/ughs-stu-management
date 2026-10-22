from datetime import date
from pathlib import Path

import pytest

from app.agent.tools import RosterToolbox
from app.config import get_settings
from app.db import SessionLocal
from app.models import FlaggedRow, RosterUpload, SchoolClass, Student, UploadStatus
from app.services.roster_parser import parse_roster

SAMPLE = Path(__file__).parents[1] / "samples" / "messy_roster_5a.csv"
ASHA = {
    "first_name": "Asha",
    "last_name": "Rao",
    "date_of_birth": "2016-04-02",
    "parent_email": "asha.parent@example.com",
}


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def toolbox(db) -> RosterToolbox:
    school_class = SchoolClass(grade="5", section="A", academic_year="2026-27")
    db.add(school_class)
    db.flush()
    roster = parse_roster(SAMPLE.name, SAMPLE.read_bytes(), get_settings().max_upload_rows)
    upload = RosterUpload(
        class_id=school_class.id,
        filename=SAMPLE.name,
        status=UploadStatus.PROCESSING,
        columns=roster.columns,
        rows=roster.rows_json(),
        total_rows=len(roster.rows),
        inserted_count=0,
        flagged_count=0,
    )
    db.add(upload)
    db.commit()
    return RosterToolbox(db, upload)


def test_sample_rows(toolbox):
    # Spreadsheet rows 5-9 and 11 hold students; 10 is blank, 1-4 are title/header.
    assert toolbox.unhandled_rows() == [5, 6, 7, 8, 9, 11]


def test_get_class_schema(toolbox):
    schema = toolbox.get_class_schema()
    assert schema["class"] == {"grade": "5", "section": "A", "academic_year": "2026-27"}
    assert schema["fields"]["first_name"]["required"] is True
    assert schema["fields"]["date_of_birth"]["required"] is False
    assert "YYYY-MM-DD" in schema["fields"]["date_of_birth"]["description"]


def test_insert_valid_student(toolbox, db):
    result = toolbox.insert_student_record(5, ASHA)
    assert result["ok"] is True
    student = db.get(Student, result["student_id"])
    assert (student.first_name, student.date_of_birth) == ("Asha", date(2016, 4, 2))
    assert student.class_id == toolbox.upload.class_id
    assert (student.upload_id, student.upload_row) == (toolbox.upload.id, 5)
    assert toolbox.upload.inserted_count == 1
    assert 5 not in toolbox.unhandled_rows()


def test_insert_normalizes_values(toolbox, db):
    result = toolbox.insert_student_record(
        9,
        {
            "first_name": "  John ",
            "last_name": "D'Souza",
            "date_of_birth": "",
            "parent_email": "JOHN.DSOUZA@EXAMPLE.COM",
        },
    )
    student = db.get(Student, result["student_id"])
    assert student.first_name == "John"
    assert student.date_of_birth is None
    assert student.parent_email == "john.dsouza@example.com"


def test_optional_fields_can_be_omitted(toolbox):
    result = toolbox.insert_student_record(5, {"first_name": "Asha", "last_name": "Rao"})
    assert result["ok"] is True


@pytest.mark.parametrize(
    ("student_data", "expected_detail"),
    [
        ({**ASHA, "first_name": ""}, "first_name"),
        ({k: v for k, v in ASHA.items() if k != "last_name"}, "last_name: Field required"),
        ({**ASHA, "date_of_birth": "2016-02-31"}, "date_of_birth"),
        ({**ASHA, "date_of_birth": "02/04/2016"}, "YYYY-MM-DD"),
        ({**ASHA, "date_of_birth": "2099-01-01"}, "not a plausible date of birth"),
        ({**ASHA, "parent_email": "ravi_dad@example"}, "parent_email"),
        ({**ASHA, "class_id": 99}, "class_id: Extra inputs are not permitted"),
    ],
)
def test_insert_rejects_invalid_data(toolbox, student_data, expected_detail):
    result = toolbox.insert_student_record(5, student_data)
    assert result["ok"] is False
    assert any(expected_detail in d for d in result["details"]), result
    # Nothing written; the agent can retry the same row.
    assert toolbox.upload.inserted_count == 0
    assert 5 in toolbox.unhandled_rows()


def test_flag_invalid_row_copies_original_values(toolbox, db):
    result = toolbox.flag_invalid_row(8, "Row has no student name")
    assert result == {"ok": True, "row_number": 8, "flagged": True}
    flagged = db.query(FlaggedRow).one()
    assert flagged.reason == "Row has no student name"
    assert flagged.values["S.No"] == "4"
    assert toolbox.upload.flagged_count == 1


def test_flag_requires_reason(toolbox):
    assert toolbox.flag_invalid_row(8, "   ")["ok"] is False


@pytest.mark.parametrize("first", ["insert", "flag"])
def test_each_row_is_handled_once(toolbox, first):
    if first == "insert":
        toolbox.insert_student_record(5, ASHA)
    else:
        toolbox.flag_invalid_row(5, "bad")
    assert "already" in toolbox.insert_student_record(5, ASHA)["error"]
    assert "already" in toolbox.flag_invalid_row(5, "bad")["error"]


@pytest.mark.parametrize("row_number", [1, 4, 10, 999, "5", True])
def test_rows_outside_the_data_are_rejected(toolbox, row_number):
    assert toolbox.insert_student_record(row_number, ASHA)["ok"] is False


def test_call_dispatches_and_reports_bad_calls(toolbox):
    assert toolbox.call("get_class_schema", {})["ok"] is True
    assert toolbox.call("insert_student_record", {"row_number": 5, "student_data": ASHA})["ok"]
    assert "Unknown tool" in toolbox.call("drop_table", {})["error"]
    assert "Invalid arguments" in toolbox.call("flag_invalid_row", {"row": 6})["error"]


def test_all_rows_handled(toolbox):
    toolbox.insert_student_record(5, ASHA)
    toolbox.insert_student_record(6, {"first_name": "Ravi", "last_name": "Kumar"})
    toolbox.insert_student_record(7, {"first_name": "Meena", "last_name": "Meena"})
    toolbox.flag_invalid_row(8, "No student name")
    toolbox.insert_student_record(9, {"first_name": "John", "last_name": "D'Souza"})
    toolbox.flag_invalid_row(11, "Date of birth 31/02/2016 does not exist")
    assert toolbox.unhandled_rows() == []
    assert (toolbox.upload.inserted_count, toolbox.upload.flagged_count) == (4, 2)

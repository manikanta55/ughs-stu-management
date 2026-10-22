import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.agent import runner
from app.agent.tools import TOOL_DEFINITIONS, StudentRecord
from app.config import get_settings
from app.db import SessionLocal
from app.models import RosterUpload, SchoolClass, Student, UploadStatus
from app.services.roster_parser import parse_roster

SAMPLE = Path(__file__).parents[1] / "samples" / "messy_roster_5a.csv"
ALL_ROWS = [5, 6, 7, 8, 9, 11]


def tool_use(name, tool_input, id_=None):
    return SimpleNamespace(
        type="tool_use",
        id=id_ or f"tu_{name}_{json.dumps(tool_input)}",
        name=name,
        input=tool_input,
    )


def insert(row, first="A", last="B"):
    return tool_use(
        "insert_student_record",
        {
            "row_number": row,
            "student_data": {
                "first_name": first,
                "last_name": last,
                "date_of_birth": None,
                "parent_email": None,
            },
        },
    )


def flag(row, reason="bad row"):
    return tool_use("flag_invalid_row", {"row_number": row, "error_reason": reason})


def reply(*blocks, stop_reason=None):
    blocks = blocks or (SimpleNamespace(type="text", text="Done."),)
    has_tools = any(b.type == "tool_use" for b in blocks)
    usage = SimpleNamespace(
        input_tokens=100,
        output_tokens=10,
        cache_creation_input_tokens=0,
        cache_read_input_tokens=50,
    )
    return SimpleNamespace(
        content=list(blocks),
        usage=usage,
        stop_reason=stop_reason or ("tool_use" if has_tools else "end_turn"),
    )


class FakeClient:
    """Returns scripted responses and records each request's messages."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.requests.append(json.loads(json.dumps(kwargs["messages"], default=vars)))
        if not self.responses:
            raise AssertionError("Agent made more requests than scripted")
        return self.responses.pop(0)


@pytest.fixture
def upload_id() -> int:
    with SessionLocal() as db:
        school_class = SchoolClass(grade="5", section="A", academic_year="2026-27")
        db.add(school_class)
        db.flush()
        roster = parse_roster(SAMPLE.name, SAMPLE.read_bytes(), 100)
        upload = RosterUpload(
            class_id=school_class.id,
            filename=SAMPLE.name,
            status=UploadStatus.PARSED,
            columns=roster.columns,
            rows=roster.rows_json(),
            total_rows=len(roster.rows),
            inserted_count=0,
            flagged_count=0,
        )
        db.add(upload)
        db.commit()
        return upload.id


def run(upload_id, responses) -> tuple[RosterUpload, FakeClient]:
    client = FakeClient(responses)
    with SessionLocal() as db:
        assert runner.claim_upload(db, upload_id)
    runner.run_agent(upload_id, client=client)
    with SessionLocal() as db:
        return db.get(RosterUpload, upload_id), client


def handle_all():
    return reply(*[insert(r) for r in ALL_ROWS if r != 8], flag(8, "No student name"))


def test_tool_definitions_match_toolbox():
    names = [t["name"] for t in TOOL_DEFINITIONS]
    assert names == ["get_class_schema", "insert_student_record", "flag_invalid_row"]
    student_schema = TOOL_DEFINITIONS[1]["input_schema"]["properties"]["student_data"]
    assert set(student_schema["properties"]) == set(StudentRecord.model_fields)


def test_happy_path(upload_id):
    upload, client = run(
        upload_id,
        [
            reply(tool_use("get_class_schema", {})),
            handle_all(),
            reply(),
        ],
    )
    assert upload.status == UploadStatus.COMPLETED
    assert (upload.inserted_count, upload.flagged_count) == (5, 1)
    assert upload.error_message is None
    assert upload.agent_stats["turns"] == 3
    assert upload.agent_stats["tool_calls"] == 7
    assert upload.agent_stats["usage"]["cache_read_input_tokens"] == 150
    # First message carries the rows as data, tool results come back in one user message.
    assert '"_row": 5' in client.requests[0][0]["content"]
    assert "<roster_rows>" in client.requests[0][0]["content"]
    results = client.requests[2][-1]["content"]
    assert len(results) == 6 and all(r["type"] == "tool_result" for r in results)


def test_tool_errors_are_returned_to_the_agent(upload_id):
    bad = tool_use(
        "insert_student_record",
        {
            "row_number": 5,
            "student_data": {
                "first_name": "Asha",
                "last_name": "Rao",
                "date_of_birth": "02/04/2016",
                "parent_email": None,
            },
        },
    )
    upload, client = run(upload_id, [reply(bad), handle_all(), reply()])
    result = client.requests[1][-1]["content"][0]
    assert result["is_error"] is True
    assert "YYYY-MM-DD" in result["content"]
    assert upload.status == UploadStatus.COMPLETED


def test_nudges_when_rows_are_left_unhandled(upload_id):
    upload, client = run(
        upload_id,
        [
            reply(insert(5), insert(6)),
            reply(),  # claims to be done too early
            reply(insert(7), flag(8), insert(9), insert(11)),
            reply(),
        ],
    )
    nudge = client.requests[2][-1]["content"]
    assert nudge == "Rows 7, 8, 9, 11 are still unhandled. Insert or flag each of them."
    assert upload.status == UploadStatus.COMPLETED


def test_fails_after_repeated_nudges(upload_id):
    upload, _ = run(upload_id, [reply(insert(5)), reply(), reply(), reply()])
    assert upload.status == UploadStatus.FAILED
    assert upload.error_message == "The import stopped before handling rows 6, 7, 8, 9, 11."
    assert upload.inserted_count == 1  # partial progress is kept


def test_turn_limit(upload_id, monkeypatch):
    monkeypatch.setattr(get_settings(), "agent_max_turns", 2)
    upload, _ = run(upload_id, [reply(insert(5)), reply(insert(6))])
    assert upload.status == UploadStatus.FAILED
    assert "ran out of steps" in upload.error_message


def test_refusal(upload_id):
    upload, _ = run(upload_id, [reply(stop_reason="refusal")])
    assert upload.status == UploadStatus.FAILED
    assert "declined" in upload.error_message


def test_truncated_response_runs_no_tools(upload_id):
    upload, client = run(
        upload_id,
        [
            reply(insert(5), stop_reason="max_tokens"),
            handle_all(),
            reply(),
        ],
    )
    result = client.requests[1][-1]["content"][0]
    assert result["is_error"] is True and "output limit" in result["content"]
    assert upload.status == UploadStatus.COMPLETED
    assert upload.inserted_count == 5


def test_crash_fails_upload_and_resume_sends_only_remaining_rows(upload_id):
    class Boom(FakeClient):
        def _create(self, **kwargs):
            if len(self.requests) == 1:
                raise RuntimeError("network down")
            return super()._create(**kwargs)

    client = Boom([reply(insert(5), insert(6))])
    with SessionLocal() as db:
        runner.claim_upload(db, upload_id)
    runner.run_agent(upload_id, client=client)
    with SessionLocal() as db:
        upload = db.get(RosterUpload, upload_id)
        assert upload.status == UploadStatus.FAILED
        assert "network down" in upload.error_message
        assert upload.inserted_count == 2

    upload, client = run(upload_id, [reply(insert(7), flag(8), insert(9), insert(11)), reply()])
    first_message = client.requests[0][0]["content"]
    assert '"_row": 5' not in first_message and '"_row": 7' in first_message
    assert upload.status == UploadStatus.COMPLETED
    with SessionLocal() as db:
        assert db.query(Student).count() == 5


def test_teacher_notes_reach_the_agent(upload_id):
    client = FakeClient([handle_all(), reply()])
    with SessionLocal() as db:
        runner.claim_upload(db, upload_id)
    runner.run_agent(upload_id, client=client, instructions="Dates are month/day/year")
    first_message = client.requests[0][0]["content"]
    assert "<teacher_notes>\nDates are month/day/year\n</teacher_notes>" in first_message


def test_claim_is_exclusive(upload_id):
    with SessionLocal() as db:
        assert runner.claim_upload(db, upload_id) is True
        assert runner.claim_upload(db, upload_id) is False


# --- Endpoint -------------------------------------------------------------------------


def test_process_endpoint_starts_agent(client, upload_id, monkeypatch):
    started = []
    monkeypatch.setattr(
        "app.api.uploads.run_agent",
        lambda upload_id, instructions=None: started.append((upload_id, instructions)),
    )
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key")
    resp = client.post(
        f"/api/uploads/{upload_id}/process", json={"instructions": " Dates are M/D/Y "}
    )
    assert resp.status_code == 202
    assert resp.json()["status"] == "processing"
    assert started == [(upload_id, "Dates are M/D/Y")]
    assert client.post(f"/api/uploads/{upload_id}/process").status_code == 409


def test_process_endpoint_without_key_503(client, upload_id, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", None)
    assert client.post(f"/api/uploads/{upload_id}/process").status_code == 503


def test_process_missing_upload_404(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "anthropic_api_key", "test-key")
    assert client.post("/api/uploads/999/process").status_code == 404

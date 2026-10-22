from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy import select

from app.agent.runner import claim_upload, run_agent
from app.config import get_settings
from app.db import DbSession
from app.models import RosterUpload, SchoolClass, UploadStatus
from app.schemas import ProcessRequest, UploadOut, UploadSummary
from app.services.roster_parser import RosterParseError, UnsupportedFileType, parse_roster

router = APIRouter(tags=["uploads"])


@router.post(
    "/classes/{class_id}/uploads", response_model=UploadOut, status_code=status.HTTP_201_CREATED
)
def upload_roster(class_id: int, file: UploadFile, db: DbSession) -> UploadOut:
    settings = get_settings()
    if db.get(SchoolClass, class_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found")

    content = file.file.read(settings.max_upload_bytes + 1)
    if len(content) > settings.max_upload_bytes:
        limit_mb = settings.max_upload_bytes // (1024 * 1024)
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, f"File is larger than {limit_mb} MB")

    filename = file.filename or "upload"
    try:
        roster = parse_roster(filename, content, settings.max_upload_rows)
    except UnsupportedFileType as exc:
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc)) from None
    except RosterParseError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None

    upload = RosterUpload(
        class_id=class_id,
        filename=filename,
        status=UploadStatus.PARSED,
        columns=roster.columns,
        rows=roster.rows_json(),
        total_rows=len(roster.rows),
        inserted_count=0,
        flagged_count=0,
    )
    db.add(upload)
    db.commit()
    return UploadOut.model_validate(upload)


@router.get("/classes/{class_id}/uploads", response_model=list[UploadSummary])
def list_class_uploads(class_id: int, db: DbSession) -> list[RosterUpload]:
    stmt = (
        select(RosterUpload)
        .where(RosterUpload.class_id == class_id)
        .order_by(RosterUpload.created_at.desc(), RosterUpload.id.desc())
    )
    return list(db.scalars(stmt))


@router.get("/uploads/{upload_id}", response_model=UploadOut)
def get_upload(upload_id: int, db: DbSession) -> UploadOut:
    upload = db.get(RosterUpload, upload_id)
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    return UploadOut.model_validate(upload)


@router.post(
    "/uploads/{upload_id}/process",
    response_model=UploadSummary,
    status_code=status.HTTP_202_ACCEPTED,
)
def process_upload(
    upload_id: int,
    background_tasks: BackgroundTasks,
    db: DbSession,
    payload: ProcessRequest | None = None,
) -> UploadSummary:
    """Start the AI import. Poll GET /uploads/{id} for progress and the result."""
    if get_settings().anthropic_api_key is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "AI import is not configured")
    upload = db.get(RosterUpload, upload_id)
    if upload is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Upload not found")
    if not claim_upload(db, upload_id):
        raise HTTPException(status.HTTP_409_CONFLICT, f"Upload is already {upload.status}")

    instructions = payload.instructions.strip() if payload and payload.instructions else None
    background_tasks.add_task(run_agent, upload_id, instructions=instructions or None)
    db.refresh(upload)
    return UploadSummary.model_validate(upload)

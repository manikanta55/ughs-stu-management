from fastapi import APIRouter
from sqlalchemy import select

from app.db import DbSession
from app.models import Student
from app.schemas import StudentOut

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=list[StudentOut])
def list_students(db: DbSession, class_id: int | None = None) -> list[Student]:
    stmt = select(Student).order_by(Student.last_name, Student.first_name)
    if class_id is not None:
        stmt = stmt.where(Student.class_id == class_id)
    return list(db.scalars(stmt))

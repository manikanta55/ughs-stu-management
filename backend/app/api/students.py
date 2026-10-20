from fastapi import APIRouter
from sqlalchemy import select

from app.db import DbSession
from app.models import Student
from app.schemas import StudentOut

router = APIRouter(prefix="/students", tags=["students"])


@router.get("", response_model=list[StudentOut])
def list_students(db: DbSession) -> list[Student]:
    return list(db.scalars(select(Student).order_by(Student.id)))

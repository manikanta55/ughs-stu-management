from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import DbSession
from app.models import SchoolClass, Student
from app.schemas import ClassCreate, ClassOut

router = APIRouter(prefix="/classes", tags=["classes"])


def _with_count(school_class: SchoolClass, count: int) -> ClassOut:
    return ClassOut.model_validate(school_class).model_copy(update={"student_count": count})


@router.get("", response_model=list[ClassOut])
def list_classes(db: DbSession, academic_year: str | None = None) -> list[ClassOut]:
    stmt = (
        select(SchoolClass, func.count(Student.id))
        .outerjoin(Student)
        .group_by(SchoolClass.id)
        .order_by(SchoolClass.academic_year, SchoolClass.grade, SchoolClass.section)
    )
    if academic_year:
        stmt = stmt.where(SchoolClass.academic_year == academic_year)
    return [_with_count(c, n) for c, n in db.execute(stmt)]


@router.post("", response_model=ClassOut, status_code=status.HTTP_201_CREATED)
def create_class(payload: ClassCreate, db: DbSession) -> ClassOut:
    school_class = SchoolClass(**payload.model_dump())
    db.add(school_class)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Class already exists") from None
    return _with_count(school_class, 0)


@router.get("/{class_id}", response_model=ClassOut)
def get_class(class_id: int, db: DbSession) -> ClassOut:
    school_class = db.get(SchoolClass, class_id)
    if school_class is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Class not found")
    count = db.scalar(select(func.count()).where(Student.class_id == class_id))
    return _with_count(school_class, count or 0)

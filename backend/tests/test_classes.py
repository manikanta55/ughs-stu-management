from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import SchoolClass, Student

CLASS_5A = {"grade": "5", "section": "A", "academic_year": "2026-27"}


def test_create_and_list_classes(client):
    resp = client.post("/api/classes", json=CLASS_5A)
    assert resp.status_code == 201
    body = resp.json()
    assert body["grade"] == "5" and body["section"] == "A" and body["student_count"] == 0

    resp = client.get("/api/classes", params={"academic_year": "2026-27"})
    assert [c["id"] for c in resp.json()] == [body["id"]]


def test_duplicate_class_rejected(client):
    assert client.post("/api/classes", json=CLASS_5A).status_code == 201
    assert client.post("/api/classes", json=CLASS_5A).status_code == 409


def test_invalid_academic_year_rejected(client):
    resp = client.post("/api/classes", json={**CLASS_5A, "academic_year": "2026"})
    assert resp.status_code == 422


def test_get_missing_class_404(client):
    assert client.get("/api/classes/999").status_code == 404


def test_students_belong_to_class(client):
    with SessionLocal() as db:
        five_a = SchoolClass(**CLASS_5A)
        five_b = SchoolClass(grade="5", section="B", academic_year="2026-27")
        db.add_all([five_a, five_b])
        db.flush()
        db.add_all(
            [
                Student(
                    class_id=five_a.id,
                    first_name="Asha",
                    last_name="Rao",
                    date_of_birth=date(2016, 4, 2),
                ),
                Student(class_id=five_b.id, first_name="Ravi", last_name="Kumar"),
            ]
        )
        db.commit()
        a_id = five_a.id

    assert client.get(f"/api/classes/{a_id}").json()["student_count"] == 1
    students = client.get("/api/students", params={"class_id": a_id}).json()
    assert [s["first_name"] for s in students] == ["Asha"]
    assert len(client.get("/api/students").json()) == 2


def test_student_requires_existing_class():
    with SessionLocal() as db:
        db.add(Student(class_id=12345, first_name="No", last_name="Class"))
        with pytest.raises(IntegrityError):
            db.commit()


def test_class_with_students_cannot_be_deleted():
    with SessionLocal() as db:
        c = SchoolClass(**CLASS_5A)
        db.add(c)
        db.flush()
        db.add(Student(class_id=c.id, first_name="Asha", last_name="Rao"))
        db.commit()
        db.delete(c)
        with pytest.raises(IntegrityError):
            db.commit()

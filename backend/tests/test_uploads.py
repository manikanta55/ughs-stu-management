from app.config import get_settings

CSV = b"Student Name,DOB,Parent Email\nAsha Rao,02/04/2016,asha@x.com\nRavi Kumar,,\n"


def make_class(client) -> int:
    resp = client.post(
        "/api/classes", json={"grade": "5", "section": "A", "academic_year": "2026-27"}
    )
    return resp.json()["id"]


def upload(client, class_id, filename="roster.csv", content=CSV):
    return client.post(f"/api/classes/{class_id}/uploads", files={"file": (filename, content)})


def test_upload_csv_is_parsed_and_stored(client):
    class_id = make_class(client)
    resp = upload(client, class_id)
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "parsed"
    assert body["total_rows"] == 2
    assert body["inserted_count"] == 0 and body["flagged_rows"] == []
    assert body["columns"] == ["Student Name", "DOB", "Parent Email"]
    assert body["preview"][0] == {
        "row": 2,
        "values": {"Student Name": "Asha Rao", "DOB": "02/04/2016", "Parent Email": "asha@x.com"},
    }

    detail = client.get(f"/api/uploads/{body['id']}").json()
    assert detail["total_rows"] == 2

    listing = client.get(f"/api/classes/{class_id}/uploads").json()
    assert [u["id"] for u in listing] == [body["id"]]
    assert "preview" not in listing[0]


def test_upload_to_missing_class_404(client):
    assert upload(client, 999).status_code == 404


def test_unsupported_file_type_415(client):
    assert upload(client, make_class(client), filename="roster.pdf").status_code == 415


def test_unreadable_file_422(client):
    resp = upload(client, make_class(client), content=b"Name,DOB\n")
    assert resp.status_code == 422
    assert "no student rows" in resp.json()["detail"]


def test_file_too_large_413(client, monkeypatch):
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 10)
    assert upload(client, make_class(client)).status_code == 413


def test_get_missing_upload_404(client):
    assert client.get("/api/uploads/999").status_code == 404

import io
import json
from datetime import datetime

import pytest
from openpyxl import Workbook

from app.services.roster_parser import RosterParseError, UnsupportedFileType, parse_roster


def xlsx_bytes(rows: list[list]) -> bytes:
    wb = Workbook()
    for row in rows:
        wb.active.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_csv_basic():
    content = b"Student Name,DOB,Parent Email\nAsha Rao,02/04/2016,asha@x.com\n"
    roster = parse_roster("class.csv", content, max_rows=100)
    assert roster.columns == ["Student Name", "DOB", "Parent Email"]
    assert roster.rows[0].row_number == 2
    assert roster.rows[0].values == {
        "Student Name": "Asha Rao",
        "DOB": "02/04/2016",
        "Parent Email": "asha@x.com",
    }


def test_title_rows_blank_rows_and_columns_are_skipped():
    content = (
        b"Class 5-A Roster 2026-27,,,\n"
        b",,,\n"
        b"Name,,Surname,DOB\n"
        b"Asha,,Rao,2016-04-02\n"
        b",,,\n"
        b"  Ravi   ,,Kumar ,\n"
    )
    roster = parse_roster("r.csv", content, max_rows=100)
    assert roster.columns == ["Name", "Surname", "DOB"]
    assert [r.row_number for r in roster.rows] == [4, 6]
    assert roster.rows[1].values == {"Name": "Ravi", "Surname": "Kumar", "DOB": ""}


def test_semicolon_csv_and_cp1252_encoding():
    content = "Nom;Prénom\nRao;Asha\n".encode("cp1252")
    roster = parse_roster("r.csv", content, max_rows=100)
    assert roster.columns == ["Nom", "Prénom"]
    assert roster.rows[0].values == {"Nom": "Rao", "Prénom": "Asha"}


def test_ragged_csv_rows():
    roster = parse_roster("r.csv", b"a,b\n1\n2,3,4\n", max_rows=100)
    assert roster.columns == ["a", "b", "Column 3"]
    assert roster.rows[0].values == {"a": "1", "b": "", "Column 3": ""}


def test_duplicate_and_empty_headers_get_unique_names():
    roster = parse_roster("r.csv", b"Name,Name,,Phone\nA,B,x,1\n", max_rows=100)
    assert roster.columns == ["Name", "Name (2)", "Column 3", "Phone"]


def test_xlsx_dates_and_numbers_become_plain_text():
    content = xlsx_bytes(
        [
            ["Roster"],
            ["Student Name", "Date of Birth", "Phone"],
            ["Asha Rao", datetime(2016, 4, 2), 9876543210],
        ]
    )
    roster = parse_roster("r.xlsx", content, max_rows=100)
    assert roster.rows[0].row_number == 3
    assert roster.rows[0].values == {
        "Student Name": "Asha Rao",
        "Date of Birth": "2016-04-02",
        "Phone": "9876543210",
    }


def test_prompt_text_is_one_json_object_per_row():
    roster = parse_roster("r.csv", b"Name,DOB\nAsha,2016\nRavi,2015\n", max_rows=100)
    lines = roster.to_prompt_text().splitlines()
    assert [json.loads(line) for line in lines] == [
        {"_row": 2, "Name": "Asha", "DOB": "2016"},
        {"_row": 3, "Name": "Ravi", "DOB": "2015"},
    ]


@pytest.mark.parametrize(
    ("filename", "content", "error", "message"),
    [
        ("r.pdf", b"x", UnsupportedFileType, "Unsupported file type"),
        ("r.csv", b"", RosterParseError, "empty"),
        ("r.csv", b"Name,DOB\n", RosterParseError, "no student rows"),
        ("r.xlsx", b"not a zip", RosterParseError, "valid .xlsx"),
        ("r.csv", b"Name,DOB\na,1\nb,2\nc,3\n", RosterParseError, "limit is 2"),
    ],
)
def test_rejections(filename, content, error, message):
    with pytest.raises(error, match=message):
        parse_roster(filename, content, max_rows=2)

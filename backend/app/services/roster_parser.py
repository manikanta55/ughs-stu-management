"""Read an uploaded .csv/.xlsx roster into rows for the agent.

No column mapping happens here: headers and values are kept as the teacher wrote them,
only tidied (blank rows/columns dropped, whitespace collapsed, Excel dates and numbers
turned into plain text). Mapping to student fields is the agent's job.
"""

import csv
import io
import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import pandas as pd

SUPPORTED_EXTENSIONS = (".csv", ".xlsx")


class RosterParseError(ValueError):
    """The file can't be used as a roster. The message is safe to show to the teacher."""


class UnsupportedFileType(RosterParseError):
    pass


@dataclass
class ParsedRow:
    row_number: int  # row number as the teacher sees it in the spreadsheet (1-based)
    values: dict[str, str]


@dataclass
class ParsedRoster:
    columns: list[str]
    rows: list[ParsedRow]

    def rows_json(self) -> list[dict[str, Any]]:
        return [{"row": r.row_number, "values": r.values} for r in self.rows]

    def to_prompt_text(self) -> str:
        return format_rows_for_prompt(self.rows_json())


def format_rows_for_prompt(rows: list[dict[str, Any]]) -> str:
    """One JSON object per line, keyed by the original headers, for the agent's prompt."""
    return "\n".join(
        json.dumps({"_row": r["row"], **r["values"]}, ensure_ascii=False) for r in rows
    )


def parse_roster(filename: str, content: bytes, max_rows: int) -> ParsedRoster:
    ext = Path(filename).suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise UnsupportedFileType(
            f"Unsupported file type '{ext or filename}'. Upload a .csv or .xlsx file."
        )
    try:
        grid = _read_csv(content) if ext == ".csv" else _read_xlsx(content)
    except RosterParseError:
        raise
    except Exception as exc:
        raise RosterParseError(
            f"Could not read the file as {ext}. Is it a valid {ext} file?"
        ) from exc
    return _to_roster(grid, max_rows)


def _read_csv(content: bytes) -> pd.DataFrame:
    for encoding in ("utf-8-sig", "cp1252"):
        try:
            text = content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise RosterParseError("Could not decode the CSV file. Save it as UTF-8 and try again.")

    try:
        dialect: Any = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    # csv.reader tolerates ragged rows; DataFrame pads short rows with None.
    return pd.DataFrame(list(csv.reader(io.StringIO(text), dialect)))


def _read_xlsx(content: bytes) -> pd.DataFrame:
    # dtype=object keeps Excel dates as datetimes so they don't become "2016-04-02 00:00:00".
    return pd.read_excel(io.BytesIO(content), sheet_name=0, header=None, dtype=object)


def _to_roster(grid: pd.DataFrame, max_rows: int) -> ParsedRoster:
    grid = grid.map(_cell_to_str)
    filled = grid.ne("")
    grid = grid.loc[filled.any(axis=1), filled.any(axis=0)]
    if grid.empty:
        raise RosterParseError("The file is empty.")

    # Title or note rows above the table fill only a cell or two; take the first row that
    # fills at least half the columns as the header.
    filled_per_row = grid.ne("").sum(axis=1)
    threshold = max(2, math.ceil(grid.shape[1] / 2))
    header_pos = int((filled_per_row >= threshold).to_numpy().argmax())

    columns = _header_names(grid.iloc[header_pos].tolist())
    body = grid.iloc[header_pos + 1 :]
    if body.empty:
        raise RosterParseError("Found a header row but no student rows below it.")
    if len(body) > max_rows:
        raise RosterParseError(f"The file has {len(body)} rows; the limit is {max_rows}.")

    rows = [
        # The grid index is the 0-based line in the file, so +1 is the spreadsheet row number.
        ParsedRow(row_number=int(index) + 1, values=dict(zip(columns, cells, strict=True)))
        for index, cells in zip(body.index, body.itertuples(index=False, name=None), strict=True)
    ]
    return ParsedRoster(columns=columns, rows=rows)


def _cell_to_str(value: Any) -> str:
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return ""
    if isinstance(value, datetime):
        is_midnight = value.time() == datetime.min.time()
        return value.date().isoformat() if is_midnight else value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, float) and value.is_integer():
        return str(int(value))  # Excel stores 9876543210 as 9876543210.0
    return " ".join(str(value).split())


def _header_names(cells: list[str]) -> list[str]:
    names: list[str] = []
    for i, cell in enumerate(cells, start=1):
        name = cell or f"Column {i}"
        candidate, n = name, 2
        while candidate in names:
            candidate, n = f"{name} ({n})", n + 1
        names.append(candidate)
    return names

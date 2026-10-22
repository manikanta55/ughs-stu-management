"""Run the roster agent on one upload and print the result.

Usage: uv run python -m scripts.process_upload <upload_id>
"""

import logging
import sys

from app.agent.runner import claim_upload, run_agent
from app.db import SessionLocal
from app.models import RosterUpload, Student


def main(upload_id: int) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    with SessionLocal() as db:
        if not claim_upload(db, upload_id):
            upload = db.get(RosterUpload, upload_id)
            print(
                f"Cannot process upload {upload_id}: " + (upload.status if upload else "not found")
            )
            return 1

    run_agent(upload_id)

    with SessionLocal() as db:
        upload = db.get(RosterUpload, upload_id)
        print(
            f"\nStatus: {upload.status}  inserted={upload.inserted_count}  "
            f"flagged={upload.flagged_count}  of {upload.total_rows}"
        )
        if upload.error_message:
            print(f"Error: {upload.error_message}")
        print(f"Agent: {upload.agent_stats}")
        print("\nInserted:")
        students = db.query(Student).filter_by(upload_id=upload_id).order_by(Student.upload_row)
        for s in students:
            print(
                f"  row {s.upload_row}: {s.first_name} {s.last_name} | {s.date_of_birth} | "
                f"{s.parent_email}"
            )
        print("\nFlagged:")
        for f in upload.flagged_rows:
            print(f"  row {f.row_number}: {f.reason}")
    return 0 if upload.status == "completed" else 1


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1])))

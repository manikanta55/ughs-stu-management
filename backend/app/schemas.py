from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class StudentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    first_name: str
    last_name: str
    date_of_birth: date | None
    parent_email: str | None
    created_at: datetime

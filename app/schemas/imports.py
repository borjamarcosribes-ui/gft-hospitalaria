from pydantic import BaseModel
from uuid import UUID


class ImportBatchResponse(BaseModel):
    id: UUID
    status: str
    total_rows: int
    processed_rows: int
    ok_rows: int
    error_rows: int

    class Config:
        from_attributes = True

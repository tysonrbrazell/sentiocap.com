from pydantic import BaseModel


class ClassificationResult(BaseModel):
    label: str
    confidence: float


class BulkClassifyRequest(BaseModel):
    investment_ids: list[str]

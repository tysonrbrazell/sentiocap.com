from pydantic import BaseModel


class Plan(BaseModel):
    id: str
    name: str


class PlanCreate(BaseModel):
    name: str


class PlanUpdate(BaseModel):
    name: str


class PlanSummary(BaseModel):
    total: int

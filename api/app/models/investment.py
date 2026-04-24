from pydantic import BaseModel


class Investment(BaseModel):
    id: str
    name: str


class InvestmentCreate(BaseModel):
    name: str


class ClassifyRequest(BaseModel):
    investment_id: str

from pydantic import BaseModel


class Benchmark(BaseModel):
    sector: str


class CompareRequest(BaseModel):
    sector: str


class CompareResponse(BaseModel):
    percentile: float

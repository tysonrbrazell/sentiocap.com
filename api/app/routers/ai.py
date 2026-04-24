from fastapi import APIRouter

router = APIRouter()


@router.post("/classify")
async def classify() -> dict[str, str]:
    return {"message": "classification placeholder"}

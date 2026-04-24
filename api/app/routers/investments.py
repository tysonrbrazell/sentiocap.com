from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def list_investments() -> list[dict[str, str]]:
    return []

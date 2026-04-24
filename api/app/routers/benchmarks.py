from fastapi import APIRouter

router = APIRouter()


@router.get("")
async def get_benchmarks() -> list[dict[str, str]]:
    return []

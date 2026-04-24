from fastapi import APIRouter

router = APIRouter()


@router.get("/plans/{plan_id}/csv")
async def export_plan_csv(plan_id: str) -> dict[str, str]:
    return {"plan_id": plan_id, "message": "export placeholder"}

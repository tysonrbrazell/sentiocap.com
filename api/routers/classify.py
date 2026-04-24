"""
Classification router — single + batch AI classification.
"""
from fastapi import APIRouter, Depends
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from models.schemas import (
    ClassificationRequest,
    ClassificationResult,
    ClassificationAlternative,
    BatchClassificationRequest,
    BatchClassificationResponse,
    BatchClassificationResultItem,
    L1Type,
)
from services.classification import classify_single, classify_batch

router = APIRouter(prefix="/classify", tags=["classify"])


# ---------------------------------------------------------------------------
# POST /api/classify
# ---------------------------------------------------------------------------

@router.post("/", response_model=ClassificationResult)
def classify_single_item(
    payload: ClassificationRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    result = classify_single(
        description=payload.description,
        cost_center=payload.cost_center,
        gl_account=payload.gl_account,
        amount=str(payload.amount or ""),
    )
    alternatives = [
        ClassificationAlternative(**a) for a in result.get("alternatives", [])
    ]
    return ClassificationResult(
        classified_l1=L1Type(result["l1"]),
        classified_l2=result["l2"],
        classified_l3=result["l3"],
        classified_l4=result["l4"],
        confidence=result["confidence"],
        method="ai_auto",
        reasoning=result.get("reasoning"),
        alternatives=alternatives,
    )


# ---------------------------------------------------------------------------
# POST /api/classify/batch
# ---------------------------------------------------------------------------

@router.post("/batch", response_model=BatchClassificationResponse)
def classify_batch_items(
    payload: BatchClassificationRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    items = [
        {
            "id": item.id,
            "description": item.description,
            "cost_center": item.cost_center,
            "gl_account": item.gl_account,
            "amount": item.amount or 0,
        }
        for item in payload.items
    ]

    results = classify_batch(items)

    auto_confirmed = 0
    needs_review = 0
    flagged = 0
    result_items = []

    for r in results:
        conf = r.get("confidence", 0)
        if conf >= 0.9:
            auto_confirmed += 1
        elif conf >= 0.7:
            needs_review += 1
        else:
            flagged += 1

        result_items.append(
            BatchClassificationResultItem(
                id=r["id"],
                classified_l1=L1Type(r["l1"]),
                classified_l2=r["l2"],
                classified_l3=r["l3"],
                classified_l4=r["l4"],
                confidence=conf,
                method="ai_auto",
                reasoning=r.get("reasoning"),
            )
        )

    return BatchClassificationResponse(
        results=result_items,
        total=len(result_items),
        auto_confirmed=auto_confirmed,
        needs_review=needs_review,
        flagged=flagged,
    )

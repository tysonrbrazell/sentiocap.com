"""
Actuals router — upload monthly GL actuals, query by period.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from models.schemas import ActualsUploadResponse, ActualsResponse
from services.upload import parse_upload_file
from services.classification import classify_batch

router = APIRouter(prefix="/actuals", tags=["actuals"])


# ---------------------------------------------------------------------------
# POST /api/actuals/upload
# ---------------------------------------------------------------------------

@router.post("/upload", response_model=ActualsUploadResponse)
async def upload_actuals(
    file: UploadFile = File(...),
    period: str = Form(...),
    description_column: str = Form(...),
    cost_center_column: Optional[str] = Form(None),
    gl_account_column: Optional[str] = Form(None),
    amount_column: Optional[str] = Form(...),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Upload monthly actual GL data. Auto-classifies via AI."""
    contents = await file.read()
    filename = file.filename or ""

    column_map = {
        "description": description_column,
        "cost_center": cost_center_column,
        "gl_account": gl_account_column,
        "annual": amount_column,  # single amount column maps to "annual" for actuals
    }

    rows, _ = parse_upload_file(contents, filename, column_map)

    # Classify all rows
    batch_items = [
        {
            "id": str(i),
            "description": row["source_description"],
            "cost_center": row.get("source_cost_center"),
            "gl_account": row.get("source_gl_account"),
            "amount": row.get("annual_total", 0),
        }
        for i, row in enumerate(rows)
    ]

    classifications = {}
    flagged = 0
    classified_count = 0
    try:
        results = classify_batch(batch_items)
        for r in results:
            idx = int(r["id"])
            classifications[idx] = r
            conf = r.get("confidence", 0)
            if conf >= 0.7:
                classified_count += 1
            else:
                flagged += 1
    except Exception:
        flagged = len(rows)

    # Build insert rows
    insert_rows = []
    total_amount = 0.0
    for i, row in enumerate(rows):
        cls = classifications.get(i, {})
        amount = row.get("annual_total", 0) or 0
        total_amount += amount
        insert_rows.append({
            "org_id": current_user["org_id"],
            "period": period,
            "source_description": row["source_description"],
            "source_cost_center": row.get("source_cost_center"),
            "source_gl_account": row.get("source_gl_account"),
            "amount": amount,
            "classified_l1": cls.get("l1"),
            "classified_l2": cls.get("l2"),
            "classified_l3": cls.get("l3"),
            "classified_l4": cls.get("l4"),
            "classification_confidence": cls.get("confidence"),
            "classification_method": "ai_auto" if cls else "user_manual",
            "uploaded_by": current_user["id"],
        })

    # Insert in batches
    for i in range(0, len(insert_rows), 100):
        db.table("actuals").insert(insert_rows[i:i+100]).execute()

    return ActualsUploadResponse(
        period=period,
        rows_imported=len(rows),
        rows_classified=classified_count,
        rows_flagged=flagged,
        total_amount=total_amount,
        variances_updated=False,  # variance computation handled separately
    )


# ---------------------------------------------------------------------------
# GET /api/actuals
# ---------------------------------------------------------------------------

@router.get("/", response_model=ActualsResponse)
def get_actuals(
    period: str = Query(...),
    l2: Optional[str] = Query(None),
    l1: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    q = (
        db.table("actuals")
        .select("*")
        .eq("org_id", current_user["org_id"])
        .eq("period", period)
    )
    if l2:
        q = q.eq("classified_l2", l2)
    if l1:
        q = q.eq("classified_l1", l1)

    result = q.execute()
    items = result.data or []

    total_amount = sum(i.get("amount", 0) or 0 for i in items)
    by_l2: dict[str, float] = {}
    for item in items:
        l2_code = item.get("classified_l2")
        if l2_code:
            by_l2[l2_code] = by_l2.get(l2_code, 0) + (item.get("amount") or 0)

    return ActualsResponse(
        period=period,
        total_amount=total_amount,
        by_l2=by_l2,
        line_items=items,
    )

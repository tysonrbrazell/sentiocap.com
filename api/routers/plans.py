"""
Plans router — CRUD + upload + classify + approve.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from models.schemas import (
    PlanCreate,
    PlanUpdate,
    PlanResponse,
    PlanListResponse,
    PlanListItem,
    PlanLineItemResponse,
    PlanSummaryStats,
    LineItemUpdate,
    PlanApproveRequest,
    PlanApproveResponse,
    ClassifyPlanRequest,
    ClassifyPlanResponse,
    UploadPreviewResponse,
)
from services.upload import parse_upload_file, map_columns
from services.classification import classify_single

router = APIRouter(prefix="/plans", tags=["plans"])


def _require_plan_access(plan_id: str, org_id: str, db: Client) -> dict:
    result = db.table("plans").select("*").eq("id", plan_id).eq("org_id", org_id).single().execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Plan not found")
    return result.data


def _compute_plan_summary(plan_id: str, db: Client) -> PlanSummaryStats:
    items_result = (
        db.table("plan_line_items")
        .select("classified_l1, classified_l2, annual_total")
        .eq("plan_id", plan_id)
        .execute()
    )
    items = items_result.data or []

    rtb_total = sum(i["annual_total"] or 0 for i in items if i.get("classified_l1") == "RTB")
    ctb_total = sum(i["annual_total"] or 0 for i in items if i.get("classified_l1") == "CTB")
    grand_total = rtb_total + ctb_total

    by_l2: dict[str, float] = {}
    for item in items:
        l2 = item.get("classified_l2")
        if l2:
            by_l2[l2] = by_l2.get(l2, 0) + (item.get("annual_total") or 0)

    return PlanSummaryStats(
        rtb_total=rtb_total,
        ctb_total=ctb_total,
        rtb_pct=round(rtb_total / grand_total * 100, 1) if grand_total else 0,
        ctb_pct=round(ctb_total / grand_total * 100, 1) if grand_total else 0,
        by_l2=by_l2,
    )


# ---------------------------------------------------------------------------
# GET /api/plans
# ---------------------------------------------------------------------------

@router.get("/", response_model=PlanListResponse)
def list_plans(
    fiscal_year: Optional[int] = Query(None),
    plan_status: Optional[str] = Query(None, alias="status"),
    plan_type: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    query = db.table("plans").select("*").eq("org_id", current_user["org_id"])
    if fiscal_year:
        query = query.eq("fiscal_year", fiscal_year)
    if plan_status:
        query = query.eq("status", plan_status)
    if plan_type:
        query = query.eq("plan_type", plan_type)

    result = query.order("created_at", desc=True).execute()
    plans_raw = result.data or []

    plans = []
    for p in plans_raw:
        # Count line items
        count_res = (
            db.table("plan_line_items")
            .select("id, classified_l1, user_confirmed", count="exact")
            .eq("plan_id", p["id"])
            .execute()
        )
        items = count_res.data or []
        classified = sum(1 for i in items if i.get("classified_l1"))
        confirmed = sum(1 for i in items if i.get("user_confirmed"))

        plans.append(
            PlanListItem(
                id=p["id"],
                name=p["name"],
                plan_type=p["plan_type"],
                fiscal_year=p["fiscal_year"],
                status=p["status"],
                total_budget=p.get("total_budget"),
                line_item_count=len(items),
                classified_count=classified,
                confirmed_count=confirmed,
                created_at=p["created_at"],
                approved_at=p.get("approved_at"),
            )
        )

    return PlanListResponse(plans=plans, total=len(plans))


# ---------------------------------------------------------------------------
# POST /api/plans
# ---------------------------------------------------------------------------

@router.post("/", response_model=PlanResponse, status_code=201)
def create_plan(
    payload: PlanCreate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    data = {
        "org_id": current_user["org_id"],
        "name": payload.name,
        "plan_type": payload.plan_type.value,
        "fiscal_year": payload.fiscal_year,
        "status": "draft",
        "created_by": current_user["id"],
        "notes": payload.notes,
    }
    result = db.table("plans").insert(data).execute()
    plan = result.data[0]
    return PlanResponse(
        **{k: v for k, v in plan.items() if k in PlanResponse.model_fields},
        line_items=[],
    )


# ---------------------------------------------------------------------------
# GET /api/plans/:id
# ---------------------------------------------------------------------------

@router.get("/{plan_id}", response_model=PlanResponse)
def get_plan(
    plan_id: str,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    l2: Optional[str] = Query(None),
    confirmed: Optional[bool] = Query(None),
    min_confidence: Optional[float] = Query(None),
    max_confidence: Optional[float] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    plan = _require_plan_access(plan_id, current_user["org_id"], db)

    # Build line items query
    q = (
        db.table("plan_line_items")
        .select("*")
        .eq("plan_id", plan_id)
        .order("source_row_number")
    )
    if l2:
        q = q.eq("classified_l2", l2)
    if confirmed is not None:
        q = q.eq("user_confirmed", confirmed)
    if min_confidence is not None:
        q = q.gte("classification_confidence", min_confidence)
    if max_confidence is not None:
        q = q.lte("classification_confidence", max_confidence)

    # Total count
    count_res = (
        db.table("plan_line_items")
        .select("id", count="exact")
        .eq("plan_id", plan_id)
        .execute()
    )
    total = len(count_res.data or [])

    # Paginate
    offset = (page - 1) * per_page
    items_result = q.range(offset, offset + per_page - 1).execute()
    items = [PlanLineItemResponse(**i) for i in (items_result.data or [])]

    # Fetch approver name
    approved_by_info = None
    if plan.get("approved_by"):
        user_res = (
            db.table("users")
            .select("id, name")
            .eq("id", plan["approved_by"])
            .single()
            .execute()
        )
        if user_res.data:
            approved_by_info = user_res.data

    summary = _compute_plan_summary(plan_id, db)

    return PlanResponse(
        id=plan["id"],
        name=plan["name"],
        plan_type=plan["plan_type"],
        fiscal_year=plan["fiscal_year"],
        status=plan["status"],
        total_budget=plan.get("total_budget"),
        currency=plan.get("currency", "USD"),
        approved_by=approved_by_info,
        approved_at=plan.get("approved_at"),
        notes=plan.get("notes"),
        created_at=plan["created_at"],
        summary=summary,
        line_items=items,
        line_items_total=total,
        line_items_page=page,
        line_items_per_page=per_page,
    )


# ---------------------------------------------------------------------------
# PUT /api/plans/:id
# ---------------------------------------------------------------------------

@router.put("/{plan_id}", response_model=PlanResponse)
def update_plan(
    plan_id: str,
    payload: PlanUpdate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    _require_plan_access(plan_id, current_user["org_id"], db)
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    result = db.table("plans").update(updates).eq("id", plan_id).execute()
    plan = result.data[0]
    summary = _compute_plan_summary(plan_id, db)
    return PlanResponse(
        **{k: plan[k] for k in PlanResponse.model_fields if k in plan},
        summary=summary,
        line_items=[],
    )


# ---------------------------------------------------------------------------
# POST /api/plans/:id/upload
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/upload", response_model=UploadPreviewResponse)
async def upload_plan_file(
    plan_id: str,
    file: UploadFile = File(...),
    description_column: str = Form(...),
    cost_center_column: Optional[str] = Form(None),
    gl_account_column: Optional[str] = Form(None),
    jan_column: Optional[str] = Form(None),
    feb_column: Optional[str] = Form(None),
    mar_column: Optional[str] = Form(None),
    apr_column: Optional[str] = Form(None),
    may_column: Optional[str] = Form(None),
    jun_column: Optional[str] = Form(None),
    jul_column: Optional[str] = Form(None),
    aug_column: Optional[str] = Form(None),
    sep_column: Optional[str] = Form(None),
    oct_column: Optional[str] = Form(None),
    nov_column: Optional[str] = Form(None),
    dec_column: Optional[str] = Form(None),
    annual_column: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    plan = _require_plan_access(plan_id, current_user["org_id"], db)

    contents = await file.read()
    filename = file.filename or ""
    column_map = {
        "description": description_column,
        "cost_center": cost_center_column,
        "gl_account": gl_account_column,
        "jan": jan_column, "feb": feb_column, "mar": mar_column,
        "apr": apr_column, "may": may_column, "jun": jun_column,
        "jul": jul_column, "aug": aug_column, "sep": sep_column,
        "oct": oct_column, "nov": nov_column, "dec": dec_column,
        "annual": annual_column,
    }

    rows, columns = parse_upload_file(contents, filename, column_map)

    # Classify first 5 rows for preview
    preview = []
    for i, row in enumerate(rows[:5]):
        suggested = None
        try:
            result = classify_single(
                description=row["source_description"],
                cost_center=row.get("source_cost_center"),
                gl_account=row.get("source_gl_account"),
                amount=str(row.get("annual_total", "")),
            )
            from models.schemas import ClassificationResult, L1Type
            suggested = ClassificationResult(
                classified_l1=L1Type(result["l1"]),
                classified_l2=result["l2"],
                classified_l3=result["l3"],
                classified_l4=result["l4"],
                confidence=result["confidence"],
                reasoning=result.get("reasoning"),
            )
        except Exception:
            pass

        amounts = {m: row.get(m, 0) for m in ["jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"]}
        preview.append({
            "row": i + 1,
            "source_description": row["source_description"],
            "source_cost_center": row.get("source_cost_center"),
            "source_gl_account": row.get("source_gl_account"),
            "amounts": amounts,
            "annual_total": row.get("annual_total", 0),
            "suggested_classification": suggested,
        })

    # Persist all rows to plan_line_items
    insert_rows = []
    for idx, row in enumerate(rows):
        insert_rows.append({
            "plan_id": plan_id,
            "source_description": row["source_description"],
            "source_cost_center": row.get("source_cost_center"),
            "source_gl_account": row.get("source_gl_account"),
            "source_row_number": idx + 1,
            "jan": row.get("jan", 0), "feb": row.get("feb", 0),
            "mar": row.get("mar", 0), "apr": row.get("apr", 0),
            "may": row.get("may", 0), "jun": row.get("jun", 0),
            "jul": row.get("jul", 0), "aug": row.get("aug", 0),
            "sep": row.get("sep", 0), "oct": row.get("oct", 0),
            "nov": row.get("nov", 0), "dec": row.get("dec", 0),
        })

    # Insert in batches of 100
    for i in range(0, len(insert_rows), 100):
        db.table("plan_line_items").insert(insert_rows[i:i+100]).execute()

    upload_id = str(uuid4())
    return UploadPreviewResponse(
        upload_id=upload_id,
        rows_detected=len(rows),
        columns_detected=columns,
        preview=preview,
        preview_count=len(preview),
    )


# ---------------------------------------------------------------------------
# POST /api/plans/:id/classify
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/classify", response_model=ClassifyPlanResponse, status_code=202)
def classify_plan_items(
    plan_id: str,
    payload: ClassifyPlanRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    _require_plan_access(plan_id, current_user["org_id"], db)

    # Fetch items to classify
    q = db.table("plan_line_items").select("*").eq("plan_id", plan_id)
    if payload.mode == "unclassified_only":
        q = q.is_("classified_l1", "null")
    elif payload.mode == "low_confidence":
        q = q.lt("classification_confidence", payload.confidence_threshold)

    items_result = q.execute()
    items = items_result.data or []

    # Run classification synchronously (for simplicity — could be backgrounded)
    from services.classification import classify_batch
    if items:
        batch_items = [
            {
                "id": item["id"],
                "description": item["source_description"],
                "cost_center": item.get("source_cost_center"),
                "gl_account": item.get("source_gl_account"),
                "amount": 0,
            }
            for item in items
        ]
        results = classify_batch(batch_items)
        for r in results:
            db.table("plan_line_items").update({
                "classified_l1": r.get("l1"),
                "classified_l2": r.get("l2"),
                "classified_l3": r.get("l3"),
                "classified_l4": r.get("l4"),
                "classification_confidence": r.get("confidence"),
                "classification_method": "ai_auto",
                "classified_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", r["id"]).execute()

    job_id = str(uuid4())
    return ClassifyPlanResponse(
        job_id=job_id,
        status="completed",
        total_items=len(items),
        message=f"Classified {len(items)} line items.",
    )


# ---------------------------------------------------------------------------
# PUT /api/plans/:id/line-items/:line_id
# ---------------------------------------------------------------------------

@router.put("/{plan_id}/line-items/{line_id}", response_model=PlanLineItemResponse)
def update_line_item(
    plan_id: str,
    line_id: str,
    payload: LineItemUpdate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    _require_plan_access(plan_id, current_user["org_id"], db)

    # Verify line item belongs to plan
    item_res = (
        db.table("plan_line_items")
        .select("*")
        .eq("id", line_id)
        .eq("plan_id", plan_id)
        .single()
        .execute()
    )
    if not item_res.data:
        raise HTTPException(status_code=404, detail="Line item not found")

    updates = {}
    if payload.classified_l1 is not None:
        updates["classified_l1"] = payload.classified_l1.value
    if payload.classified_l2 is not None:
        updates["classified_l2"] = payload.classified_l2.value
    if payload.classified_l3 is not None:
        updates["classified_l3"] = payload.classified_l3.value
    if payload.classified_l4 is not None:
        updates["classified_l4"] = payload.classified_l4
    if payload.user_confirmed is not None:
        updates["user_confirmed"] = payload.user_confirmed
    if payload.notes is not None:
        updates["notes"] = payload.notes
    if updates:
        updates["classification_method"] = "user_manual"
        updates["classified_by"] = current_user["id"]

    result = db.table("plan_line_items").update(updates).eq("id", line_id).execute()
    return PlanLineItemResponse(**result.data[0])


# ---------------------------------------------------------------------------
# POST /api/plans/:id/approve
# ---------------------------------------------------------------------------

@router.post("/{plan_id}/approve", response_model=PlanApproveResponse)
def approve_plan(
    plan_id: str,
    payload: PlanApproveRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Only admins can approve plans")

    _require_plan_access(plan_id, current_user["org_id"], db)
    now = datetime.now(timezone.utc).isoformat()

    updates = {
        "status": "approved",
        "approved_by": current_user["id"],
        "approved_at": now,
    }
    if payload.notes:
        updates["notes"] = payload.notes

    result = db.table("plans").update(updates).eq("id", plan_id).execute()
    plan = result.data[0]

    return PlanApproveResponse(
        id=plan["id"],
        status=plan["status"],
        approved_by={"id": current_user["id"], "name": current_user["name"]},
        approved_at=plan.get("approved_at"),
    )

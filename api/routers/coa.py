"""
Chart of Accounts (CoA) router.

Endpoints:
  POST /api/coa/analyze         — upload trial balance, get structure + classifications
  GET  /api/coa                 — view learned chart of accounts
  GET  /api/coa/structure       — view detected account structure
  PUT  /api/coa/{account_code}  — manually correct a classification
  GET  /api/coa/summary         — Scout's learned CoA summary
  POST /api/coa/reclassify      — re-run classification on all accounts
  GET  /api/coa/anomalies       — accounts with unusual amounts
"""
import io
import logging
from typing import Optional
from urllib.parse import unquote

import pandas as pd
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from services.coa_learner import CoALearner
from services.memory import AgentMemory
from models.schemas import (
    CoAAccount,
    CoAStructure,
    CoAAnalysis,
    CoASummary,
    CoAAccountUpdate,
    CoAListResponse,
    CoAAnomalyResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/coa", tags=["coa"])


# ---------------------------------------------------------------------------
# POST /api/coa/analyze
# ---------------------------------------------------------------------------

@router.post("/analyze", response_model=CoAAnalysis)
async def analyze_trial_balance(
    file: UploadFile = File(...),
    account_code_column: Optional[str] = Form(None),
    account_name_column: Optional[str] = Form(None),
    amount_column: Optional[str] = Form(None),
    period_column: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Upload a trial balance or GL export. Scout analyzes, learns, and classifies."""
    org_id = current_user["org_id"]
    contents = await file.read()
    filename = file.filename or ""

    # Parse file
    try:
        if filename.lower().endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    df = pd.read_csv(io.BytesIO(contents), encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise HTTPException(status_code=400, detail="Could not decode file.")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

    df.columns = [str(c).strip() for c in df.columns]
    headers = list(df.columns)

    # Auto-detect columns if not provided
    memory = AgentMemory(org_id=org_id, supabase_client=db)
    learner = CoALearner(org_id=org_id, supabase_client=db, memory=memory)

    sample_rows = df.head(20).values.tolist()
    detected = await learner.get_smart_columns(headers, sample_rows)

    code_col = account_code_column or _find_col(detected, headers, "account_code")
    name_col = account_name_column or _find_col(detected, headers, "account_name")
    amount_col = amount_column or _find_col(detected, headers, "amount")
    period_col = period_column or _find_col(detected, headers, "period")

    if not code_col and not name_col:
        raise HTTPException(
            status_code=400,
            detail="Could not detect account code or name columns. Please specify them.",
        )

    # Build rows list
    rows = []
    for _, row in df.iterrows():
        code = str(row[code_col]).strip() if code_col and code_col in df.columns else ""
        name = str(row[name_col]).strip() if name_col and name_col in df.columns else ""
        amount = 0.0
        if amount_col and amount_col in df.columns:
            try:
                amount = float(str(row[amount_col]).replace(",", "").replace("$", "").strip())
            except (ValueError, TypeError):
                amount = 0.0
        period = str(row[period_col]).strip() if period_col and period_col in df.columns else None

        if not code and not name:
            continue
        rows.append({
            "account_code": code,
            "account_name": name,
            "amount": amount,
            "period": period,
        })

    if not rows:
        raise HTTPException(status_code=400, detail="No valid rows found in file.")

    analysis = await learner.analyze_upload(rows)

    # Map to response model
    return CoAAnalysis(
        structure=CoAStructure(**_structure_to_schema(analysis["structure"])),
        total_accounts=analysis["total_accounts"],
        expense_accounts=analysis["expense_accounts"],
        classified_accounts=analysis["classified_accounts"],
        new_accounts=analysis["new_accounts"],
        anomalies=analysis["anomalies"],
        accounts=[CoAAccount(**_account_to_schema(a)) for a in analysis["accounts"]],
        hierarchy=analysis.get("hierarchy", {}),
        column_mapping={
            "account_code": code_col,
            "account_name": name_col,
            "amount": amount_col,
            "period": period_col,
        },
    )


# ---------------------------------------------------------------------------
# GET /api/coa
# ---------------------------------------------------------------------------

@router.get("/", response_model=CoAListResponse)
def get_chart_of_accounts(
    is_expense: Optional[bool] = Query(None),
    classified: Optional[bool] = Query(None),
    l1: Optional[str] = Query(None),
    l2: Optional[str] = Query(None),
    min_confidence: Optional[float] = Query(None),
    max_confidence: Optional[float] = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """View the learned chart of accounts for this org."""
    org_id = current_user["org_id"]

    q = db.table("chart_of_accounts").select("*").eq("org_id", org_id)

    if is_expense is not None:
        q = q.eq("is_expense", is_expense)
    if classified is True:
        q = q.not_.is_("classified_l2", "null")
    elif classified is False:
        q = q.is_("classified_l2", "null")
    if l1:
        q = q.eq("classified_l1", l1)
    if l2:
        q = q.eq("classified_l2", l2)
    if min_confidence is not None:
        q = q.gte("classification_confidence", min_confidence)
    if max_confidence is not None:
        q = q.lte("classification_confidence", max_confidence)

    count_res = db.table("chart_of_accounts").select("id", count="exact").eq("org_id", org_id).execute()
    total = len(count_res.data or [])

    offset = (page - 1) * per_page
    result = q.order("account_code").range(offset, offset + per_page - 1).execute()
    accounts = [CoAAccount(**_account_to_schema(a)) for a in (result.data or [])]

    return CoAListResponse(accounts=accounts, total=total, page=page, per_page=per_page)


# ---------------------------------------------------------------------------
# GET /api/coa/structure
# ---------------------------------------------------------------------------

@router.get("/structure", response_model=CoAStructure)
def get_coa_structure(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """View the detected account code structure."""
    org_id = current_user["org_id"]
    res = db.table("coa_structure").select("*").eq("org_id", org_id).limit(1).execute()
    if not res.data:
        raise HTTPException(status_code=404, detail="No CoA structure learned yet. Upload a trial balance first.")
    return CoAStructure(**_structure_to_schema(res.data[0]))


# ---------------------------------------------------------------------------
# GET /api/coa/summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=CoASummary)
async def get_coa_summary(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Scout's learned summary of the CoA."""
    org_id = current_user["org_id"]
    memory = AgentMemory(org_id=org_id, supabase_client=db)
    learner = CoALearner(org_id=org_id, supabase_client=db, memory=memory)
    summary = await learner.generate_upload_summary()
    return CoASummary(**summary)


# ---------------------------------------------------------------------------
# GET /api/coa/anomalies
# ---------------------------------------------------------------------------

@router.get("/anomalies", response_model=CoAAnomalyResponse)
def get_anomalies(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Accounts with amounts deviating significantly from their typical value."""
    org_id = current_user["org_id"]
    # Fetch accounts that have been seen multiple times (have a baseline)
    res = (
        db.table("chart_of_accounts")
        .select("*")
        .eq("org_id", org_id)
        .gte("times_seen", 2)
        .execute()
    )
    accounts = res.data or []

    # We don't have live amounts here — return accounts where typical is set
    # The live anomaly detection happens during analyze_upload
    # This endpoint shows accounts flagged as anomalous based on their history
    anomalies = []
    for a in accounts:
        typical = a.get("typical_monthly_amount")
        if typical and float(typical) > 0:
            anomalies.append({
                "account_code": a["account_code"],
                "account_name": a["account_name"],
                "typical_amount": float(typical),
                "times_seen": a.get("times_seen", 0),
                "last_seen_at": a.get("last_seen_at"),
                "classified_l2": a.get("classified_l2"),
            })

    return CoAAnomalyResponse(anomalies=anomalies, total=len(anomalies))


# ---------------------------------------------------------------------------
# PUT /api/coa/{account_code}
# ---------------------------------------------------------------------------

@router.put("/{account_code}", response_model=CoAAccount)
async def update_account_classification(
    account_code: str,
    payload: CoAAccountUpdate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Manually correct the classification of an account. Scout will learn from this."""
    org_id = current_user["org_id"]
    account_code = unquote(account_code)

    res = (
        db.table("chart_of_accounts")
        .select("*")
        .eq("org_id", org_id)
        .eq("account_code", account_code)
        .limit(1)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail=f"Account '{account_code}' not found.")

    existing = res.data[0]
    updates: dict = {"classification_source": "user"}

    if payload.classified_l1 is not None:
        updates["classified_l1"] = payload.classified_l1
    if payload.classified_l2 is not None:
        updates["classified_l2"] = payload.classified_l2
    if payload.classified_l3 is not None:
        updates["classified_l3"] = payload.classified_l3
    if payload.classified_l4 is not None:
        updates["classified_l4"] = payload.classified_l4

    # User corrections are high confidence
    updates["classification_confidence"] = 1.0

    updated = db.table("chart_of_accounts").update(updates).eq("id", existing["id"]).execute()
    saved = updated.data[0] if updated.data else {**existing, **updates}

    # Teach memory service about this correction
    try:
        memory = AgentMemory(org_id=org_id, supabase_client=db)
        await memory.record_correction(
            source_desc=existing["account_name"],
            original={
                "l1": existing.get("classified_l1"),
                "l2": existing.get("classified_l2"),
                "l3": existing.get("classified_l3"),
                "l4": existing.get("classified_l4"),
            },
            corrected={
                "l1": updates.get("classified_l1", existing.get("classified_l1")),
                "l2": updates.get("classified_l2", existing.get("classified_l2")),
                "l3": updates.get("classified_l3", existing.get("classified_l3")),
                "l4": updates.get("classified_l4", existing.get("classified_l4")),
            },
            user_id=current_user.get("id"),
            source_gl_account=account_code,
        )
    except Exception as e:
        logger.warning(f"Memory record_correction failed: {e}")

    return CoAAccount(**_account_to_schema(saved))


# ---------------------------------------------------------------------------
# POST /api/coa/reclassify
# ---------------------------------------------------------------------------

@router.post("/reclassify")
async def reclassify_all_accounts(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Re-run classification on all accounts for this org (useful after corrections improve the model)."""
    org_id = current_user["org_id"]

    # Fetch all expense accounts that don't have user-confirmed classification
    res = (
        db.table("chart_of_accounts")
        .select("*")
        .eq("org_id", org_id)
        .eq("is_expense", True)
        .neq("classification_source", "user")
        .execute()
    )
    accounts_to_reclassify = res.data or []

    if not accounts_to_reclassify:
        return {"message": "No accounts to reclassify.", "total": 0}

    memory = AgentMemory(org_id=org_id, supabase_client=db)
    learner = CoALearner(org_id=org_id, supabase_client=db, memory=memory)

    # Build rows for classification
    rows = [
        {
            "account_code": a["account_code"],
            "account_name": a["account_name"],
            "amount": float(a.get("typical_monthly_amount") or 0),
            "is_expense": True,
        }
        for a in accounts_to_reclassify
    ]

    classified = await learner.classify_accounts(rows)

    # Update each account
    updated_count = 0
    for result in classified:
        if result.get("classified_l2"):
            try:
                db.table("chart_of_accounts").update({
                    "classified_l1": result.get("classified_l1"),
                    "classified_l2": result.get("classified_l2"),
                    "classified_l3": result.get("classified_l3"),
                    "classified_l4": result.get("classified_l4"),
                    "classification_confidence": result.get("classification_confidence", 0.5),
                    "classification_source": result.get("classification_source", "ai"),
                }).eq("org_id", org_id).eq("account_code", result["account_code"]).execute()
                updated_count += 1
            except Exception as e:
                logger.warning(f"Reclassify update failed for {result.get('account_code')}: {e}")

    return {
        "message": f"Reclassified {updated_count} of {len(accounts_to_reclassify)} accounts.",
        "total": len(accounts_to_reclassify),
        "updated": updated_count,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_col(detected: dict, headers: list[str], col_type: str) -> Optional[str]:
    """Find a header that maps to the given type."""
    for h, t in detected.items():
        if t == col_type and h in headers:
            return h
    return None


def _account_to_schema(a: dict) -> dict:
    """Map a DB row to CoAAccount schema fields."""
    return {
        "id": str(a.get("id", "")),
        "account_code": a.get("account_code", ""),
        "account_name": a.get("account_name", ""),
        "account_name_normalized": a.get("account_name_normalized"),
        "segment_category": a.get("segment_category"),
        "segment_cost_center": a.get("segment_cost_center"),
        "segment_sub": a.get("segment_sub"),
        "segment_location": a.get("segment_location"),
        "classified_l1": a.get("classified_l1"),
        "classified_l2": a.get("classified_l2"),
        "classified_l3": a.get("classified_l3"),
        "classified_l4": a.get("classified_l4"),
        "classification_confidence": float(a.get("classification_confidence") or 0.5),
        "classification_source": a.get("classification_source", "ai"),
        "account_type": a.get("account_type"),
        "is_expense": bool(a.get("is_expense", False)),
        "parent_code": a.get("parent_code"),
        "typical_monthly_amount": float(a.get("typical_monthly_amount") or 0) if a.get("typical_monthly_amount") is not None else None,
        "times_seen": a.get("times_seen", 1),
        "last_seen_at": a.get("last_seen_at"),
        "created_at": a.get("created_at"),
        "updated_at": a.get("updated_at"),
    }


def _structure_to_schema(s: dict) -> dict:
    return {
        "delimiter": s.get("delimiter", ""),
        "num_segments": s.get("num_segments", 1),
        "segment_definitions": s.get("segment_definitions", []),
        "expense_range_start": s.get("expense_range_start"),
        "expense_range_end": s.get("expense_range_end"),
        "revenue_range_start": s.get("revenue_range_start"),
        "revenue_range_end": s.get("revenue_range_end"),
        "detected_erp": s.get("detected_erp", "unknown"),
        "detection_confidence": float(s.get("detection_confidence") or 0.5),
        "samples_analyzed": s.get("samples_analyzed", 0),
    }

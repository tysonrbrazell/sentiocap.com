"""
Decisions router — signal detection alerts and status management.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from models.schemas import (
    DecisionResponse,
    DecisionUpdate,
    DecisionSummary,
    DecisionScanResult,
)
from services.signals import SignalDetector

router = APIRouter(prefix="/decisions", tags=["decisions"])


# ---------------------------------------------------------------------------
# GET /api/decisions/summary  — must be defined before /{id}
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=DecisionSummary)
def get_summary(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Counts by severity and status for the dashboard widget."""
    org_id = current_user["org_id"]

    res = (
        db.table("decisions")
        .select("severity, status")
        .eq("org_id", org_id)
        .execute()
    )
    rows = res.data or []

    by_severity = {"critical": 0, "warning": 0, "info": 0}
    by_status = {"new": 0, "acknowledged": 0, "in_progress": 0, "resolved": 0, "dismissed": 0}

    for row in rows:
        sev = row.get("severity")
        sta = row.get("status")
        if sev in by_severity:
            by_severity[sev] += 1
        if sta in by_status:
            by_status[sta] += 1

    total = len(rows)
    active = total - by_status["resolved"] - by_status["dismissed"]

    return DecisionSummary(
        total=total,
        active=active,
        by_severity=by_severity,
        by_status=by_status,
    )


# ---------------------------------------------------------------------------
# GET /api/decisions
# ---------------------------------------------------------------------------

@router.get("", response_model=list[DecisionResponse])
def list_decisions(
    severity: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    org_id = current_user["org_id"]

    q = (
        db.table("decisions")
        .select("*, investments(name)")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .range(offset, offset + limit - 1)
    )

    if severity:
        q = q.eq("severity", severity)
    if status:
        q = q.eq("status", status)
    if category:
        q = q.eq("category", category)

    res = q.execute()
    rows = res.data or []

    decisions = []
    for row in rows:
        inv_name = None
        if row.get("investments") and isinstance(row["investments"], dict):
            inv_name = row["investments"].get("name")
        decisions.append(DecisionResponse(
            **{k: v for k, v in row.items() if k != "investments"},
            investment_name=inv_name,
        ))
    return decisions


# ---------------------------------------------------------------------------
# POST /api/decisions/scan
# ---------------------------------------------------------------------------

@router.post("/scan", response_model=DecisionScanResult)
def run_scan(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Trigger a full signal scan for the org."""
    org_id = current_user["org_id"]
    detector = SignalDetector(db)
    new_decisions = detector.scan_all(org_id)
    return DecisionScanResult(
        new_decisions=len(new_decisions),
        decision_ids=[d["id"] for d in new_decisions if d.get("id")],
    )


# ---------------------------------------------------------------------------
# GET /api/decisions/{id}
# ---------------------------------------------------------------------------

@router.get("/{decision_id}", response_model=DecisionResponse)
def get_decision(
    decision_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    org_id = current_user["org_id"]

    res = (
        db.table("decisions")
        .select("*, investments(name)")
        .eq("id", str(decision_id))
        .eq("org_id", org_id)
        .single()
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=404, detail="Decision not found")

    row = res.data
    inv_name = None
    if row.get("investments") and isinstance(row["investments"], dict):
        inv_name = row["investments"].get("name")

    return DecisionResponse(
        **{k: v for k, v in row.items() if k != "investments"},
        investment_name=inv_name,
    )


# ---------------------------------------------------------------------------
# PUT /api/decisions/{id}
# ---------------------------------------------------------------------------

@router.put("/{decision_id}", response_model=DecisionResponse)
def update_decision(
    decision_id: UUID,
    payload: DecisionUpdate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    org_id = current_user["org_id"]

    # Verify ownership
    existing = (
        db.table("decisions")
        .select("id")
        .eq("id", str(decision_id))
        .eq("org_id", org_id)
        .single()
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Decision not found")

    update_data: dict = {}
    if payload.status is not None:
        update_data["status"] = payload.status
        if payload.status == "resolved":
            from datetime import datetime, timezone
            update_data["resolved_at"] = datetime.now(timezone.utc).isoformat()
            update_data["resolved_by"] = current_user["id"]
    if payload.owner is not None:
        update_data["owner"] = payload.owner
    if payload.resolution_notes is not None:
        update_data["resolution_notes"] = payload.resolution_notes

    if not update_data:
        raise HTTPException(status_code=400, detail="No fields to update")

    res = (
        db.table("decisions")
        .update(update_data)
        .eq("id", str(decision_id))
        .execute()
    )

    # Re-fetch with investment join
    updated = (
        db.table("decisions")
        .select("*, investments(name)")
        .eq("id", str(decision_id))
        .single()
        .execute()
    )
    row = updated.data
    inv_name = None
    if row.get("investments") and isinstance(row["investments"], dict):
        inv_name = row["investments"].get("name")

    return DecisionResponse(
        **{k: v for k, v in row.items() if k != "investments"},
        investment_name=inv_name,
    )

"""
Investments router — CRUD + ROI.
"""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from models.schemas import (
    InvestmentCreate,
    InvestmentUpdate,
    InvestmentResponse,
    InvestmentListResponse,
    InvestmentROIResponse,
    PortfolioSummary,
    BenefitResponse,
    ROIMetrics,
    VarianceSignal,
)
from services.analysis import calculate_roi

router = APIRouter(prefix="/investments", tags=["investments"])


def _get_investment(inv_id: str, org_id: str, db: Client) -> dict:
    result = (
        db.table("investments")
        .select("*")
        .eq("id", inv_id)
        .eq("org_id", org_id)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Investment not found")
    return result.data


def _enrich_investment(inv: dict, db: Client) -> InvestmentResponse:
    # Fetch benefits
    benefits_res = (
        db.table("investment_benefits")
        .select("*")
        .eq("investment_id", inv["id"])
        .execute()
    )
    benefits_raw = benefits_res.data or []
    benefits = []
    total_target = 0.0
    total_actual = 0.0
    for b in benefits_raw:
        target = b.get("target_value") or 0
        actual = b.get("actual_value") or 0
        total_target += target
        total_actual += actual
        pct = round(actual / target * 100, 1) if target else None
        benefits.append(BenefitResponse(**b, realization_pct=pct))

    # Fetch monthly spend
    spend_res = (
        db.table("investment_spend_monthly")
        .select("*")
        .eq("investment_id", inv["id"])
        .order("period")
        .execute()
    )
    spend_monthly = spend_res.data or []

    # ROI calculation
    roi_metrics = None
    try:
        roi_data = calculate_roi(inv, benefits_raw)
        roi_metrics = ROIMetrics(**roi_data)
    except Exception:
        pass

    benefits_realized_pct = None
    if total_target > 0:
        benefits_realized_pct = round(total_actual / total_target * 100, 1)

    return InvestmentResponse(
        id=inv["id"],
        name=inv["name"],
        description=inv.get("description"),
        owner=inv.get("owner"),
        l2_category=inv.get("l2_category"),
        l3_domain=inv.get("l3_domain"),
        l4_activity=inv.get("l4_activity"),
        status=inv["status"],
        start_date=inv.get("start_date"),
        target_completion=inv.get("target_completion"),
        planned_total=inv.get("planned_total"),
        actual_total=inv.get("actual_total") or 0,
        strategic_rating=inv.get("strategic_rating"),
        benefits=benefits,
        spend_monthly=spend_monthly,
        roi=roi_metrics,
        benefit_count=len(benefits),
        benefits_realized_pct=benefits_realized_pct,
        created_at=inv["created_at"],
        updated_at=inv["updated_at"],
    )


# ---------------------------------------------------------------------------
# GET /api/investments
# ---------------------------------------------------------------------------

@router.get("/", response_model=InvestmentListResponse)
def list_investments(
    inv_status: Optional[str] = Query(None, alias="status"),
    l2: Optional[str] = Query(None),
    plan_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    q = db.table("investments").select("*").eq("org_id", current_user["org_id"])
    if inv_status:
        q = q.eq("status", inv_status)
    if l2:
        q = q.eq("l2_category", l2)
    if plan_id:
        q = q.eq("plan_id", plan_id)

    result = q.order("created_at", desc=True).execute()
    investments_raw = result.data or []

    investments = [_enrich_investment(inv, db) for inv in investments_raw]

    # Portfolio summary
    total_planned = sum(i.planned_total or 0 for i in investments)
    total_actual = sum(i.actual_total or 0 for i in investments)
    deployment_rate = round(total_actual / total_planned * 100, 1) if total_planned else 0
    at_risk = sum(
        1 for i in investments
        if i.roi and i.roi.signal in (VarianceSignal.RED, VarianceSignal.YELLOW)
    )
    rois = [i.roi.current_roi for i in investments if i.roi and i.roi.current_roi]
    portfolio_roi = round(sum(rois) / len(rois), 2) if rois else None

    return InvestmentListResponse(
        investments=investments,
        total=len(investments),
        portfolio_summary=PortfolioSummary(
            total_planned=total_planned,
            total_actual=total_actual,
            deployment_rate=deployment_rate,
            portfolio_roi=portfolio_roi,
            at_risk_count=at_risk,
        ),
    )


# ---------------------------------------------------------------------------
# POST /api/investments
# ---------------------------------------------------------------------------

@router.post("/", response_model=InvestmentResponse, status_code=201)
def create_investment(
    payload: InvestmentCreate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    data = {
        "org_id": current_user["org_id"],
        "name": payload.name,
        "description": payload.description,
        "owner": payload.owner,
        "l2_category": payload.l2_category.value if payload.l2_category else None,
        "l3_domain": payload.l3_domain.value if payload.l3_domain else None,
        "l4_activity": payload.l4_activity,
        "status": payload.status.value,
        "start_date": payload.start_date.isoformat() if payload.start_date else None,
        "target_completion": payload.target_completion.isoformat() if payload.target_completion else None,
        "planned_total": payload.planned_total,
        "strategic_rating": payload.strategic_rating,
        "plan_id": str(payload.plan_id) if payload.plan_id else None,
        "notes": payload.notes,
        "created_by": current_user["id"],
    }
    result = db.table("investments").insert(data).execute()
    inv = result.data[0]

    # Insert benefits
    if payload.benefits:
        benefits_data = [
            {
                "investment_id": inv["id"],
                "benefit_type": b.benefit_type,
                "description": b.description,
                "calculation_method": b.calculation_method.value,
                "formula": b.formula,
                "target_value": b.target_value,
                "actual_value": b.actual_value,
                "measurement_start": b.measurement_start.isoformat() if b.measurement_start else None,
                "measurement_source": b.measurement_source,
                "confidence": b.confidence.value,
                "notes": b.notes,
            }
            for b in payload.benefits
        ]
        db.table("investment_benefits").insert(benefits_data).execute()

    return _enrich_investment(inv, db)


# ---------------------------------------------------------------------------
# GET /api/investments/:id
# ---------------------------------------------------------------------------

@router.get("/{inv_id}", response_model=InvestmentResponse)
def get_investment(
    inv_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    inv = _get_investment(inv_id, current_user["org_id"], db)
    return _enrich_investment(inv, db)


# ---------------------------------------------------------------------------
# PUT /api/investments/:id
# ---------------------------------------------------------------------------

@router.put("/{inv_id}", response_model=InvestmentResponse)
def update_investment(
    inv_id: str,
    payload: InvestmentUpdate,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    _get_investment(inv_id, current_user["org_id"], db)
    updates = {}
    for field, val in payload.model_dump(exclude_unset=True).items():
        if val is None:
            continue
        if field == "l2_category":
            updates[field] = val.value if hasattr(val, "value") else val
        elif field == "l3_domain":
            updates[field] = val.value if hasattr(val, "value") else val
        elif field == "status":
            updates[field] = val.value if hasattr(val, "value") else val
        elif field in ("start_date", "target_completion") and val:
            updates[field] = val.isoformat() if hasattr(val, "isoformat") else val
        else:
            updates[field] = val

    result = db.table("investments").update(updates).eq("id", inv_id).execute()
    inv = result.data[0]
    return _enrich_investment(inv, db)


# ---------------------------------------------------------------------------
# DELETE /api/investments/:id
# ---------------------------------------------------------------------------

@router.delete("/{inv_id}", status_code=204)
def delete_investment(
    inv_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    _get_investment(inv_id, current_user["org_id"], db)
    db.table("investments").delete().eq("id", inv_id).execute()


# ---------------------------------------------------------------------------
# GET /api/investments/:id/roi
# ---------------------------------------------------------------------------

@router.get("/{inv_id}/roi", response_model=InvestmentROIResponse)
def get_investment_roi(
    inv_id: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    inv = _get_investment(inv_id, current_user["org_id"], db)

    benefits_res = (
        db.table("investment_benefits")
        .select("*")
        .eq("investment_id", inv_id)
        .execute()
    )
    benefits_raw = benefits_res.data or []

    spend_res = (
        db.table("investment_spend_monthly")
        .select("*")
        .eq("investment_id", inv_id)
        .order("period")
        .execute()
    )
    spend_monthly = spend_res.data or []

    roi_data = calculate_roi(inv, benefits_raw)

    total_planned_spend = sum(s.get("planned", 0) or 0 for s in spend_monthly)
    total_actual_spend = inv.get("actual_total") or 0

    benefit_breakdown = []
    for b in benefits_raw:
        target = b.get("target_value") or 0
        actual = b.get("actual_value") or 0
        benefit_breakdown.append({
            "benefit_type": b.get("benefit_type"),
            "target": target,
            "actual": actual,
            "realization_pct": round(actual / target * 100, 1) if target else None,
            "confidence": b.get("confidence"),
        })

    return InvestmentROIResponse(
        investment_id=inv["id"],
        name=inv["name"],
        total_costs=roi_data.get("total_costs", 0),
        total_benefits=roi_data.get("total_benefits", 0),
        roi=roi_data.get("current_roi"),
        roi_pct=roi_data.get("roi_pct"),
        npv_roi=roi_data.get("npv_roi"),
        payback_months=roi_data.get("payback_months"),
        discount_rate=0.10,
        composite_score=roi_data.get("composite_score"),
        signal=VarianceSignal(roi_data.get("signal", "YELLOW")),
        benefit_breakdown=benefit_breakdown,
        spend_vs_plan={
            "total_planned": total_planned_spend,
            "total_actual": total_actual_spend,
            "deployment_pct": round(total_actual_spend / total_planned_spend * 100, 1)
            if total_planned_spend else 0,
        },
    )

"""
Dashboard router — summary KPIs, treemap, variance, benchmarks, timeseries.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from models.schemas import (
    DashboardSummary,
    RTBSummary,
    CTBSummary,
    InvestmentSummary,
    L2Summary,
    TreemapNode,
    VarianceResponse,
    VarianceRecord,
    BenchmarkResponse,
    BenchmarkComparisonItem,
    TimeseriesResponse,
    TimeseriesPoint,
    VarianceSignal,
)
from services.analysis import calculate_variance
from services.benchmarks import get_sector_benchmarks

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

L2_COLORS = {
    "RTB-OPS": "#3B82F6",
    "RTB-MNT": "#60A5FA",
    "RTB-CMP": "#93C5FD",
    "RTB-SUP": "#BFDBFE",
    "CTB-GRW": "#10B981",
    "CTB-TRN": "#34D399",
    "CTB-EFF": "#6EE7B7",
    "CTB-INN": "#A7F3D0",
}


def _signal_for_pct(pct_diff: float) -> VarianceSignal:
    abs_diff = abs(pct_diff)
    if abs_diff <= 5:
        return VarianceSignal.GREEN
    elif abs_diff <= 15:
        return VarianceSignal.YELLOW
    return VarianceSignal.RED


# ---------------------------------------------------------------------------
# GET /api/dashboard/summary
# ---------------------------------------------------------------------------

@router.get("/summary", response_model=DashboardSummary)
def get_summary(
    plan_id: Optional[str] = Query(None),
    fiscal_year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    org_id = current_user["org_id"]

    # Fetch org
    org_res = db.table("organizations").select("*").eq("id", org_id).single().execute()
    org = org_res.data or {}

    # Find plan
    if not plan_id:
        q = db.table("plans").select("*").eq("org_id", org_id).eq("status", "approved")
        if fiscal_year:
            q = q.eq("fiscal_year", fiscal_year)
        plan_res = q.order("fiscal_year", desc=True).limit(1).execute()
        plan = (plan_res.data or [None])[0]
    else:
        plan_res = db.table("plans").select("*").eq("id", plan_id).single().execute()
        plan = plan_res.data

    if not plan:
        # Fallback: empty summary
        return DashboardSummary(
            org={"name": org.get("name", ""), "sector": org.get("sector", "")},
            fiscal_year=fiscal_year or 2027,
            total_budget=0,
            rtb=RTBSummary(total=0, pct=0, signal=VarianceSignal.GREEN),
            ctb=CTBSummary(total=0, pct=0, signal=VarianceSignal.GREEN),
            investments=InvestmentSummary(),
        )

    # Aggregate line items
    items_res = (
        db.table("plan_line_items")
        .select("classified_l1, classified_l2, annual_total")
        .eq("plan_id", plan["id"])
        .execute()
    )
    items = items_res.data or []

    rtb_total = sum(i["annual_total"] or 0 for i in items if i.get("classified_l1") == "RTB")
    ctb_total = sum(i["annual_total"] or 0 for i in items if i.get("classified_l1") == "CTB")
    total = rtb_total + ctb_total

    rtb_pct = round(rtb_total / total * 100, 1) if total else 0
    ctb_pct = round(ctb_total / total * 100, 1) if total else 0

    by_l2_amounts: dict[str, float] = {}
    for item in items:
        l2 = item.get("classified_l2")
        if l2:
            by_l2_amounts[l2] = by_l2_amounts.get(l2, 0) + (item.get("annual_total") or 0)

    # Fetch sector benchmarks
    benchmarks = get_sector_benchmarks(org.get("sector", ""), plan.get("fiscal_year", 2025), db)
    ctb_peer_median = None
    rtb_peer_median = None
    if benchmarks:
        ctb_pcts = [b.get("median_pct", 0) for b in benchmarks if b.get("l2_category", "").startswith("CTB")]
        rtb_pcts = [b.get("median_pct", 0) for b in benchmarks if b.get("l2_category", "").startswith("RTB")]
        ctb_peer_median = sum(ctb_pcts) if ctb_pcts else None
        rtb_peer_median = sum(rtb_pcts) if rtb_pcts else None

    # Investment summary
    inv_res = (
        db.table("investments")
        .select("id, status, planned_total, actual_total")
        .eq("org_id", org_id)
        .in_("status", ["proposed", "approved", "in_progress"])
        .execute()
    )
    invs = inv_res.data or []
    total_inv_planned = sum(i.get("planned_total") or 0 for i in invs)
    total_inv_actual = sum(i.get("actual_total") or 0 for i in invs)
    deployment_rate = round(total_inv_actual / total_inv_planned * 100, 1) if total_inv_planned else None

    by_l2_summary: dict[str, L2Summary] = {}
    for l2_code, amount in by_l2_amounts.items():
        pct = round(amount / total * 100, 1) if total else 0
        by_l2_summary[l2_code] = L2Summary(
            amount=amount,
            pct=pct,
            signal=VarianceSignal.GREEN,
        )

    return DashboardSummary(
        org={"name": org.get("name", ""), "sector": org.get("sector", "")},
        fiscal_year=plan.get("fiscal_year", fiscal_year or 2027),
        plan_id=plan["id"],
        plan_name=plan.get("name"),
        total_budget=total,
        rtb=RTBSummary(
            total=rtb_total,
            pct=rtb_pct,
            peer_median_pct=rtb_peer_median,
            signal=VarianceSignal.GREEN,
        ),
        ctb=CTBSummary(
            total=ctb_total,
            pct=ctb_pct,
            peer_median_pct=ctb_peer_median,
            signal=VarianceSignal.GREEN,
            deployment_rate=deployment_rate,
        ),
        investments=InvestmentSummary(
            active_count=len(invs),
            deployment_rate=deployment_rate,
        ),
        by_l2=by_l2_summary,
    )


# ---------------------------------------------------------------------------
# GET /api/dashboard/treemap
# ---------------------------------------------------------------------------

@router.get("/treemap", response_model=TreemapNode)
def get_treemap(
    plan_id: Optional[str] = Query(None),
    fiscal_year: Optional[int] = Query(None),
    depth: int = Query(3, ge=1, le=4),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    org_id = current_user["org_id"]

    if not plan_id:
        q = db.table("plans").select("id").eq("org_id", org_id).eq("status", "approved")
        if fiscal_year:
            q = q.eq("fiscal_year", fiscal_year)
        plan_res = q.order("fiscal_year", desc=True).limit(1).execute()
        plans = plan_res.data or []
        if not plans:
            return TreemapNode(name="Total Budget", value=0)
        plan_id = plans[0]["id"]

    items_res = (
        db.table("plan_line_items")
        .select("classified_l1, classified_l2, classified_l3, classified_l4, annual_total")
        .eq("plan_id", plan_id)
        .execute()
    )
    items = items_res.data or []

    # Build hierarchy
    total = sum(i.get("annual_total") or 0 for i in items)

    # L1 → L2 → L3
    hierarchy: dict = {}
    for item in items:
        l1 = item.get("classified_l1") or "Unknown"
        l2 = item.get("classified_l2") or "Unknown"
        l3 = item.get("classified_l3") or "Unknown"
        amt = item.get("annual_total") or 0

        if l1 not in hierarchy:
            hierarchy[l1] = {}
        if l2 not in hierarchy[l1]:
            hierarchy[l1][l2] = {}
        if l3 not in hierarchy[l1][l2]:
            hierarchy[l1][l2][l3] = 0
        hierarchy[l1][l2][l3] += amt

    l1_nodes = []
    for l1, l2_map in hierarchy.items():
        l2_nodes = []
        l1_total = sum(sum(l3_map.values()) for l3_map in l2_map.values())
        for l2, l3_map in l2_map.items():
            l2_total = sum(l3_map.values())
            if depth >= 3:
                l3_nodes = [
                    TreemapNode(
                        name=l3,
                        value=amt,
                        pct=round(amt / total * 100, 1) if total else 0,
                    )
                    for l3, amt in l3_map.items()
                ]
            else:
                l3_nodes = []
            l2_nodes.append(
                TreemapNode(
                    name=l2,
                    value=l2_total,
                    color=L2_COLORS.get(l2),
                    children=l3_nodes if depth >= 3 else [],
                )
            )
        color = "#3B82F6" if l1 == "RTB" else "#10B981"
        l1_nodes.append(
            TreemapNode(
                name=l1,
                value=l1_total,
                color=color,
                children=l2_nodes if depth >= 2 else [],
            )
        )

    return TreemapNode(name="Total Budget", value=total, children=l1_nodes)


# ---------------------------------------------------------------------------
# GET /api/dashboard/variance
# ---------------------------------------------------------------------------

@router.get("/variance", response_model=VarianceResponse)
def get_variance(
    period: str = Query(...),
    plan_id: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    org_id = current_user["org_id"]

    if not plan_id:
        plan_res = (
            db.table("plans")
            .select("id")
            .eq("org_id", org_id)
            .eq("status", "approved")
            .order("fiscal_year", desc=True)
            .limit(1)
            .execute()
        )
        plans = plan_res.data or []
        plan_id = plans[0]["id"] if plans else None

    variances = calculate_variance(plan_id, period, org_id, db) if plan_id else []

    return VarianceResponse(
        period=period,
        plan_id=plan_id,
        variances=[VarianceRecord(**v) for v in variances],
    )


# ---------------------------------------------------------------------------
# GET /api/dashboard/benchmarks
# ---------------------------------------------------------------------------

@router.get("/benchmarks", response_model=BenchmarkResponse)
def get_benchmarks(
    sector: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    org_id = current_user["org_id"]
    org_res = db.table("organizations").select("*").eq("id", org_id).single().execute()
    org = org_res.data or {}

    use_sector = sector or org.get("sector", "")
    use_year = year or 2025

    benchmarks = get_sector_benchmarks(use_sector, use_year, db)

    # Get org's current plan data for comparison
    plan_res = (
        db.table("plans")
        .select("id")
        .eq("org_id", org_id)
        .eq("status", "approved")
        .order("fiscal_year", desc=True)
        .limit(1)
        .execute()
    )
    org_l2: dict[str, float] = {}
    org_total = 0.0
    if plan_res.data:
        items_res = (
            db.table("plan_line_items")
            .select("classified_l2, annual_total")
            .eq("plan_id", plan_res.data[0]["id"])
            .execute()
        )
        items = items_res.data or []
        org_total = sum(i.get("annual_total") or 0 for i in items)
        for item in items:
            l2 = item.get("classified_l2")
            if l2:
                org_l2[l2] = org_l2.get(l2, 0) + (item.get("annual_total") or 0)

    comparison = []
    for b in benchmarks:
        l2_code = b.get("l2_category", "")
        org_amount = org_l2.get(l2_code, 0)
        org_pct = round(org_amount / org_total * 100, 2) if org_total else None
        peer_median = b.get("median_pct")
        signal = VarianceSignal.GREEN
        insight = None
        if org_pct is not None and peer_median:
            diff = org_pct - peer_median
            signal = _signal_for_pct(diff / peer_median * 100 if peer_median else 0)
            if signal == VarianceSignal.RED:
                insight = f"{l2_code} spend is significantly off vs {use_sector} sector peers."

        comparison.append(
            BenchmarkComparisonItem(
                l2_category=l2_code,
                org_pct=org_pct,
                peer_p25=b.get("p25_pct"),
                peer_median=peer_median,
                peer_p75=b.get("p75_pct"),
                signal=signal,
                insight=insight,
            )
        )

    return BenchmarkResponse(
        org={"name": org.get("name", ""), "sector": org.get("sector", "")},
        benchmark_year=use_year,
        benchmark_sector=use_sector,
        comparison=comparison,
    )


# ---------------------------------------------------------------------------
# GET /api/dashboard/timeseries
# ---------------------------------------------------------------------------

@router.get("/timeseries", response_model=TimeseriesResponse)
def get_timeseries(
    from_period: str = Query(...),
    to_period: str = Query(...),
    granularity: str = Query("monthly"),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    org_id = current_user["org_id"]

    # Fetch actuals in range
    actuals_res = (
        db.table("actuals")
        .select("period, classified_l1, amount")
        .eq("org_id", org_id)
        .gte("period", from_period)
        .lte("period", to_period)
        .execute()
    )
    actuals = actuals_res.data or []

    # Group by period
    by_period: dict[str, dict] = {}
    for a in actuals:
        p = a.get("period", "")
        if p not in by_period:
            by_period[p] = {"rtb": 0.0, "ctb": 0.0}
        l1 = a.get("classified_l1", "")
        amount = a.get("amount") or 0
        if l1 == "RTB":
            by_period[p]["rtb"] += amount
        elif l1 == "CTB":
            by_period[p]["ctb"] += amount

    series = []
    for period in sorted(by_period.keys()):
        rtb = by_period[period]["rtb"]
        ctb = by_period[period]["ctb"]
        total = rtb + ctb
        series.append(
            TimeseriesPoint(
                period=period,
                rtb_actual=rtb,
                ctb_actual=ctb,
                rtb_pct=round(rtb / total * 100, 1) if total else None,
                ctb_pct=round(ctb / total * 100, 1) if total else None,
            )
        )

    return TimeseriesResponse(series=series)

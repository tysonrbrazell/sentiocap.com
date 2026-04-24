"""
Analysis service — variance, ROI, and reforecast calculations.
"""
import logging
from typing import Optional
from supabase import Client

logger = logging.getLogger(__name__)

DISCOUNT_RATE = 0.10  # 10% annual discount rate


def calculate_variance(
    plan_id: str,
    period: str,
    org_id: str,
    db: Client,
) -> list[dict]:
    """Compute plan vs actuals variance by L2 category for a given period.

    Returns a list of variance dicts, one per L2 category.
    """
    # Parse period: YYYY-MM
    try:
        year, month = period.split("-")
        month_num = int(month)
    except Exception:
        logger.error(f"Invalid period format: {period}")
        return []

    month_col = _month_col(month_num)
    if not month_col:
        return []

    # Fetch plan line items for this period's month column
    items_res = (
        db.table("plan_line_items")
        .select(f"classified_l2, {month_col}")
        .eq("plan_id", plan_id)
        .execute()
    )
    plan_items = items_res.data or []

    # Aggregate planned amounts by L2
    planned_by_l2: dict[str, float] = {}
    for item in plan_items:
        l2 = item.get("classified_l2")
        if l2:
            planned_by_l2[l2] = planned_by_l2.get(l2, 0) + (item.get(month_col) or 0)

    # Fetch actuals for this period
    actuals_res = (
        db.table("actuals")
        .select("classified_l2, amount")
        .eq("org_id", org_id)
        .eq("period", period)
        .execute()
    )
    actuals = actuals_res.data or []

    actual_by_l2: dict[str, float] = {}
    for a in actuals:
        l2 = a.get("classified_l2")
        if l2:
            actual_by_l2[l2] = actual_by_l2.get(l2, 0) + (a.get("amount") or 0)

    # YTD: sum all months from start of year through current month
    ytd_months = [_month_col(m) for m in range(1, month_num + 1) if _month_col(m)]
    ytd_planned_by_l2: dict[str, float] = {}
    for m_col in ytd_months:
        ytd_res = (
            db.table("plan_line_items")
            .select(f"classified_l2, {m_col}")
            .eq("plan_id", plan_id)
            .execute()
        )
        for item in (ytd_res.data or []):
            l2 = item.get("classified_l2")
            if l2:
                ytd_planned_by_l2[l2] = ytd_planned_by_l2.get(l2, 0) + (item.get(m_col) or 0)

    # YTD actuals: all periods from YYYY-01 through current period
    ytd_start = f"{year}-01"
    ytd_actuals_res = (
        db.table("actuals")
        .select("classified_l2, amount")
        .eq("org_id", org_id)
        .gte("period", ytd_start)
        .lte("period", period)
        .execute()
    )
    ytd_actual_by_l2: dict[str, float] = {}
    for a in (ytd_actuals_res.data or []):
        l2 = a.get("classified_l2")
        if l2:
            ytd_actual_by_l2[l2] = ytd_actual_by_l2.get(l2, 0) + (a.get("amount") or 0)

    # Build variance records
    all_l2s = set(list(planned_by_l2.keys()) + list(actual_by_l2.keys()))
    variances = []

    for l2 in sorted(all_l2s):
        planned = planned_by_l2.get(l2, 0)
        actual = actual_by_l2.get(l2, 0)
        variance_amount = actual - planned
        variance_pct = round((variance_amount / planned * 100), 2) if planned else 0.0

        ytd_planned = ytd_planned_by_l2.get(l2, 0)
        ytd_actual = ytd_actual_by_l2.get(l2, 0)

        # Reforecast: extrapolate YTD run rate to full year
        full_year_forecast = None
        if month_num > 0 and ytd_actual > 0:
            full_year_forecast = round(ytd_actual / month_num * 12, 2)

        # Signal
        abs_pct = abs(variance_pct)
        if abs_pct <= 5:
            signal = "GREEN"
        elif abs_pct <= 15:
            signal = "YELLOW"
        else:
            signal = "RED"

        # Signal reason for significant deviations
        signal_reason = None
        if signal == "RED" and l2.startswith("CTB") and variance_amount < 0:
            signal_reason = f"{l2} under-execution: only {round(actual / planned * 100, 0) if planned else 0}% of planned spend deployed."

        variances.append({
            "l2_category": l2,
            "planned": planned,
            "actual": actual,
            "variance_amount": variance_amount,
            "variance_pct": variance_pct,
            "ytd_planned": ytd_planned,
            "ytd_actual": ytd_actual,
            "full_year_forecast": full_year_forecast,
            "signal": signal,
            "signal_reason": signal_reason,
        })

    return variances


def calculate_roi(investment: dict, benefits: list[dict]) -> dict:
    """Calculate ROI metrics for an investment.

    Returns dict with: total_costs, total_benefits, current_roi, roi_pct,
    npv_roi, payback_months, composite_score, signal
    """
    total_costs = investment.get("actual_total") or 0
    if not total_costs:
        total_costs = investment.get("planned_total") or 0

    total_benefits = sum(b.get("actual_value") or 0 for b in benefits)

    current_roi = None
    roi_pct = None
    if total_costs > 0:
        current_roi = round(total_benefits / total_costs, 2)
        roi_pct = round((total_benefits - total_costs) / total_costs * 100, 1)

    # Planned ROI (using target values)
    planned_benefits = sum(b.get("target_value") or 0 for b in benefits)
    planned_total = investment.get("planned_total") or 0
    planned_roi = None
    if planned_total > 0 and planned_benefits > 0:
        planned_roi = round(planned_benefits / planned_total, 2)

    # Simple payback: months until cumulative benefits >= costs
    payback_months = None
    if total_benefits > 0 and total_costs > 0:
        monthly_benefit = total_benefits / 12  # crude annual → monthly
        if monthly_benefit > 0:
            payback_months = int(total_costs / monthly_benefit)

    # NPV ROI (simple discounted version)
    npv_roi = None
    if current_roi is not None:
        npv_roi = round(current_roi / (1 + DISCOUNT_RATE), 2)

    # Composite score (0-100)
    composite_score = None
    if current_roi is not None:
        score = min(int(current_roi * 33), 100)
        if investment.get("strategic_rating"):
            score = int(score * 0.7 + investment["strategic_rating"] * 6)
        composite_score = min(score, 100)

    # Signal
    signal = "YELLOW"
    if current_roi is not None:
        if current_roi >= 2.0:
            signal = "GREEN"
        elif current_roi >= 1.0:
            signal = "YELLOW"
        else:
            signal = "RED"

    return {
        "total_costs": total_costs,
        "total_benefits": total_benefits,
        "current_roi": current_roi,
        "planned_roi": planned_roi,
        "roi_pct": roi_pct,
        "npv_roi": npv_roi,
        "payback_months": payback_months,
        "composite_score": composite_score,
        "signal": signal,
    }


def calculate_reforecast(plan_id: str, latest_period: str, db: Client) -> dict:
    """Project full-year spend based on YTD actuals and remaining plan.

    Args:
        plan_id: plan UUID
        latest_period: last uploaded period, e.g. '2027-03'
        db: Supabase client

    Returns dict with: period, total_forecast, by_l2, deployment_pct
    """
    try:
        _, month_str = latest_period.split("-")
        month_num = int(month_str)
    except Exception:
        return {}

    # YTD actuals by L2
    plan_res = db.table("plans").select("org_id").eq("id", plan_id).single().execute()
    if not plan_res.data:
        return {}
    org_id = plan_res.data["org_id"]

    year = latest_period.split("-")[0]
    ytd_actuals_res = (
        db.table("actuals")
        .select("classified_l2, amount")
        .eq("org_id", org_id)
        .gte("period", f"{year}-01")
        .lte("period", latest_period)
        .execute()
    )
    ytd_by_l2: dict[str, float] = {}
    for a in (ytd_actuals_res.data or []):
        l2 = a.get("classified_l2")
        if l2:
            ytd_by_l2[l2] = ytd_by_l2.get(l2, 0) + (a.get("amount") or 0)

    # Remaining plan months
    remaining_months = list(range(month_num + 1, 13))
    remaining_cols = [_month_col(m) for m in remaining_months if _month_col(m)]

    remaining_plan_by_l2: dict[str, float] = {}
    for col in remaining_cols:
        items_res = (
            db.table("plan_line_items")
            .select(f"classified_l2, {col}")
            .eq("plan_id", plan_id)
            .execute()
        )
        for item in (items_res.data or []):
            l2 = item.get("classified_l2")
            if l2:
                remaining_plan_by_l2[l2] = remaining_plan_by_l2.get(l2, 0) + (item.get(col) or 0)

    # Combine: YTD actuals + remaining plan
    all_l2s = set(list(ytd_by_l2.keys()) + list(remaining_plan_by_l2.keys()))
    by_l2_forecast: dict[str, float] = {}
    for l2 in all_l2s:
        by_l2_forecast[l2] = ytd_by_l2.get(l2, 0) + remaining_plan_by_l2.get(l2, 0)

    total_forecast = sum(by_l2_forecast.values())

    return {
        "period": latest_period,
        "total_forecast": total_forecast,
        "by_l2": by_l2_forecast,
    }


def _month_col(month_num: int) -> Optional[str]:
    """Convert 1-12 to DB column name (jan, feb, ...)."""
    cols = ["jan", "feb", "mar", "apr", "may", "jun",
            "jul", "aug", "sep", "oct", "nov", "dec"]
    if 1 <= month_num <= 12:
        return cols[month_num - 1]
    return None

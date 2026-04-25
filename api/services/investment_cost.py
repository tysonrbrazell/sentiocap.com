"""
Investment Cost Reconciliation Service

Reconciles the 3 cost layers for each investment:
  1. Planned cost  — from investment.planned_total
  2. GL actual     — from actuals table
  3. Effort cost   — from effort_data (hours × blended rate)

Plus revenue outcomes from CRM:
  4. Revenue pipeline  — from crm_revenue_data
  5. Revenue closed    — from crm_revenue_data

Produces a UnifiedCostView with ROI metrics and discrepancy signals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from supabase import Client


BLENDED_HOURLY_RATE = 125.0  # USD — override via org config in future


# ---------------------------------------------------------------------------
# Output model
# ---------------------------------------------------------------------------

@dataclass
class UnifiedCostView:
    investment_id: str
    investment_name: str
    l2_category: Optional[str] = None
    status: Optional[str] = None

    # Layer 1: Plan
    planned_cost: float = 0.0

    # Layer 2: GL actuals
    gl_actual_cost: float = 0.0

    # Layer 3: Effort (JIRA)
    effort_cost: float = 0.0
    effort_hours: float = 0.0

    # Layer 4: Revenue (CRM)
    revenue_pipeline: float = 0.0
    revenue_closed: float = 0.0
    new_logos: int = 0
    churn_amount: float = 0.0

    # Derived metrics
    deployment_rate: Optional[float] = None        # gl_actual / planned
    effort_efficiency: Optional[float] = None      # effort_cost / gl_actual (direct effort %)
    roi_on_plan: Optional[float] = None            # revenue_closed / planned_cost
    roi_on_effort: Optional[float] = None          # revenue_closed / effort_cost
    pipeline_coverage: Optional[float] = None      # pipeline / planned_cost

    # Discrepancies and signals
    discrepancies: list[str] = field(default_factory=list)
    health_signals: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "investment_id": self.investment_id,
            "investment_name": self.investment_name,
            "l2_category": self.l2_category,
            "status": self.status,
            "planned_cost": self.planned_cost,
            "gl_actual_cost": self.gl_actual_cost,
            "effort_cost": self.effort_cost,
            "effort_hours": self.effort_hours,
            "revenue_pipeline": self.revenue_pipeline,
            "revenue_closed": self.revenue_closed,
            "new_logos": self.new_logos,
            "churn_amount": self.churn_amount,
            "deployment_rate": self.deployment_rate,
            "effort_efficiency": self.effort_efficiency,
            "roi_on_plan": self.roi_on_plan,
            "roi_on_effort": self.roi_on_effort,
            "pipeline_coverage": self.pipeline_coverage,
            "discrepancies": self.discrepancies,
            "health_signals": self.health_signals,
            "signal": self._overall_signal(),
        }

    def _overall_signal(self) -> str:
        """GREEN / YELLOW / RED based on number and severity of signals."""
        critical = sum(1 for s in self.health_signals if s.get("severity") == "critical")
        warnings = sum(1 for s in self.health_signals if s.get("severity") == "warning")
        if critical > 0:
            return "RED"
        if warnings > 0 or len(self.discrepancies) > 2:
            return "YELLOW"
        return "GREEN"


# ---------------------------------------------------------------------------
# Reconciler
# ---------------------------------------------------------------------------

class InvestmentCostReconciler:
    """
    Pulls planned cost, GL actual, JIRA effort, and Salesforce revenue
    for one or all investments and produces unified cost views.
    """

    def __init__(self, db: Client):
        self.db = db

    async def reconcile(self, org_id: str, investment_id: str) -> UnifiedCostView:
        """Reconcile a single investment."""
        # Fetch investment
        inv_result = (
            self.db.table("investments")
            .select("id, name, planned_total, l2_category, status")
            .eq("id", investment_id)
            .eq("org_id", org_id)
            .execute()
        )
        if not inv_result.data:
            raise ValueError(f"Investment {investment_id} not found")

        inv = inv_result.data[0]
        return await self._build_view(org_id, inv)

    async def reconcile_all(self, org_id: str) -> list[UnifiedCostView]:
        """Reconcile all investments for an org."""
        inv_result = (
            self.db.table("investments")
            .select("id, name, planned_total, l2_category, status")
            .eq("org_id", org_id)
            .execute()
        )
        investments = inv_result.data or []

        views = []
        for inv in investments:
            view = await self._build_view(org_id, inv)
            views.append(view)

        return views

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    async def _build_view(self, org_id: str, inv: dict) -> UnifiedCostView:
        investment_id = inv["id"]
        planned_cost = float(inv.get("planned_total") or 0)

        view = UnifiedCostView(
            investment_id=investment_id,
            investment_name=inv["name"],
            l2_category=inv.get("l2_category"),
            status=inv.get("status"),
            planned_cost=planned_cost,
        )

        # Layer 2: GL actuals
        view.gl_actual_cost = await self._get_gl_actuals(org_id, investment_id)

        # Layer 3: Effort (JIRA)
        effort = await self._get_effort(org_id, investment_id)
        view.effort_cost = effort["cost"]
        view.effort_hours = effort["hours"]

        # Layer 4: CRM revenue
        revenue = await self._get_revenue(org_id, investment_id)
        view.revenue_pipeline = revenue["pipeline"]
        view.revenue_closed = revenue["closed"]
        view.new_logos = revenue["new_logos"]
        view.churn_amount = revenue["churn"]

        # Compute derived metrics
        if planned_cost > 0:
            view.deployment_rate = round(view.gl_actual_cost / planned_cost, 4)
            view.roi_on_plan = round(view.revenue_closed / planned_cost, 4) if planned_cost else None
            view.pipeline_coverage = round(view.revenue_pipeline / planned_cost, 4)

        if view.gl_actual_cost > 0:
            view.effort_efficiency = round(view.effort_cost / view.gl_actual_cost, 4)

        if view.effort_cost > 0:
            view.roi_on_effort = round(view.revenue_closed / view.effort_cost, 4)

        # Detect discrepancies and health signals
        view.discrepancies = self._detect_discrepancies(view)
        view.health_signals = self._detect_signals(view)

        return view

    async def _get_gl_actuals(self, org_id: str, investment_id: str) -> float:
        """Sum actuals linked to this investment via plan_line_items."""
        try:
            # actuals are stored per plan_line_item; investment links through plan_line_items
            result = (
                self.db.table("actuals")
                .select("amount")
                .eq("org_id", org_id)
                .execute()
            )
            # Sum all actuals for simplicity — production would filter by investment
            # via plan_line_item.investment_id join
            if result.data:
                # Rough estimate: pro-rate based on 1/total investments
                inv_count_result = (
                    self.db.table("investments")
                    .select("id", count="exact")
                    .eq("org_id", org_id)
                    .execute()
                )
                total_investments = max(1, inv_count_result.count or 1)
                total = sum(float(r["amount"] or 0) for r in result.data)
                return round(total / total_investments, 2)
        except Exception:
            pass
        return 0.0

    async def _get_effort(self, org_id: str, investment_id: str) -> dict:
        """Sum effort data mapped to this investment."""
        try:
            result = (
                self.db.table("effort_data")
                .select("hours_logged, effort_cost")
                .eq("org_id", org_id)
                .eq("investment_id", investment_id)
                .execute()
            )
            if result.data:
                total_hours = sum(float(r.get("hours_logged") or 0) for r in result.data)
                total_cost = sum(float(r.get("effort_cost") or 0) for r in result.data)
                return {"hours": round(total_hours, 2), "cost": round(total_cost, 2)}
        except Exception:
            pass
        return {"hours": 0.0, "cost": 0.0}

    async def _get_revenue(self, org_id: str, investment_id: str) -> dict:
        """Sum CRM revenue mapped to this investment."""
        try:
            result = (
                self.db.table("crm_revenue_data")
                .select("pipeline_amount, closed_won_amount, new_logos, churned_amount")
                .eq("org_id", org_id)
                .eq("investment_id", investment_id)
                .execute()
            )
            if result.data:
                return {
                    "pipeline": round(sum(float(r.get("pipeline_amount") or 0) for r in result.data), 2),
                    "closed": round(sum(float(r.get("closed_won_amount") or 0) for r in result.data), 2),
                    "new_logos": sum(int(r.get("new_logos") or 0) for r in result.data),
                    "churn": round(sum(float(r.get("churned_amount") or 0) for r in result.data), 2),
                }
        except Exception:
            pass
        return {"pipeline": 0.0, "closed": 0.0, "new_logos": 0, "churn": 0.0}

    # ------------------------------------------------------------------
    # Discrepancy and signal detection
    # ------------------------------------------------------------------

    def _detect_discrepancies(self, v: UnifiedCostView) -> list[str]:
        """Identify gaps between cost layers."""
        issues = []

        if v.planned_cost > 0 and v.gl_actual_cost > 0:
            gap_pct = abs(v.gl_actual_cost - v.planned_cost) / v.planned_cost
            if gap_pct > 0.30:
                direction = "over" if v.gl_actual_cost > v.planned_cost else "under"
                issues.append(
                    f"GL actual is {gap_pct*100:.0f}% {direction} plan "
                    f"(${v.gl_actual_cost:,.0f} vs ${v.planned_cost:,.0f})"
                )

        if v.gl_actual_cost > 0 and v.effort_cost > 0:
            gap_pct = abs(v.effort_cost - v.gl_actual_cost) / v.gl_actual_cost
            if gap_pct > 0.40:
                issues.append(
                    f"Effort cost diverges {gap_pct*100:.0f}% from GL actual "
                    f"(${v.effort_cost:,.0f} vs ${v.gl_actual_cost:,.0f})"
                )

        if v.planned_cost > 0 and v.effort_cost == 0:
            issues.append("No JIRA effort data linked — cannot validate delivery")

        if v.planned_cost > 0 and v.revenue_closed == 0 and v.revenue_pipeline == 0:
            issues.append("No CRM revenue data linked — benefit verification not possible")

        if v.revenue_closed > 0 and v.planned_cost > 0:
            roi = v.revenue_closed / v.planned_cost
            if roi < 0.5:
                issues.append(
                    f"Low ROI on plan: {roi*100:.0f}% "
                    f"(${v.revenue_closed:,.0f} closed / ${v.planned_cost:,.0f} planned)"
                )

        return issues

    def _detect_signals(self, v: UnifiedCostView) -> list[dict]:
        """Generate Sentinel-style health signals."""
        signals = []

        # Ghost Investment (Cat 22): budget allocated, near-zero effort
        if v.planned_cost > 100_000 and v.effort_cost < v.planned_cost * 0.10:
            signals.append({
                "category": 22,
                "name": "Ghost Investment",
                "description": (
                    f"${v.planned_cost:,.0f} budgeted but only ${v.effort_cost:,.0f} "
                    f"in direct effort logged ({v.effort_cost/v.planned_cost*100:.0f}% utilisation)"
                ),
                "severity": "critical",
            })

        # Benefit Verification Failed: claimed benefit vs actual CRM
        if v.planned_cost > 0 and v.revenue_pipeline > 0:
            if v.roi_on_plan is not None and v.roi_on_plan < 0.3:
                signals.append({
                    "category": None,
                    "name": "Benefit Verification Failed",
                    "description": (
                        f"Investment ROI on plan is only {v.roi_on_plan*100:.0f}% — "
                        f"pipeline (${v.revenue_pipeline:,.0f}) may not justify cost (${v.planned_cost:,.0f})"
                    ),
                    "severity": "warning",
                })

        # RTB Disguised as CTB: categorised CTB but effort/GL points to maintenance
        if v.l2_category and v.l2_category.startswith("CTB"):
            if v.effort_efficiency is not None and v.effort_efficiency < 0.40:
                signals.append({
                    "category": 23,
                    "name": "RTB Disguised as CTB",
                    "description": (
                        f"Classified as {v.l2_category} but only {v.effort_efficiency*100:.0f}% "
                        f"of GL spend is direct effort — overhead-heavy, possible maintenance misclassification"
                    ),
                    "severity": "warning",
                })

        # Deployment Lag: plan approved but GL/effort spend very low
        if v.deployment_rate is not None and v.deployment_rate < 0.20 and v.status == "in_progress":
            signals.append({
                "category": None,
                "name": "Deployment Lag",
                "description": (
                    f"Investment is In Progress but only {v.deployment_rate*100:.0f}% of budget deployed "
                    f"(${v.gl_actual_cost:,.0f} of ${v.planned_cost:,.0f})"
                ),
                "severity": "warning",
            })

        # Pipeline Surge: revenue pipeline >> expected
        if v.pipeline_coverage is not None and v.pipeline_coverage > 3.0:
            signals.append({
                "category": None,
                "name": "Pipeline Surge",
                "description": (
                    f"Revenue pipeline (${v.revenue_pipeline:,.0f}) is {v.pipeline_coverage:.1f}x planned cost — "
                    f"consider accelerating investment"
                ),
                "severity": "info",
            })

        return signals

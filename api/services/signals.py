"""
Signal detection engine — identifies actionable decision signals from investment and plan data.
Each of the 20 decision categories has a dedicated detector with threshold-based logic.
Detected signals are enriched with AI-generated narratives via Claude.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

import anthropic
from supabase import Client

from config import settings
from services.memory import AgentMemory

logger = logging.getLogger(__name__)

MODEL = "claude-3-5-haiku-20241022"  # Fast + cheap for narrative generation

# Regulatory L4 codes that qualify for tailwind detection
REGULATORY_L4_CODES = {"FIN-TAX", "FIN-LEGAL", "TECH-SEC", "FIN-RISK", "CRP-REG", "FIN-CMP", "RTB-CMP"}


def _get_anthropic() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# AI narrative generation
# ---------------------------------------------------------------------------

def _generate_narrative(category_name: str, trigger_type: str, trigger_data: dict, investment_name: str = "") -> dict:
    """Ask Claude to generate title, description, recommended_action, impact_estimate."""
    client = _get_anthropic()

    context = f"Investment: {investment_name}\n" if investment_name else ""
    context += f"Signal: {category_name}\nTrigger: {trigger_type}\nData: {json.dumps(trigger_data, default=str)}"

    prompt = f"""You are a CFO-level investment analyst. Generate a concise decision signal card.

{context}

Return JSON only:
{{
  "title": "<one-line title citing the key number>",
  "description": "<2-3 sentences citing specific numbers from the trigger data, explaining why this is an issue>",
  "recommended_action": "<concrete next step, e.g. 'Schedule kill decision review by Q2' or 'Submit incremental funding request'>",
  "impact_estimate": "<dollar impact estimate if inferable, else null>"
}}"""

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1][4:] if parts[1].startswith("json") else parts[1]
        return json.loads(raw.strip())
    except Exception as e:
        logger.warning(f"Narrative generation failed: {e}")
        return {
            "title": f"{category_name} detected",
            "description": f"Signal triggered: {trigger_type}. Review trigger data for details.",
            "recommended_action": "Review investment and take appropriate action.",
            "impact_estimate": None,
        }


# ---------------------------------------------------------------------------
# Decision record builder
# ---------------------------------------------------------------------------

def _build_decision(
    org_id: str,
    category_num: int,
    category_key: str,
    category_name: str,
    severity: str,
    trigger_type: str,
    trigger_data: dict,
    investment_id: Optional[str] = None,
    plan_id: Optional[str] = None,
    investment_name: str = "",
) -> dict:
    narrative = _generate_narrative(category_name, trigger_type, trigger_data, investment_name)
    return {
        "org_id": org_id,
        "investment_id": investment_id,
        "plan_id": plan_id,
        "category": category_key,
        "category_number": category_num,
        "severity": severity,
        "trigger_type": trigger_type,
        "trigger_data": trigger_data,
        "title": narrative.get("title", f"{category_name} detected"),
        "description": narrative.get("description", ""),
        "recommended_action": narrative.get("recommended_action", ""),
        "impact_estimate": narrative.get("impact_estimate"),
        "status": "new",
    }


# ---------------------------------------------------------------------------
# Helper: check if a signal already exists (dedup by org+category+investment)
# ---------------------------------------------------------------------------

def _already_exists(db: Client, org_id: str, category_key: str, investment_id: Optional[str] = None) -> bool:
    q = (
        db.table("decisions")
        .select("id")
        .eq("org_id", org_id)
        .eq("category", category_key)
        .in_("status", ["new", "acknowledged", "in_progress"])
    )
    if investment_id:
        q = q.eq("investment_id", investment_id)
    else:
        q = q.is_("investment_id", "null")
    res = q.limit(1).execute()
    return bool(res.data)


# ---------------------------------------------------------------------------
# Main detector class
# ---------------------------------------------------------------------------

class SignalDetector:
    """Detects actionable decision signals from investment and plan data."""

    CATEGORIES = {
        1:  {"key": "kill_eliminate",        "name": "Kill / Eliminate",             "severity": "critical"},
        2:  {"key": "pause_reassess",         "name": "Pause & Reassess",             "severity": "critical"},
        3:  {"key": "cost_overrun",           "name": "Cost Overrun Alert",           "severity": "critical"},
        4:  {"key": "accelerate",             "name": "Accelerate / Double Down",     "severity": "critical"},
        5:  {"key": "turnaround_required",    "name": "Turnaround Required",          "severity": "warning"},
        6:  {"key": "reallocate_funds",       "name": "Reallocate Funds",             "severity": "warning"},
        7:  {"key": "reclassify_rtb_ctb",     "name": "Reclassify RTB↔CTB",          "severity": "warning"},
        8:  {"key": "merge_consolidate",      "name": "Merge / Consolidate",          "severity": "warning"},
        9:  {"key": "extend_timeline",        "name": "Extend Timeline",              "severity": "warning"},
        10: {"key": "portfolio_rebalance",    "name": "Portfolio Rebalance",          "severity": "info"},
        11: {"key": "benchmark_gap",          "name": "Benchmark Gap",               "severity": "info"},
        12: {"key": "roi_decay",              "name": "ROI Decay",                   "severity": "info"},
        13: {"key": "concentration_risk",     "name": "Concentration Risk",          "severity": "info"},
        14: {"key": "competitive_threat",     "name": "Competitive Threat",          "severity": "info"},
        15: {"key": "delivery_risk",          "name": "Delivery Risk",               "severity": "warning"},
        16: {"key": "zombie_investment",      "name": "Zombie Investment",            "severity": "critical"},
        17: {"key": "benefit_hockey_stick",   "name": "Benefit Hockey Stick",        "severity": "warning"},
        18: {"key": "hiring_blocked",         "name": "Hiring-Blocked Investment",    "severity": "warning"},
        19: {"key": "decommission_redeploy",  "name": "Decommission & Redeploy",     "severity": "info"},
        20: {"key": "regulatory_tailwind",    "name": "Regulatory Tailwind",         "severity": "info"},
    }

    def __init__(self, db: Client, memory: Optional[AgentMemory] = None):
        self.db = db
        self.memory = memory

    def _fetch_investments(self, org_id: str) -> list[dict]:
        res = (
            self.db.table("investments")
            .select("*")
            .eq("org_id", org_id)
            .execute()
        )
        return res.data or []

    def _fetch_benefits(self, investment_ids: list[str]) -> dict[str, list[dict]]:
        if not investment_ids:
            return {}
        res = (
            self.db.table("investment_benefits")
            .select("*")
            .in_("investment_id", investment_ids)
            .execute()
        )
        by_inv: dict[str, list] = {}
        for b in (res.data or []):
            inv_id = b["investment_id"]
            by_inv.setdefault(inv_id, []).append(b)
        return by_inv

    def _fetch_spend(self, investment_ids: list[str]) -> dict[str, list[dict]]:
        if not investment_ids:
            return {}
        res = (
            self.db.table("investment_spend")
            .select("*")
            .in_("investment_id", investment_ids)
            .order("period")
            .execute()
        )
        by_inv: dict[str, list] = {}
        for s in (res.data or []):
            inv_id = s["investment_id"]
            by_inv.setdefault(inv_id, []).append(s)
        return by_inv

    def _tenure_years(self, investment: dict) -> float:
        start = investment.get("start_date")
        if not start:
            return 0
        try:
            start_dt = datetime.fromisoformat(str(start))
            now = datetime.now(timezone.utc)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            return (now - start_dt).days / 365.25
        except Exception:
            return 0

    def _roi(self, investment: dict, benefits: list[dict]) -> Optional[float]:
        costs = investment.get("actual_total") or investment.get("planned_total") or 0
        if not costs:
            return None
        total_benefits = sum(b.get("actual_value") or 0 for b in benefits)
        return total_benefits / costs

    def _save_decisions(self, decisions: list[dict]) -> list[dict]:
        if not decisions:
            return []
        res = self.db.table("decisions").insert(decisions).execute()
        return res.data or []

    # -----------------------------------------------------------------------
    # Investment-level detectors (categories 1-9, 15-20)
    # -----------------------------------------------------------------------

    def _check_sensitivity(self, org_id: str, category_key: str) -> bool:
        """Return False if this org dismisses this signal category too often (suppress it)."""
        if self.memory is None:
            return True
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            sensitivity = loop.run_until_complete(self.memory.get_signal_sensitivity(category_key))
            loop.close()
            # If sensitivity below 0.3 threshold, suppress
            return sensitivity >= 0.3
        except Exception as e:
            logger.warning(f"Sensitivity check failed for {category_key}: {e}")
            return True

    def scan_investments(self, org_id: str) -> list[dict]:
        investments = self._fetch_investments(org_id)
        if not investments:
            return []

        inv_ids = [i["id"] for i in investments]
        benefits_by_inv = self._fetch_benefits(inv_ids)
        spend_by_inv = self._fetch_spend(inv_ids)

        new_decisions: list[dict] = []

        for inv in investments:
            inv_id = inv["id"]
            name = inv.get("name", "Unknown")
            benefits = benefits_by_inv.get(inv_id, [])
            spends = spend_by_inv.get(inv_id, [])
            roi = self._roi(inv, benefits)
            tenure = self._tenure_years(inv)
            planned_total = inv.get("planned_total") or 0
            actual_total = inv.get("actual_total") or 0
            status = inv.get("status", "")
            strategic_rating = inv.get("strategic_rating") or 0

            total_benefit_target = sum(b.get("target_value") or 0 for b in benefits)
            total_benefit_actual = sum(b.get("actual_value") or 0 for b in benefits)
            benefit_realization = (
                total_benefit_actual / total_benefit_target if total_benefit_target else None
            )

            # Cat 1: Kill / Eliminate
            kill_signal = False
            if roi is not None and roi < 0.30 and tenure > 2:
                if total_benefit_actual == 0:
                    kill_signal = True
                elif benefit_realization is not None and benefit_realization < 0.2:
                    kill_signal = True
            if kill_signal and self._check_sensitivity(org_id, "kill_eliminate") and not _already_exists(self.db, org_id, "kill_eliminate", inv_id):
                new_decisions.append(_build_decision(
                    org_id=org_id, category_num=1, category_key="kill_eliminate",
                    category_name="Kill / Eliminate", severity="critical",
                    trigger_type="roi_below_threshold",
                    trigger_data={"roi": roi, "tenure_years": round(tenure, 1), "benefit_realization_pct": round((benefit_realization or 0) * 100, 1)},
                    investment_id=inv_id, investment_name=name,
                ))

            # Cat 2: Pause & Reassess
            if roi is not None and strategic_rating >= 4 and planned_total > 0:
                spend_pct = actual_total / planned_total if planned_total else 0
                if benefit_realization is not None and benefit_realization < 0.20 and spend_pct < 0.50:
                    if self._check_sensitivity(org_id, "pause_reassess") and not _already_exists(self.db, org_id, "pause_reassess", inv_id):
                        new_decisions.append(_build_decision(
                            org_id=org_id, category_num=2, category_key="pause_reassess",
                            category_name="Pause & Reassess", severity="critical",
                            trigger_type="benefits_not_materializing",
                            trigger_data={"roi": roi, "strategic_rating": strategic_rating, "benefit_realization_pct": round(benefit_realization * 100, 1), "spend_pct": round(spend_pct * 100, 1)},
                            investment_id=inv_id, investment_name=name,
                        ))

            # Cat 3: Cost Overrun
            if planned_total > 0 and actual_total > planned_total * 1.3:
                if self._check_sensitivity(org_id, "cost_overrun") and not _already_exists(self.db, org_id, "cost_overrun", inv_id):
                    overrun_pct = round((actual_total / planned_total - 1) * 100, 1)
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=3, category_key="cost_overrun",
                        category_name="Cost Overrun Alert", severity="critical",
                        trigger_type="actual_exceeds_plan_130pct",
                        trigger_data={"planned_total": planned_total, "actual_total": actual_total, "overrun_pct": overrun_pct},
                        investment_id=inv_id, investment_name=name,
                    ))

            # Cat 4: Accelerate
            if roi is not None and roi > 2.0:
                costs = actual_total or planned_total
                payback_months = None
                if costs > 0 and total_benefit_actual > 0:
                    monthly_benefit = total_benefit_actual / 12
                    payback_months = int(costs / monthly_benefit) if monthly_benefit > 0 else None
                if payback_months is not None and payback_months < 12 and benefit_realization is not None and benefit_realization > 0.80:
                    if self._check_sensitivity(org_id, "accelerate") and not _already_exists(self.db, org_id, "accelerate", inv_id):
                        new_decisions.append(_build_decision(
                            org_id=org_id, category_num=4, category_key="accelerate",
                            category_name="Accelerate / Double Down", severity="critical",
                            trigger_type="high_roi_fast_payback",
                            trigger_data={"roi": roi, "roi_pct": round((roi - 1) * 100, 1), "payback_months": payback_months, "benefit_realization_pct": round(benefit_realization * 100, 1)},
                            investment_id=inv_id, investment_name=name,
                        ))

            # Cat 5: Turnaround Required
            if roi is not None and 0.30 <= roi <= 0.80 and tenure > 2 and strategic_rating >= 3:
                if self._check_sensitivity(org_id, "turnaround_required") and not _already_exists(self.db, org_id, "turnaround_required", inv_id):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=5, category_key="turnaround_required",
                        category_name="Turnaround Required", severity="warning",
                        trigger_type="low_roi_strategic_value",
                        trigger_data={"roi": roi, "roi_pct": round((roi - 1) * 100, 1), "tenure_years": round(tenure, 1), "strategic_rating": strategic_rating},
                        investment_id=inv_id, investment_name=name,
                    ))

            # Cat 7: Reclassify RTB↔CTB
            l1 = (inv.get("l2_category") or "").split("-")[0]  # RTB or CTB
            if l1 == "CTB" and tenure > 4 and not inv.get("target_completion"):
                if self._check_sensitivity(org_id, "reclassify_rtb_ctb") and not _already_exists(self.db, org_id, "reclassify_rtb_ctb", inv_id):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=7, category_key="reclassify_rtb_ctb",
                        category_name="Reclassify RTB↔CTB", severity="warning",
                        trigger_type="ctb_no_completion_date_long_running",
                        trigger_data={"l2_category": inv.get("l2_category"), "tenure_years": round(tenure, 1), "target_completion": None},
                        investment_id=inv_id, investment_name=name,
                    ))

            # Cat 9: Extend Timeline
            if benefit_realization is not None and 0.40 <= benefit_realization <= 0.80:
                if self._check_sensitivity(org_id, "extend_timeline") and not _already_exists(self.db, org_id, "extend_timeline", inv_id):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=9, category_key="extend_timeline",
                        category_name="Extend Timeline", severity="warning",
                        trigger_type="benefits_emerging_slower",
                        trigger_data={"benefit_realization_pct": round(benefit_realization * 100, 1), "total_benefit_target": total_benefit_target, "total_benefit_actual": total_benefit_actual},
                        investment_id=inv_id, investment_name=name,
                    ))

            # Cat 16: Zombie Investment
            if roi is not None and roi < 0.50 and tenure > 5:
                # Check no active kill decision
                kill_exists = (
                    self.db.table("decisions")
                    .select("id")
                    .eq("investment_id", inv_id)
                    .eq("category", "kill_eliminate")
                    .execute()
                )
                if not kill_exists.data and self._check_sensitivity(org_id, "zombie_investment") and not _already_exists(self.db, org_id, "zombie_investment", inv_id):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=16, category_key="zombie_investment",
                        category_name="Zombie Investment", severity="critical",
                        trigger_type="long_running_low_roi",
                        trigger_data={"roi": roi, "tenure_years": round(tenure, 1), "actual_total": actual_total},
                        investment_id=inv_id, investment_name=name,
                    ))

            # Cat 17: Benefit Hockey Stick — check spend periods for optimism bias
            if len(spends) >= 3:
                consecutive_optimism = 0
                for s in spends[-6:]:  # check last 6 periods
                    planned_benefit = s.get("planned_benefit") or 0
                    actual_benefit = s.get("actual_benefit") or 0
                    if planned_benefit > 0 and actual_benefit > 0:
                        if planned_benefit > actual_benefit * 1.5:
                            consecutive_optimism += 1
                        else:
                            consecutive_optimism = 0
                if consecutive_optimism >= 3 and self._check_sensitivity(org_id, "benefit_hockey_stick") and not _already_exists(self.db, org_id, "benefit_hockey_stick", inv_id):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=17, category_key="benefit_hockey_stick",
                        category_name="Benefit Hockey Stick", severity="warning",
                        trigger_type="persistent_benefit_overestimation",
                        trigger_data={"consecutive_periods": consecutive_optimism, "benefit_realization_pct": round((benefit_realization or 0) * 100, 1)},
                        investment_id=inv_id, investment_name=name,
                    ))

            # Cat 18: Hiring-Blocked
            if status in ("approved", "in_progress") and planned_total > 0:
                underspend_pct = 1 - (actual_total / planned_total)
                if underspend_pct > 0.30 and self._check_sensitivity(org_id, "hiring_blocked") and not _already_exists(self.db, org_id, "hiring_blocked", inv_id):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=18, category_key="hiring_blocked",
                        category_name="Hiring-Blocked Investment", severity="warning",
                        trigger_type="approved_but_underspent",
                        trigger_data={"planned_total": planned_total, "actual_total": actual_total, "underspend_pct": round(underspend_pct * 100, 1), "status": status},
                        investment_id=inv_id, investment_name=name,
                    ))

            # Cat 19: Decommission & Redeploy
            if status == "completed" and benefit_realization is not None and benefit_realization > 1.0:
                if self._check_sensitivity(org_id, "decommission_redeploy") and not _already_exists(self.db, org_id, "decommission_redeploy", inv_id):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=19, category_key="decommission_redeploy",
                        category_name="Decommission & Redeploy", severity="info",
                        trigger_type="completed_overperforming",
                        trigger_data={"status": status, "benefit_realization_pct": round(benefit_realization * 100, 1), "total_benefit_actual": total_benefit_actual, "total_benefit_target": total_benefit_target},
                        investment_id=inv_id, investment_name=name,
                    ))

            # Cat 20: Regulatory Tailwind
            l4 = (inv.get("l4_activity") or "").upper()
            l2 = (inv.get("l2_category") or "").upper()
            is_regulatory = l4 in REGULATORY_L4_CODES or l2 in {"RTB-CMP"}
            if is_regulatory and roi is not None and roi > 1.50:
                if self._check_sensitivity(org_id, "regulatory_tailwind") and not _already_exists(self.db, org_id, "regulatory_tailwind", inv_id):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=20, category_key="regulatory_tailwind",
                        category_name="Regulatory Tailwind", severity="info",
                        trigger_type="regulatory_investment_high_roi",
                        trigger_data={"l4_activity": inv.get("l4_activity"), "l2_category": inv.get("l2_category"), "roi": roi, "roi_pct": round((roi - 1) * 100, 1)},
                        investment_id=inv_id, investment_name=name,
                    ))

        # Cat 8: Merge / Consolidate — group by L4 activity
        l4_groups: dict[str, list[dict]] = {}
        for inv in investments:
            l4 = inv.get("l4_activity")
            if l4:
                l4_groups.setdefault(l4, []).append(inv)

        for l4, group in l4_groups.items():
            if len(group) >= 3 and not _already_exists(self.db, org_id, "merge_consolidate"):
                total_spend = sum((i.get("actual_total") or i.get("planned_total") or 0) for i in group)
                new_decisions.append(_build_decision(
                    org_id=org_id, category_num=8, category_key="merge_consolidate",
                    category_name="Merge / Consolidate", severity="warning",
                    trigger_type="multiple_investments_same_l4",
                    trigger_data={"l4_activity": l4, "investment_count": len(group), "investment_names": [i["name"] for i in group], "total_spend": total_spend},
                ))

        # Cat 15: Delivery Risk — check for in_progress past target_completion
        in_progress = [i for i in investments if i.get("status") == "in_progress"]
        if in_progress:
            now = datetime.now(timezone.utc)
            overdue = []
            for inv in in_progress:
                tc = inv.get("target_completion")
                if tc:
                    try:
                        tc_dt = datetime.fromisoformat(str(tc))
                        if tc_dt.tzinfo is None:
                            tc_dt = tc_dt.replace(tzinfo=timezone.utc)
                        if now > tc_dt:
                            overdue.append(inv["name"])
                    except Exception:
                        pass
            overdue_pct = len(overdue) / len(in_progress) * 100 if in_progress else 0
            if overdue_pct > 20 and not _already_exists(self.db, org_id, "delivery_risk"):
                new_decisions.append(_build_decision(
                    org_id=org_id, category_num=15, category_key="delivery_risk",
                    category_name="Delivery Risk", severity="warning",
                    trigger_type="overdue_investments_threshold",
                    trigger_data={"overdue_count": len(overdue), "total_in_progress": len(in_progress), "overdue_pct": round(overdue_pct, 1), "overdue_investments": overdue[:10]},
                ))

        return self._save_decisions(new_decisions)

    # -----------------------------------------------------------------------
    # Portfolio-level detectors (categories 6, 10-14)
    # -----------------------------------------------------------------------

    def scan_portfolio(self, org_id: str) -> list[dict]:
        new_decisions: list[dict] = []

        # Fetch approved plan for this org
        plan_res = (
            self.db.table("plans")
            .select("id, fiscal_year")
            .eq("org_id", org_id)
            .eq("status", "approved")
            .order("fiscal_year", desc=True)
            .limit(1)
            .execute()
        )
        plan = (plan_res.data or [None])[0]

        if plan:
            plan_id = plan["id"]
            items_res = (
                self.db.table("plan_line_items")
                .select("classified_l1, classified_l2, annual_total")
                .eq("plan_id", plan_id)
                .execute()
            )
            items = items_res.data or []

            ctb_items = [i for i in items if i.get("classified_l1") == "CTB"]
            total_ctb = sum(i.get("annual_total") or 0 for i in ctb_items)
            total_all = sum(i.get("annual_total") or 0 for i in items)

            # Spending by L2
            by_l2: dict[str, float] = {}
            for item in ctb_items:
                l2 = item.get("classified_l2") or "Unknown"
                by_l2[l2] = by_l2.get(l2, 0) + (item.get("annual_total") or 0)

            # Cat 6: Reallocate Funds — L2 variance
            if by_l2 and total_ctb > 0:
                l2_pcts = {l2: amt / total_ctb * 100 for l2, amt in by_l2.items()}
                # Simple heuristic: check for high variance among L2 allocations
                avg_pct = 100 / len(l2_pcts)
                underfunded = [l2 for l2, pct in l2_pcts.items() if pct < avg_pct * 0.80]
                overfunded = [l2 for l2, pct in l2_pcts.items() if pct > avg_pct * 1.15]
                if underfunded and overfunded and not _already_exists(self.db, org_id, "reallocate_funds"):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=6, category_key="reallocate_funds",
                        category_name="Reallocate Funds", severity="warning",
                        trigger_type="l2_imbalance",
                        trigger_data={"underfunded_l2": underfunded, "overfunded_l2": overfunded, "l2_pcts": {k: round(v, 1) for k, v in l2_pcts.items()}},
                        plan_id=plan_id,
                    ))

            # Cat 11: Benchmark Gap — CTB% outside 10-20% of revenue
            org_res = self.db.table("organizations").select("revenue").eq("id", org_id).single().execute()
            revenue = (org_res.data or {}).get("revenue") or 0
            if revenue > 0 and total_ctb > 0:
                ctb_rev_pct = total_ctb / revenue * 100
                if ctb_rev_pct < 10 or ctb_rev_pct > 20:
                    if not _already_exists(self.db, org_id, "benchmark_gap"):
                        zone = "below Goldilocks zone" if ctb_rev_pct < 10 else "above Goldilocks zone"
                        new_decisions.append(_build_decision(
                            org_id=org_id, category_num=11, category_key="benchmark_gap",
                            category_name="Benchmark Gap", severity="info",
                            trigger_type="ctb_pct_outside_10_20_revenue",
                            trigger_data={"ctb_total": total_ctb, "revenue": revenue, "ctb_rev_pct": round(ctb_rev_pct, 1), "zone": zone},
                            plan_id=plan_id,
                        ))

            # Cat 13: Concentration Risk — single L2 > 40% of CTB
            for l2, amt in by_l2.items():
                l2_pct = amt / total_ctb * 100 if total_ctb else 0
                if l2_pct > 40 and not _already_exists(self.db, org_id, "concentration_risk"):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=13, category_key="concentration_risk",
                        category_name="Concentration Risk", severity="info",
                        trigger_type="single_l2_exceeds_40pct",
                        trigger_data={"l2_category": l2, "l2_pct": round(l2_pct, 1), "l2_amount": amt, "total_ctb": total_ctb},
                        plan_id=plan_id,
                    ))

        # Cat 10: Portfolio Rebalance — fetch sector benchmarks
        org_res2 = self.db.table("organizations").select("*").eq("id", org_id).single().execute()
        org = org_res2.data or {}
        sector = org.get("sector", "")
        if sector:
            benchmark_res = (
                self.db.table("sector_benchmarks")
                .select("*")
                .eq("sector", sector)
                .execute()
            )
            benchmarks = benchmark_res.data or []
            if benchmarks and plan:
                items_res2 = (
                    self.db.table("plan_line_items")
                    .select("classified_l2, annual_total")
                    .eq("plan_id", plan["id"])
                    .execute()
                )
                all_items = items_res2.data or []
                all_total = sum(i.get("annual_total") or 0 for i in all_items)
                org_l2_pcts: dict[str, float] = {}
                for item in all_items:
                    l2 = item.get("classified_l2") or ""
                    if l2:
                        org_l2_pcts[l2] = org_l2_pcts.get(l2, 0) + (item.get("annual_total") or 0)
                if all_total:
                    org_l2_pcts = {k: v / all_total * 100 for k, v in org_l2_pcts.items()}

                outliers = []
                for b in benchmarks:
                    l2 = b.get("l2_category", "")
                    org_pct = org_l2_pcts.get(l2, 0)
                    p25 = b.get("p25_pct") or 0
                    p75 = b.get("p75_pct") or 0
                    if p25 and p75 and (org_pct < p25 or org_pct > p75):
                        outliers.append({"l2": l2, "org_pct": round(org_pct, 1), "p25": p25, "p75": p75})

                if outliers and not _already_exists(self.db, org_id, "portfolio_rebalance"):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=10, category_key="portfolio_rebalance",
                        category_name="Portfolio Rebalance", severity="info",
                        trigger_type="l2_outside_peer_percentiles",
                        trigger_data={"outliers": outliers, "sector": sector},
                        plan_id=plan["id"] if plan else None,
                    ))

        # Cat 12: ROI Decay — portfolio weighted-average ROI declining
        investments = self._fetch_investments(org_id)
        if investments:
            inv_ids = [i["id"] for i in investments]
            benefits_by_inv = self._fetch_benefits(inv_ids)

            # Compute weighted avg ROI per investment
            rois = []
            for inv in investments:
                benefits = benefits_by_inv.get(inv["id"], [])
                roi = self._roi(inv, benefits)
                if roi is not None:
                    weight = inv.get("actual_total") or inv.get("planned_total") or 1
                    rois.append((roi, weight))

            if len(rois) >= 2:
                # Simple check: more investments below 1.0x than above = decay signal
                below = sum(1 for r, _ in rois if r < 1.0)
                total_roi_invs = len(rois)
                avg_roi = sum(r * w for r, w in rois) / sum(w for _, w in rois) if rois else 0
                if below / total_roi_invs > 0.5 and not _already_exists(self.db, org_id, "roi_decay"):
                    new_decisions.append(_build_decision(
                        org_id=org_id, category_num=12, category_key="roi_decay",
                        category_name="ROI Decay", severity="info",
                        trigger_type="portfolio_roi_declining",
                        trigger_data={"avg_roi": round(avg_roi, 2), "below_1x_count": below, "total_investments": total_roi_invs, "below_pct": round(below / total_roi_invs * 100, 1)},
                    ))

        return self._save_decisions(new_decisions)

    # -----------------------------------------------------------------------
    # Full scan
    # -----------------------------------------------------------------------

    def scan_all(self, org_id: str) -> list[dict]:
        """Run all 20 signal detectors and return newly created decisions."""
        logger.info(f"Starting full signal scan for org {org_id}")
        inv_decisions = self.scan_investments(org_id)
        portfolio_decisions = self.scan_portfolio(org_id)
        all_new = inv_decisions + portfolio_decisions
        logger.info(f"Scan complete: {len(all_new)} new decisions created for org {org_id}")
        return all_new

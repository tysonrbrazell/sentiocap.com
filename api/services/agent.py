"""
SentioCap Agent Brain — autonomous AI agent for capital allocation intelligence.

Provides:
- morning_briefing()     → daily CFO briefing
- generate_board_deck()  → quarterly investment review document
- analyze_question()     → conversational Q&A on capital data
- scenario_simulate()    → what-if scenario modeling
- auto_reforecast()      → full-year reforecast after month close
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import anthropic
from supabase import Client

from config import settings
from services.signals import SignalDetector

logger = logging.getLogger(__name__)

MODEL = "claude-3-5-sonnet-20241022"
HAIKU = "claude-3-5-haiku-20241022"


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


# ---------------------------------------------------------------------------
# Data gathering helpers
# ---------------------------------------------------------------------------

def _fetch_org(db: Client, org_id: str) -> dict:
    res = db.table("organizations").select("*").eq("id", org_id).single().execute()
    return res.data or {}


def _fetch_approved_plan(db: Client, org_id: str) -> Optional[dict]:
    res = (
        db.table("plans")
        .select("*")
        .eq("org_id", org_id)
        .eq("status", "approved")
        .order("fiscal_year", desc=True)
        .limit(1)
        .execute()
    )
    plans = res.data or []
    return plans[0] if plans else None


def _fetch_plan_items(db: Client, plan_id: str) -> list[dict]:
    res = (
        db.table("plan_line_items")
        .select("*")
        .eq("plan_id", plan_id)
        .execute()
    )
    return res.data or []


def _fetch_investments(db: Client, org_id: str) -> list[dict]:
    res = db.table("investments").select("*").eq("org_id", org_id).execute()
    return res.data or []


def _fetch_actuals(db: Client, org_id: str, from_period: Optional[str] = None) -> list[dict]:
    q = db.table("actuals").select("*").eq("org_id", org_id)
    if from_period:
        q = q.gte("period", from_period)
    res = q.order("period", desc=True).limit(200).execute()
    return res.data or []


def _fetch_decisions(db: Client, org_id: str, status: Optional[list[str]] = None) -> list[dict]:
    q = db.table("decisions").select("*").eq("org_id", org_id)
    if status:
        q = q.in_("status", status)
    res = q.order("created_at", desc=True).limit(50).execute()
    return res.data or []


def _fetch_upcoming_deadlines(db: Client, org_id: str, days: int = 7) -> list[dict]:
    cutoff = (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()
    today = datetime.now(timezone.utc).date().isoformat()
    res = (
        db.table("investments")
        .select("id, name, target_completion, status, planned_total, actual_total")
        .eq("org_id", org_id)
        .in_("status", ["approved", "in_progress"])
        .gte("target_completion", today)
        .lte("target_completion", cutoff)
        .execute()
    )
    return res.data or []


def _fetch_benchmarks(db: Client, sector: str) -> list[dict]:
    if not sector:
        return []
    res = (
        db.table("sector_benchmarks")
        .select("*")
        .eq("sector", sector)
        .execute()
    )
    return res.data or []


# ---------------------------------------------------------------------------
# Portfolio summary helper
# ---------------------------------------------------------------------------

def _build_portfolio_summary(items: list[dict], investments: list[dict]) -> dict:
    total = sum(i.get("annual_total") or 0 for i in items)
    rtb = sum(i.get("annual_total") or 0 for i in items if i.get("classified_l1") == "RTB")
    ctb = total - rtb

    by_l2: dict[str, float] = {}
    for item in items:
        l2 = item.get("classified_l2") or "Unknown"
        by_l2[l2] = by_l2.get(l2, 0) + (item.get("annual_total") or 0)

    active_invs = [i for i in investments if i.get("status") in ("approved", "in_progress")]
    total_planned = sum(i.get("planned_total") or 0 for i in active_invs)
    total_actual = sum(i.get("actual_total") or 0 for i in active_invs)

    return {
        "total_budget": total,
        "rtb_total": rtb,
        "ctb_total": ctb,
        "rtb_pct": round(rtb / total * 100, 1) if total else 0,
        "ctb_pct": round(ctb / total * 100, 1) if total else 0,
        "by_l2": {k: {"amount": v, "pct": round(v / total * 100, 1) if total else 0} for k, v in by_l2.items()},
        "active_investment_count": len(active_invs),
        "total_investment_planned": total_planned,
        "total_investment_actual": total_actual,
        "deployment_rate_pct": round(total_actual / total_planned * 100, 1) if total_planned else None,
    }


# ---------------------------------------------------------------------------
# Claude helpers
# ---------------------------------------------------------------------------

def _chat(system: str, user_content: str, model: str = MODEL, max_tokens: int = 2048) -> str:
    client = _get_client()
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    return response.content[0].text.strip()


def _chat_json(system: str, user_content: str, model: str = MODEL, max_tokens: int = 2048) -> dict | list:
    raw = _chat(system, user_content, model=model, max_tokens=max_tokens)
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1][4:].strip() if parts[1].startswith("json") else parts[1].strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"raw": raw}


# ---------------------------------------------------------------------------
# SentiocapAgent
# ---------------------------------------------------------------------------

class SentiocapAgent:
    """Autonomous AI agent that monitors, analyzes, and acts on capital allocation data."""

    def __init__(self, org_id: str, db: Client):
        self.org_id = org_id
        self.db = db

    # -----------------------------------------------------------------------
    # 1. Morning Briefing
    # -----------------------------------------------------------------------

    async def morning_briefing(self) -> dict:
        """Generate a daily briefing for the CFO."""
        org = _fetch_org(self.db, self.org_id)
        org_name = org.get("name", "your organization")
        plan = _fetch_approved_plan(self.db, self.org_id)
        items = _fetch_plan_items(self.db, plan["id"]) if plan else []
        investments = _fetch_investments(self.db, self.org_id)
        portfolio = _build_portfolio_summary(items, investments)

        # Recent actuals — last 2 months
        two_months_ago = (datetime.now(timezone.utc) - timedelta(days=60)).strftime("%Y-%m")
        actuals = _fetch_actuals(self.db, self.org_id, from_period=two_months_ago)

        # New signals (status=new)
        signals = _fetch_decisions(self.db, self.org_id, status=["new"])

        # Upcoming deadlines
        upcoming = _fetch_upcoming_deadlines(self.db, self.org_id, days=7)

        # Investments with budget threshold issues (>90% or >120% of planned)
        threshold_alerts = []
        for inv in investments:
            planned = inv.get("planned_total") or 0
            actual = inv.get("actual_total") or 0
            if planned > 0:
                pct = actual / planned
                if pct > 1.2:
                    threshold_alerts.append({"name": inv["name"], "pct": round(pct * 100, 1), "issue": "overrun"})
                elif pct > 0.9:
                    threshold_alerts.append({"name": inv["name"], "pct": round(pct * 100, 1), "issue": "approaching_limit"})

        context_data = {
            "org_name": org_name,
            "portfolio_summary": portfolio,
            "new_signals_count": len(signals),
            "signals_summary": [
                {"title": s.get("title"), "severity": s.get("severity"), "category": s.get("category")}
                for s in signals[:10]
            ],
            "upcoming_deadlines": upcoming,
            "budget_threshold_alerts": threshold_alerts[:10],
            "recent_actuals_periods": list(set(a.get("period") for a in actuals))[:6],
        }

        system = (
            f"You are the SentioCap AI agent for {org_name}. Generate a concise morning briefing "
            f"for the CFO. Be direct — lead with what matters, skip what's unchanged. "
            f"Write like a sharp chief of staff, not a dashboard. "
            f"Return a JSON object with these exact keys: "
            f"headline (one-line summary), narrative (3-5 paragraph markdown text), "
            f"recommended_actions (array of strings, max 5, prioritized)."
        )

        result = _chat_json(
            system=system,
            user_content=f"Capital allocation data as of {datetime.now().strftime('%B %d, %Y')}:\n\n{json.dumps(context_data, default=str)}",
            max_tokens=1500,
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "org_name": org_name,
            "headline": result.get("headline", f"{len(signals)} signals require attention"),
            "metrics_changed": [
                {"label": "Active Signals", "value": len(signals), "type": "warning" if signals else "ok"},
                {"label": "Deployment Rate", "value": f"{portfolio.get('deployment_rate_pct') or 0}%", "type": "info"},
                {"label": "CTB Split", "value": f"{portfolio.get('ctb_pct', 0)}%", "type": "info"},
                {"label": "Budget Alerts", "value": len(threshold_alerts), "type": "warning" if threshold_alerts else "ok"},
            ],
            "signals_fired": signals[:5],
            "investments_update": threshold_alerts[:5],
            "upcoming": upcoming,
            "recommended_actions": result.get("recommended_actions", []),
            "narrative": result.get("narrative", ""),
        }

    # -----------------------------------------------------------------------
    # 2. Board Deck Generator
    # -----------------------------------------------------------------------

    async def generate_board_deck(self, period: str, format: str = "markdown") -> dict:
        """Auto-generate a quarterly investment review document."""
        org = _fetch_org(self.db, self.org_id)
        org_name = org.get("name", "Organization")
        plan = _fetch_approved_plan(self.db, self.org_id)
        items = _fetch_plan_items(self.db, plan["id"]) if plan else []
        investments = _fetch_investments(self.db, self.org_id)
        portfolio = _build_portfolio_summary(items, investments)
        signals = _fetch_decisions(self.db, self.org_id)
        benchmarks = _fetch_benchmarks(self.db, org.get("sector", ""))

        context_data = {
            "org_name": org_name,
            "period": period,
            "fiscal_year": plan.get("fiscal_year") if plan else "N/A",
            "portfolio": portfolio,
            "total_signals": len(signals),
            "signals_by_severity": {
                "critical": len([s for s in signals if s.get("severity") == "critical"]),
                "warning": len([s for s in signals if s.get("severity") == "warning"]),
                "info": len([s for s in signals if s.get("severity") == "info"]),
            },
            "recent_signals": [
                {"title": s.get("title"), "category": s.get("category"), "status": s.get("status")}
                for s in signals[:15]
            ],
            "sector": org.get("sector", ""),
            "benchmark_count": len(benchmarks),
            "investments_by_status": {
                status: len([i for i in investments if i.get("status") == status])
                for status in ["proposed", "approved", "in_progress", "completed", "on_hold"]
            },
        }

        system = (
            f"You are a CFO-level analyst writing a quarterly board investment review for {org_name}. "
            f"Generate a comprehensive, professional document in markdown. Be specific with numbers. "
            f"Structure it with these sections using ## headers:\n"
            f"1. Executive Summary\n2. RTB/CTB Overview\n3. Investment Portfolio Performance\n"
            f"4. Variance Analysis\n5. Benchmark Position\n6. Decision Log\n"
            f"7. Recommendations\n8. Appendix\n\n"
            f"Use tables for financial data where appropriate. Be direct and analytical."
        )

        content = _chat(
            system=system,
            user_content=f"Generate the {period} quarterly investment review.\n\nData:\n{json.dumps(context_data, default=str)}",
            max_tokens=4000,
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "org_name": org_name,
            "period": period,
            "format": format,
            "content": content,
            "sections": [
                "Executive Summary", "RTB/CTB Overview", "Investment Portfolio Performance",
                "Variance Analysis", "Benchmark Position", "Decision Log",
                "Recommendations", "Appendix"
            ],
        }

    # -----------------------------------------------------------------------
    # 3. Conversational Q&A
    # -----------------------------------------------------------------------

    async def analyze_question(self, question: str) -> dict:
        """Answer any question about the org's capital allocation."""
        org = _fetch_org(self.db, self.org_id)
        org_name = org.get("name", "your organization")
        plan = _fetch_approved_plan(self.db, self.org_id)
        items = _fetch_plan_items(self.db, plan["id"]) if plan else []
        investments = _fetch_investments(self.db, self.org_id)
        portfolio = _build_portfolio_summary(items, investments)
        signals = _fetch_decisions(self.db, self.org_id, status=["new", "acknowledged"])
        benchmarks = _fetch_benchmarks(self.db, org.get("sector", ""))

        # Search for investments matching keywords in the question
        q_lower = question.lower()
        relevant_investments = [
            inv for inv in investments
            if any(word in (inv.get("name") or "").lower() for word in q_lower.split()
                   if len(word) > 3)
        ][:5]

        context_data = {
            "org_name": org_name,
            "portfolio": portfolio,
            "fiscal_year": plan.get("fiscal_year") if plan else None,
            "active_signals": [
                {"title": s.get("title"), "category": s.get("category"), "severity": s.get("severity"), "description": s.get("description")}
                for s in signals[:20]
            ],
            "sector": org.get("sector", ""),
            "benchmark_count": len(benchmarks),
            "relevant_investments": relevant_investments,
            "all_investment_names": [i.get("name") for i in investments],
        }

        system = (
            f"You are the SentioCap AI agent for {org_name}, acting as an expert CFO advisor. "
            f"Answer questions about capital allocation clearly and concisely. "
            f"Cite specific numbers from the data. Be direct — no fluff. "
            f"Return JSON with: answer (markdown string), confidence ('high'|'medium'|'low'), "
            f"supporting_data (array of key data points as strings), "
            f"follow_up_questions (array of 3 related questions the CFO might want to ask next)."
        )

        result = _chat_json(
            system=system,
            user_content=f"Question: {question}\n\nOrganization data:\n{json.dumps(context_data, default=str)}",
            max_tokens=1500,
        )

        return {
            "question": question,
            "answer": result.get("answer", "I couldn't generate an answer. Please check the data."),
            "confidence": result.get("confidence", "medium"),
            "supporting_data": result.get("supporting_data", []),
            "follow_up_questions": result.get("follow_up_questions", []),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    # -----------------------------------------------------------------------
    # 4. Scenario Simulator
    # -----------------------------------------------------------------------

    async def scenario_simulate(self, changes: list[dict]) -> dict:
        """Model what-if scenarios for capital allocation changes."""
        org = _fetch_org(self.db, self.org_id)
        org_name = org.get("name", "Organization")
        plan = _fetch_approved_plan(self.db, self.org_id)
        items = _fetch_plan_items(self.db, plan["id"]) if plan else []
        investments = _fetch_investments(self.db, self.org_id)
        portfolio = _build_portfolio_summary(items, investments)
        benchmarks = _fetch_benchmarks(self.db, org.get("sector", ""))

        # Resolve investment names for IDs in the changes
        inv_map = {i["id"]: i for i in investments}
        enriched_changes = []
        for change in changes:
            enriched = dict(change)
            if "investment_id" in change:
                inv = inv_map.get(change["investment_id"], {})
                enriched["investment_name"] = inv.get("name", change["investment_id"])
                enriched["planned_total"] = inv.get("planned_total")
                enriched["actual_total"] = inv.get("actual_total")
                enriched["l2_category"] = inv.get("l2_category")
            enriched_changes.append(enriched)

        context_data = {
            "org_name": org_name,
            "current_portfolio": portfolio,
            "proposed_changes": enriched_changes,
            "sector": org.get("sector", ""),
            "benchmarks_available": len(benchmarks) > 0,
        }

        system = (
            f"You are a CFO-level analyst modeling what-if scenarios for {org_name}. "
            f"Analyze the proposed capital allocation changes and return a detailed impact analysis. "
            f"Return JSON with: projected_ctb_split (object with new_ctb_pct, new_rtb_pct), "
            f"projected_roi_impact (string describing ROI change), "
            f"benchmark_shift (string describing movement vs peers), "
            f"freed_resources (object with budget_freed, context), "
            f"risks (array of risk strings), "
            f"narrative (2-3 paragraph markdown analysis of scenario impact)."
        )

        result = _chat_json(
            system=system,
            user_content=f"Scenario changes:\n{json.dumps(context_data, default=str)}",
            max_tokens=2000,
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "changes_analyzed": len(changes),
            "current_state": {
                "ctb_pct": portfolio["ctb_pct"],
                "rtb_pct": portfolio["rtb_pct"],
                "total_budget": portfolio["total_budget"],
            },
            "projected_ctb_split": result.get("projected_ctb_split", {}),
            "projected_roi_impact": result.get("projected_roi_impact", ""),
            "benchmark_shift": result.get("benchmark_shift", ""),
            "freed_resources": result.get("freed_resources", {}),
            "risks": result.get("risks", []),
            "narrative": result.get("narrative", ""),
        }

    # -----------------------------------------------------------------------
    # 5. Auto-Reforecast
    # -----------------------------------------------------------------------

    async def auto_reforecast(self, through_period: str) -> dict:
        """Auto-generate a full-year reforecast after month close."""
        org = _fetch_org(self.db, self.org_id)
        org_name = org.get("name", "Organization")
        plan = _fetch_approved_plan(self.db, self.org_id)
        items = _fetch_plan_items(self.db, plan["id"]) if plan else []
        actuals = _fetch_actuals(self.db, self.org_id)
        investments = _fetch_investments(self.db, self.org_id)

        # Build YTD actuals by period and L1
        ytd_by_period: dict[str, dict] = {}
        for a in actuals:
            if a.get("period", "") <= through_period:
                p = a["period"]
                if p not in ytd_by_period:
                    ytd_by_period[p] = {"rtb": 0.0, "ctb": 0.0, "total": 0.0}
                l1 = a.get("classified_l1", "")
                amount = a.get("amount") or 0
                ytd_by_period[p]["total"] += amount
                if l1 == "RTB":
                    ytd_by_period[p]["rtb"] += amount
                elif l1 == "CTB":
                    ytd_by_period[p]["ctb"] += amount

        # Plan monthly budget
        total_plan = sum(i.get("annual_total") or 0 for i in items)
        monthly_plan = total_plan / 12 if total_plan else 0

        # Trend: last 3 months average vs plan
        recent_periods = sorted(ytd_by_period.keys())[-3:]
        recent_avg = (
            sum(ytd_by_period[p]["total"] for p in recent_periods) / len(recent_periods)
            if recent_periods else monthly_plan
        )
        trend_multiplier = recent_avg / monthly_plan if monthly_plan else 1.0

        context_data = {
            "org_name": org_name,
            "through_period": through_period,
            "fiscal_year": plan.get("fiscal_year") if plan else "N/A",
            "annual_plan_total": total_plan,
            "monthly_plan_budget": round(monthly_plan, 2),
            "ytd_actuals_by_period": {p: {k: round(v, 2) for k, v in vals.items()} for p, vals in sorted(ytd_by_period.items())},
            "ytd_total": round(sum(v["total"] for v in ytd_by_period.values()), 2),
            "recent_monthly_avg": round(recent_avg, 2),
            "trend_multiplier": round(trend_multiplier, 3),
            "active_investments": len([i for i in investments if i.get("status") in ("approved", "in_progress")]),
        }

        system = (
            f"You are a CFO-level analyst generating a full-year reforecast for {org_name}. "
            f"Based on YTD actuals and trend analysis, project the remaining months and full-year total. "
            f"Return JSON with: "
            f"full_year_forecast (number), "
            f"variance_vs_plan (object with amount, pct, direction), "
            f"monthly_forecast (array of objects with period, projected_amount, basis), "
            f"variance_explanation (markdown string explaining key variances), "
            f"risk_flags (array of strings), "
            f"confidence ('high'|'medium'|'low')."
        )

        result = _chat_json(
            system=system,
            user_content=f"Reforecast data:\n{json.dumps(context_data, default=str)}",
            max_tokens=2000,
        )

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "through_period": through_period,
            "annual_plan": total_plan,
            "full_year_forecast": result.get("full_year_forecast"),
            "variance_vs_plan": result.get("variance_vs_plan", {}),
            "monthly_forecast": result.get("monthly_forecast", []),
            "variance_explanation": result.get("variance_explanation", ""),
            "risk_flags": result.get("risk_flags", []),
            "confidence": result.get("confidence", "medium"),
        }

    # -----------------------------------------------------------------------
    # Status
    # -----------------------------------------------------------------------

    def get_status(self) -> dict:
        """Return agent monitoring status."""
        org = _fetch_org(self.db, self.org_id)
        plan = _fetch_approved_plan(self.db, self.org_id)
        investments = _fetch_investments(self.db, self.org_id)
        new_signals = _fetch_decisions(self.db, self.org_id, status=["new"])

        return {
            "org_id": self.org_id,
            "org_name": org.get("name", ""),
            "status": "active",
            "monitoring": {
                "active_plan": plan.get("name") if plan else None,
                "fiscal_year": plan.get("fiscal_year") if plan else None,
                "investments_tracked": len(investments),
                "pending_signals": len(new_signals),
                "signal_detectors": 20,
            },
            "capabilities": [
                "morning_briefing",
                "board_deck_generation",
                "conversational_qa",
                "scenario_simulation",
                "auto_reforecast",
            ],
            "last_checked": datetime.now(timezone.utc).isoformat(),
        }

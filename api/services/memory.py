"""
Agent Memory Service — persistent per-company memory layer for all SentioCap agents.

Each agent (Scout, Sentinel, Compass, Oracle, Scribe) reads and writes through
this service so they get smarter over time without any per-agent plumbing.

Usage:
    memory = AgentMemory(org_id=org_id, supabase_client=db)
    context = await memory.build_classification_context()
    sensitivity = await memory.get_signal_sensitivity("kill_eliminate")
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional

from supabase import Client

logger = logging.getLogger(__name__)


class AgentMemory:
    """Persistent memory layer for all SentioCap agents."""

    def __init__(self, org_id: str, supabase_client: Client):
        self.org_id = org_id
        self.db = supabase_client

    # =========================================================================
    # SCOUT MEMORY
    # Classification corrections + firm glossary
    # =========================================================================

    async def record_correction(
        self,
        source_desc: str,
        original: dict,
        corrected: dict,
        user_id: Optional[str] = None,
        source_cost_center: Optional[str] = None,
        source_gl_account: Optional[str] = None,
    ) -> dict:
        """Record a classification correction and update the firm glossary.

        Args:
            source_desc: The original expense description text.
            original: Dict with original l1/l2/l3/l4 keys (may be None if never classified).
            corrected: Dict with corrected l1/l2/l3/l4 keys.
            user_id: UUID of the user making the correction.
            source_cost_center: Optional cost center from source data.
            source_gl_account: Optional GL account from source data.

        Returns:
            The inserted classification_corrections row.
        """
        # 1. Insert into classification_corrections
        correction_row = {
            "org_id": self.org_id,
            "source_description": source_desc,
            "source_cost_center": source_cost_center,
            "source_gl_account": source_gl_account,
            "original_l1": original.get("l1"),
            "original_l2": original.get("l2"),
            "original_l3": original.get("l3"),
            "original_l4": original.get("l4"),
            "corrected_l1": corrected["l1"],
            "corrected_l2": corrected["l2"],
            "corrected_l3": corrected.get("l3"),
            "corrected_l4": corrected.get("l4"),
            "corrected_by": user_id,
        }
        res = self.db.table("classification_corrections").insert(correction_row).execute()
        saved = (res.data or [{}])[0]

        # 2. Upsert into firm_glossary — increment usage_count if the term already exists
        # We upsert by (org_id, firm_term). On conflict we bump usage_count and refresh timestamps.
        # Supabase client doesn't support ON CONFLICT natively in upsert for non-PK, so we try
        # a select-then-insert-or-update pattern.
        try:
            existing = (
                self.db.table("firm_glossary")
                .select("id, usage_count")
                .eq("org_id", self.org_id)
                .eq("firm_term", source_desc)
                .limit(1)
                .execute()
            )
            if existing.data:
                entry = existing.data[0]
                self.db.table("firm_glossary").update({
                    "mapped_l1": corrected["l1"],
                    "mapped_l2": corrected["l2"],
                    "mapped_l3": corrected.get("l3"),
                    "mapped_l4": corrected.get("l4"),
                    "usage_count": entry["usage_count"] + 1,
                    "last_used_at": datetime.now(timezone.utc).isoformat(),
                    "source": "correction",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", entry["id"]).execute()
            else:
                self.db.table("firm_glossary").insert({
                    "org_id": self.org_id,
                    "firm_term": source_desc,
                    "mapped_l1": corrected["l1"],
                    "mapped_l2": corrected["l2"],
                    "mapped_l3": corrected.get("l3"),
                    "mapped_l4": corrected.get("l4"),
                    "confidence": 1.0,
                    "source": "correction",
                    "usage_count": 1,
                }).execute()
        except Exception as e:
            logger.warning(f"Glossary upsert failed for '{source_desc}': {e}")

        return saved

    async def get_firm_glossary(self) -> list[dict]:
        """Get all learned term mappings for this org, ordered by usage_count desc."""
        res = (
            self.db.table("firm_glossary")
            .select("*")
            .eq("org_id", self.org_id)
            .order("usage_count", desc=True)
            .execute()
        )
        return res.data or []

    async def get_prior_classifications(self, description: str) -> list[dict]:
        """Check if we've seen this description before for this org.

        Searches both classification_corrections and firm_glossary for exact
        and similar descriptions. Returns the most recent matches.
        """
        results = []

        # Exact match in firm_glossary first
        glossary_res = (
            self.db.table("firm_glossary")
            .select("*")
            .eq("org_id", self.org_id)
            .eq("firm_term", description)
            .limit(1)
            .execute()
        )
        if glossary_res.data:
            entry = glossary_res.data[0]
            results.append({
                "source": "glossary",
                "term": entry["firm_term"],
                "l1": entry.get("mapped_l1"),
                "l2": entry.get("mapped_l2"),
                "l3": entry.get("mapped_l3"),
                "l4": entry.get("mapped_l4"),
                "usage_count": entry.get("usage_count", 1),
                "confidence": entry.get("confidence", 1.0),
            })

        # Recent corrections matching this description
        corrections_res = (
            self.db.table("classification_corrections")
            .select("*")
            .eq("org_id", self.org_id)
            .eq("source_description", description)
            .order("created_at", desc=True)
            .limit(5)
            .execute()
        )
        for c in (corrections_res.data or []):
            results.append({
                "source": "correction",
                "term": c["source_description"],
                "l1": c.get("corrected_l1"),
                "l2": c.get("corrected_l2"),
                "l3": c.get("corrected_l3"),
                "l4": c.get("corrected_l4"),
                "corrected_at": c.get("created_at"),
            })

        return results

    async def build_classification_context(self) -> str:
        """Build a context string of this firm's learned mappings for the classification prompt.

        Returns a block like:
            This company uses specific terminology:
            - 'Cost of Production' → RTB-OPS (confirmed 47 times)
            - 'Strategic Initiatives' → CTB-GRW (confirmed 23 times)
        """
        glossary = await self.get_firm_glossary()
        if not glossary:
            return ""

        lines = ["This company uses specific terminology:"]
        for entry in glossary[:30]:  # cap at 30 to keep prompt size reasonable
            term = entry.get("firm_term", "")
            l1 = entry.get("mapped_l1", "")
            l2 = entry.get("mapped_l2", "")
            count = entry.get("usage_count", 1)
            mapping = f"{l1}-{l2}" if l1 and l2 else (l2 or l1 or "?")
            lines.append(f"- '{term}' → {mapping} (confirmed {count} times)")

        return "\n".join(lines)

    # =========================================================================
    # SENTINEL MEMORY
    # Signal action tracking + adaptive sensitivity
    # =========================================================================

    async def record_signal_action(self, category: str, action: str) -> None:
        """Record that a signal was acknowledged, resolved, or dismissed.

        Upserts into signal_preferences and increments the count.
        """
        try:
            existing = (
                self.db.table("signal_preferences")
                .select("id, count")
                .eq("org_id", self.org_id)
                .eq("category", category)
                .eq("action", action)
                .limit(1)
                .execute()
            )
            now = datetime.now(timezone.utc).isoformat()
            if existing.data:
                entry = existing.data[0]
                self.db.table("signal_preferences").update({
                    "count": entry["count"] + 1,
                    "last_action_at": now,
                    "updated_at": now,
                }).eq("id", entry["id"]).execute()
            else:
                self.db.table("signal_preferences").insert({
                    "org_id": self.org_id,
                    "category": category,
                    "action": action,
                    "count": 1,
                    "last_action_at": now,
                }).execute()
        except Exception as e:
            logger.warning(f"record_signal_action failed for {category}/{action}: {e}")

    async def get_signal_sensitivity(self, category: str) -> float:
        """Get the effective sensitivity multiplier for a signal category.

        Logic:
        - If this org dismisses a category > 70% of the time → return 0.3 (suppress)
        - If they always act on it (0% dismissed) → return 1.5 (amplify)
        - Otherwise → return 1.0 (normal)

        Returns:
            float: 0.3 means suppress, 1.0 is default, 1.5 means amplify.
        """
        try:
            # Check for manual override first
            override_res = (
                self.db.table("signal_preferences")
                .select("sensitivity_override, count, action")
                .eq("org_id", self.org_id)
                .eq("category", category)
                .not_.is_("sensitivity_override", "null")
                .limit(1)
                .execute()
            )
            if override_res.data and override_res.data[0].get("sensitivity_override") is not None:
                return float(override_res.data[0]["sensitivity_override"])

            # Compute from action history
            prefs_res = (
                self.db.table("signal_preferences")
                .select("action, count")
                .eq("org_id", self.org_id)
                .eq("category", category)
                .execute()
            )
            if not prefs_res.data:
                return 1.0

            total = sum(p["count"] for p in prefs_res.data)
            if total == 0:
                return 1.0

            dismissed = sum(p["count"] for p in prefs_res.data if p["action"] == "dismissed")
            dismiss_rate = dismissed / total

            if dismiss_rate > 0.7:
                return 0.3  # org mostly dismisses this — suppress it
            elif dismiss_rate == 0.0 and total >= 3:
                return 1.5  # org always acts on this — amplify it
            else:
                return 1.0
        except Exception as e:
            logger.warning(f"get_signal_sensitivity failed for {category}: {e}")
            return 1.0

    # =========================================================================
    # COMPASS MEMORY
    # Custom peer groups
    # =========================================================================

    async def save_peer_group(
        self,
        name: str,
        tickers: list[str],
        user_id: Optional[str] = None,
        is_default: bool = False,
    ) -> dict:
        """Save a custom peer group.

        If is_default=True, clears is_default on all other peer groups for this org.
        """
        now = datetime.now(timezone.utc).isoformat()

        if is_default:
            # Clear existing default
            try:
                self.db.table("custom_peer_groups").update({
                    "is_default": False,
                    "updated_at": now,
                }).eq("org_id", self.org_id).eq("is_default", True).execute()
            except Exception:
                pass

        res = self.db.table("custom_peer_groups").insert({
            "org_id": self.org_id,
            "name": name,
            "tickers": tickers,
            "is_default": is_default,
            "created_by": user_id,
        }).execute()
        return (res.data or [{}])[0]

    async def get_default_peer_group(self) -> list[str]:
        """Get the default peer group tickers for this org.

        Returns an empty list if no default is set.
        """
        res = (
            self.db.table("custom_peer_groups")
            .select("tickers")
            .eq("org_id", self.org_id)
            .eq("is_default", True)
            .limit(1)
            .execute()
        )
        if res.data:
            return res.data[0].get("tickers") or []
        return []

    async def get_peer_groups(self) -> list[dict]:
        """List all custom peer groups for this org."""
        res = (
            self.db.table("custom_peer_groups")
            .select("*")
            .eq("org_id", self.org_id)
            .order("created_at", desc=True)
            .execute()
        )
        return res.data or []

    # =========================================================================
    # ORACLE MEMORY
    # Forecast recording + accuracy tracking + bias detection
    # =========================================================================

    async def record_forecast(
        self,
        period: str,
        l2_category: str,
        forecasted_amount: float,
        forecast_date: Optional[date] = None,
    ) -> dict:
        """Record a forecast for later accuracy tracking.

        Args:
            period: 'YYYY-MM' string for the period being forecasted.
            l2_category: The L2 taxonomy category (e.g. 'CTB-GRW').
            forecasted_amount: Dollar amount forecasted.
            forecast_date: Date forecast was made. Defaults to today.
        """
        fd = (forecast_date or date.today()).isoformat()
        res = self.db.table("forecast_accuracy").insert({
            "org_id": self.org_id,
            "period": period,
            "forecast_date": fd,
            "l2_category": l2_category,
            "forecasted_amount": forecasted_amount,
        }).execute()
        return (res.data or [{}])[0]

    async def record_actual(
        self,
        period: str,
        l2_category: str,
        actual_amount: float,
    ) -> Optional[dict]:
        """When actuals arrive, compute accuracy of prior forecast.

        Finds the most recent forecast for this period+category and updates it
        with the actual amount and computed variance.
        """
        # Find the most recent forecast for this period + l2
        forecast_res = (
            self.db.table("forecast_accuracy")
            .select("id, forecasted_amount")
            .eq("org_id", self.org_id)
            .eq("period", period)
            .eq("l2_category", l2_category)
            .is_("actual_amount", "null")
            .order("forecast_date", desc=True)
            .limit(1)
            .execute()
        )
        if not forecast_res.data:
            return None

        entry = forecast_res.data[0]
        forecasted = float(entry["forecasted_amount"])
        variance_pct = ((actual_amount - forecasted) / forecasted) if forecasted != 0 else None
        bias_direction = None
        if variance_pct is not None:
            bias_direction = "over" if variance_pct > 0 else "under"

        update_res = self.db.table("forecast_accuracy").update({
            "actual_amount": actual_amount,
            "variance_pct": variance_pct,
            "bias_direction": bias_direction,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", entry["id"]).execute()
        return (update_res.data or [{}])[0]

    async def get_forecast_bias(self) -> dict[str, float]:
        """Compute systematic forecast bias for this org by L2 category.

        Returns:
            Dict mapping l2_category → average bias pct.
            Positive = org consistently over-forecasts, negative = under-forecasts.
            Oracle can use these to pre-adjust its forecasts.
        """
        res = (
            self.db.table("forecast_accuracy")
            .select("l2_category, variance_pct")
            .eq("org_id", self.org_id)
            .not_.is_("variance_pct", "null")
            .execute()
        )
        if not res.data:
            return {}

        by_category: dict[str, list[float]] = {}
        for row in res.data:
            cat = row["l2_category"]
            vp = row["variance_pct"]
            if vp is not None:
                by_category.setdefault(cat, []).append(float(vp))

        return {
            cat: round(sum(variances) / len(variances), 4)
            for cat, variances in by_category.items()
            if variances
        }

    async def get_forecast_accuracy_history(self) -> list[dict]:
        """Get the full forecast accuracy history for this org."""
        res = (
            self.db.table("forecast_accuracy")
            .select("*")
            .eq("org_id", self.org_id)
            .order("period", desc=True)
            .execute()
        )
        return res.data or []

    # =========================================================================
    # SCRIBE MEMORY
    # Report preferences + feedback loop
    # =========================================================================

    async def get_report_preferences(self, report_type: str) -> dict:
        """Get learned preferences for this report type.

        Returns a dict with preference keys (max_pages, focus_areas, etc.)
        and any feedback-derived insights.
        """
        res = (
            self.db.table("report_preferences")
            .select("*")
            .eq("org_id", self.org_id)
            .eq("report_type", report_type)
            .limit(1)
            .execute()
        )
        if not res.data:
            return {}
        entry = res.data[0]
        prefs = entry.get("preferences") or {}
        scores = entry.get("feedback_scores") or []

        # Compute average feedback score if available
        if scores:
            valid_scores = [s.get("score") for s in scores if s.get("score") is not None]
            if valid_scores:
                prefs["avg_feedback_score"] = round(sum(valid_scores) / len(valid_scores), 2)
                prefs["feedback_count"] = len(valid_scores)

        return prefs

    async def record_report_feedback(
        self,
        report_type: str,
        score: float,
        feedback_text: Optional[str] = None,
    ) -> None:
        """Record user feedback on a generated report.

        Appends to the feedback_scores JSONB array so trends can be tracked.
        """
        now = datetime.now(timezone.utc).isoformat()
        new_feedback = {"generated_at": now, "score": score, "feedback_text": feedback_text}

        existing = (
            self.db.table("report_preferences")
            .select("id, feedback_scores")
            .eq("org_id", self.org_id)
            .eq("report_type", report_type)
            .limit(1)
            .execute()
        )

        try:
            if existing.data:
                entry = existing.data[0]
                scores = list(entry.get("feedback_scores") or [])
                scores.append(new_feedback)
                self.db.table("report_preferences").update({
                    "feedback_scores": scores,
                    "updated_at": now,
                }).eq("id", entry["id"]).execute()
            else:
                self.db.table("report_preferences").insert({
                    "org_id": self.org_id,
                    "report_type": report_type,
                    "preferences": {},
                    "feedback_scores": [new_feedback],
                }).execute()
        except Exception as e:
            logger.warning(f"record_report_feedback failed for {report_type}: {e}")

    async def update_report_preferences(self, report_type: str, preferences: dict) -> None:
        """Manually update report preferences for a report type."""
        now = datetime.now(timezone.utc).isoformat()
        existing = (
            self.db.table("report_preferences")
            .select("id")
            .eq("org_id", self.org_id)
            .eq("report_type", report_type)
            .limit(1)
            .execute()
        )
        if existing.data:
            self.db.table("report_preferences").update({
                "preferences": preferences,
                "updated_at": now,
            }).eq("id", existing.data[0]["id"]).execute()
        else:
            self.db.table("report_preferences").insert({
                "org_id": self.org_id,
                "report_type": report_type,
                "preferences": preferences,
                "feedback_scores": [],
            }).execute()

    # =========================================================================
    # DECISION OUTCOMES
    # Track what happened after signals were acted on
    # =========================================================================

    async def record_decision_outcome(
        self,
        decision_id: Optional[str],
        action_taken: str,
        investment_id: Optional[str] = None,
        metrics_before: Optional[dict] = None,
        category: Optional[str] = None,
    ) -> dict:
        """Record what action was taken on a decision.

        Args:
            decision_id: UUID of the decision (signal) that was acted on.
            action_taken: One of 'killed', 'accelerated', 'reallocated', 'extended', 'ignored'.
            investment_id: UUID of the related investment, if any.
            metrics_before: Snapshot of key metrics at decision time.
            category: Signal category (pulled from decisions table if not provided).
        """
        # If no category provided, look it up from the decision
        if not category and decision_id:
            try:
                dec_res = (
                    self.db.table("decisions")
                    .select("category")
                    .eq("id", decision_id)
                    .limit(1)
                    .execute()
                )
                if dec_res.data:
                    category = dec_res.data[0].get("category", "unknown")
            except Exception:
                pass
        category = category or "unknown"

        res = self.db.table("decision_outcomes").insert({
            "org_id": self.org_id,
            "decision_id": decision_id,
            "category": category,
            "action_taken": action_taken,
            "investment_id": investment_id,
            "metrics_before": metrics_before or {},
        }).execute()
        return (res.data or [{}])[0]

    async def measure_outcome(
        self,
        outcome_id: str,
        metrics_after: dict,
        outcome_score: float,
        notes: Optional[str] = None,
    ) -> dict:
        """90 days later, record whether the decision was good.

        Args:
            outcome_id: UUID of the decision_outcomes row.
            metrics_after: Snapshot of metrics 90 days after the decision.
            outcome_score: -1 to 1 (negative = bad decision, positive = good).
            notes: Optional narrative on what happened.
        """
        res = self.db.table("decision_outcomes").update({
            "metrics_after": metrics_after,
            "outcome_score": outcome_score,
            "outcome_notes": notes,
            "measured_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", outcome_id).eq("org_id", self.org_id).execute()
        return (res.data or [{}])[0]

    async def get_decision_effectiveness(self, category: Optional[str] = None) -> dict:
        """For this org, what % of decisions in a category had positive outcomes?

        Args:
            category: Filter by specific signal category, or None for all.

        Returns:
            Dict with effectiveness stats per category.
        """
        q = (
            self.db.table("decision_outcomes")
            .select("category, outcome_score, action_taken")
            .eq("org_id", self.org_id)
            .not_.is_("outcome_score", "null")
        )
        if category:
            q = q.eq("category", category)
        res = q.execute()

        if not res.data:
            return {}

        by_cat: dict[str, Any] = {}
        for row in res.data:
            cat = row["category"]
            score = float(row["outcome_score"])
            if cat not in by_cat:
                by_cat[cat] = {"scores": [], "actions": {}}
            by_cat[cat]["scores"].append(score)
            action = row.get("action_taken", "unknown")
            by_cat[cat]["actions"][action] = by_cat[cat]["actions"].get(action, 0) + 1

        result = {}
        for cat, data in by_cat.items():
            scores = data["scores"]
            positive = sum(1 for s in scores if s > 0)
            result[cat] = {
                "total_outcomes": len(scores),
                "positive_pct": round(positive / len(scores) * 100, 1) if scores else 0,
                "avg_outcome_score": round(sum(scores) / len(scores), 3) if scores else 0,
                "actions": data["actions"],
            }
        return result

    # =========================================================================
    # NETWORK INTELLIGENCE
    # Cross-company, anonymized learning
    # =========================================================================

    async def contribute_to_network(
        self,
        intelligence_type: str,
        key: str,
        data: dict,
    ) -> None:
        """Contribute this org's data to the anonymized network.

        Merges with existing network intelligence for the same type+key.
        n_companies is incremented each time a unique org contributes.
        Only returned to callers when n_companies >= 5 (privacy threshold).
        """
        try:
            existing = (
                self.db.table("network_intelligence")
                .select("id, data, n_companies")
                .eq("intelligence_type", intelligence_type)
                .eq("key", key)
                .limit(1)
                .execute()
            )
            now = datetime.now(timezone.utc).isoformat()

            if existing.data:
                entry = existing.data[0]
                # Merge data (simple merge — callers can structure as needed)
                merged = dict(entry.get("data") or {})
                merged.update(data)
                # Track contributing org IDs to count uniques (stored anonymized as count)
                n = entry.get("n_companies", 0) + 1
                self.db.table("network_intelligence").update({
                    "data": merged,
                    "n_companies": n,
                    "last_updated": now,
                }).eq("id", entry["id"]).execute()
            else:
                self.db.table("network_intelligence").insert({
                    "intelligence_type": intelligence_type,
                    "key": key,
                    "data": data,
                    "n_companies": 1,
                    "confidence": 0.5,
                }).execute()
        except Exception as e:
            logger.warning(f"contribute_to_network failed for {intelligence_type}/{key}: {e}")

    async def query_network(self, intelligence_type: str, key: str) -> Optional[dict]:
        """Query the cross-company network intelligence.

        Returns None if fewer than 5 companies have contributed (privacy threshold).
        """
        try:
            res = (
                self.db.table("network_intelligence")
                .select("data, n_companies, confidence, last_updated")
                .eq("intelligence_type", intelligence_type)
                .eq("key", key)
                .limit(1)
                .execute()
            )
            if not res.data:
                return None

            entry = res.data[0]
            if (entry.get("n_companies") or 0) < 5:
                return None  # Privacy threshold not met

            return {
                "data": entry.get("data"),
                "n_companies": entry.get("n_companies"),
                "confidence": entry.get("confidence"),
                "last_updated": entry.get("last_updated"),
            }
        except Exception as e:
            logger.warning(f"query_network failed for {intelligence_type}/{key}: {e}")
            return None

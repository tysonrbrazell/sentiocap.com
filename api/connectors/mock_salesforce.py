"""
Mock Salesforce Connector for SentioCap.

Generates realistic CRM data for a financial data & analytics company
(modelled after MSCI). Data covers Q4-2024 through Q2-2025.

Swapping mock → real connector = replace _fetch_raw_data() with
actual Salesforce REST API calls. All data shapes remain identical.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from supabase import Client

from .base import BaseConnector, SyncResult


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRODUCTS = [
    "Index Products",
    "Analytics Platform",
    "ESG Solutions",
    "Climate Solutions",
    "Private Assets",
    "Custom Indexes",
]

SEGMENTS = [
    "Asset Managers",
    "Asset Owners",
    "Banks",
    "Hedge Funds",
    "Wealth Managers",
]

STAGES = [
    "Prospecting",
    "Qualification",
    "Needs Analysis",
    "Value Proposition",
    "Decision Makers",
    "Perception Analysis",
    "Proposal/Price Quote",
    "Negotiation/Review",
    "Closed Won",
    "Closed Lost",
]

STAGE_WEIGHTS = [5, 8, 10, 12, 10, 8, 15, 12, 20, 10]  # % probability of each stage

# Realistic deal size ranges by product (min, max in $k)
DEAL_SIZE_RANGES = {
    "Index Products": (800_000, 5_000_000),
    "Analytics Platform": (250_000, 1_500_000),
    "ESG Solutions": (150_000, 800_000),
    "Climate Solutions": (200_000, 1_200_000),
    "Private Assets": (300_000, 2_000_000),
    "Custom Indexes": (500_000, 3_000_000),
}

# Win rates by product (historical)
WIN_RATES = {
    "Index Products": 0.38,
    "Analytics Platform": 0.32,
    "ESG Solutions": 0.28,
    "Climate Solutions": 0.25,
    "Private Assets": 0.30,
    "Custom Indexes": 0.35,
}

# Avg sales cycle by product (days)
CYCLE_DAYS = {
    "Index Products": 120,
    "Analytics Platform": 90,
    "ESG Solutions": 75,
    "Climate Solutions": 80,
    "Private Assets": 110,
    "Custom Indexes": 95,
}

# Quarters we generate
QUARTERS = {
    "Q4-2024": ("2024-10-01", "2024-12-31"),
    "Q1-2025": ("2025-01-01", "2025-03-31"),
    "Q2-2025": ("2025-04-01", "2025-06-30"),
}

QUARTER_MONTHS = {
    "Q4-2024": ["2024-10", "2024-11", "2024-12"],
    "Q1-2025": ["2025-01", "2025-02", "2025-03"],
    "Q2-2025": ["2025-04", "2025-05", "2025-06"],
}

# Segment revenue split per product
SEGMENT_WEIGHTS = {
    "Index Products": [0.35, 0.25, 0.20, 0.12, 0.08],       # AM-heavy
    "Analytics Platform": [0.30, 0.20, 0.25, 0.15, 0.10],
    "ESG Solutions": [0.40, 0.30, 0.15, 0.05, 0.10],
    "Climate Solutions": [0.35, 0.35, 0.15, 0.05, 0.10],
    "Private Assets": [0.25, 0.20, 0.10, 0.35, 0.10],        # HF-heavy
    "Custom Indexes": [0.30, 0.15, 0.20, 0.25, 0.10],
}


def _random_date(start: str, end: str, rng: random.Random) -> datetime:
    s = datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    e = datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    delta = int((e - s).total_seconds())
    return s + timedelta(seconds=rng.randint(0, delta))


def _month_str(dt: datetime) -> str:
    return dt.strftime("%Y-%m")


class MockSalesforceConnector(BaseConnector):
    """
    Mock Salesforce connector. Generates deterministic-ish synthetic
    opportunity and account data matching the real Salesforce schema.
    """

    connector_type = "salesforce"
    is_mock = True

    def __init__(self, seed: int = 42):
        self._seed = seed

    # ------------------------------------------------------------------
    # Core: generate mock data
    # ------------------------------------------------------------------

    async def _fetch_raw_data(self, org_id: str) -> dict:
        """
        Generate mock Salesforce data. Structure mirrors what the real
        Salesforce connector would return from the API.
        """
        rng = random.Random(self._seed)

        opportunities = self._generate_opportunities(rng)
        accounts = self._generate_accounts(rng, opportunities)
        revenue_by_period = self._aggregate_revenue(opportunities)
        pipeline_summary = self._build_pipeline_summary(opportunities)

        return {
            "source": "mock_salesforce",
            "org_id": org_id,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "opportunities": opportunities,
            "accounts": accounts,
            "revenue_by_period": revenue_by_period,
            "pipeline_summary": pipeline_summary,
        }

    def _generate_opportunities(self, rng: random.Random) -> list[dict]:
        """Generate ~200 opportunities across 3 quarters."""
        opps = []
        opp_count = 0

        for quarter, (q_start, q_end) in QUARTERS.items():
            months = QUARTER_MONTHS[quarter]
            # ~65-70 opps per quarter
            for _ in range(rng.randint(60, 72)):
                product = rng.choice(PRODUCTS)
                segment = rng.choices(SEGMENTS, weights=SEGMENT_WEIGHTS[product])[0]
                stage = rng.choices(STAGES, weights=STAGE_WEIGHTS)[0]
                lo, hi = DEAL_SIZE_RANGES[product]
                amount = round(rng.uniform(lo, hi), -3)  # round to nearest $1k

                created_date = _random_date(q_start, q_end, rng)
                cycle = CYCLE_DAYS[product]
                close_date = created_date + timedelta(days=rng.randint(
                    int(cycle * 0.5), int(cycle * 1.8)
                ))

                # Adjust close dates: Closed Won/Lost happens within the quarter
                if stage in ("Closed Won", "Closed Lost"):
                    close_date = _random_date(q_start, q_end, rng)

                opp_count += 1
                opp = {
                    "id": f"006{opp_count:015d}",
                    "name": f"{product} — {segment} Deal {opp_count}",
                    "account_id": f"001{rng.randint(1000, 9999)}",
                    "product": product,
                    "segment": segment,
                    "stage": stage,
                    "amount": amount,
                    "created_date": created_date.isoformat(),
                    "close_date": close_date.isoformat(),
                    "quarter": quarter,
                    "month": _month_str(created_date),
                    "type": rng.choices(
                        ["New Business", "Existing Business"],
                        weights=[30, 70]
                    )[0],
                    "win_probability": self._stage_probability(stage),
                    "cycle_days": (close_date - created_date).days,
                    "arr": round(amount * rng.uniform(0.85, 1.0)),  # ARR ≈ deal value
                    "churn_risk": stage == "Closed Lost",
                }
                opps.append(opp)

        # Add ~15 churn/cancellation opportunities
        for i in range(15):
            product = rng.choice(PRODUCTS)
            quarter = rng.choice(list(QUARTERS.keys()))
            q_start, q_end = QUARTERS[quarter]
            cancel_date = _random_date(q_start, q_end, rng)
            churn_amount = -round(rng.uniform(100_000, 800_000), -3)
            opp_count += 1
            opps.append({
                "id": f"006CHURN{i:010d}",
                "name": f"CHURN — {product} cancellation {i+1}",
                "account_id": f"001{rng.randint(1000, 9999)}",
                "product": product,
                "segment": rng.choice(SEGMENTS),
                "stage": "Closed Lost",
                "amount": churn_amount,
                "created_date": cancel_date.isoformat(),
                "close_date": cancel_date.isoformat(),
                "quarter": quarter,
                "month": _month_str(cancel_date),
                "type": "Churn",
                "win_probability": 0,
                "cycle_days": 0,
                "arr": churn_amount,
                "churn_risk": True,
            })

        return opps

    def _generate_accounts(self, rng: random.Random, opps: list[dict]) -> list[dict]:
        """Unique accounts with new logo / existing flags."""
        account_ids = {o["account_id"] for o in opps}
        accounts = []
        new_logo_count = 0
        for acc_id in account_ids:
            is_new = rng.random() < 0.12  # ~12% new logos
            if is_new:
                new_logo_count += 1
            segment = rng.choice(SEGMENTS)
            accounts.append({
                "id": acc_id,
                "name": f"{segment} Client {acc_id[-4:]}",
                "type": "New Business" if is_new else "Existing Business",
                "segment": segment,
                "is_new_logo": is_new,
                "arr": round(rng.uniform(200_000, 5_000_000), -3),
            })
        return accounts

    def _aggregate_revenue(self, opps: list[dict]) -> list[dict]:
        """Aggregate to monthly revenue rows by product + segment."""
        from collections import defaultdict
        # {(period, product, segment): {pipeline, closed_won, new_logos, churned, amounts}}
        agg: dict = defaultdict(lambda: {
            "pipeline_amount": 0.0,
            "closed_won_amount": 0.0,
            "new_logos": 0,
            "churned_amount": 0.0,
            "deal_sizes": [],
            "cycle_days_list": [],
            "wins": 0,
            "losses": 0,
        })

        for opp in opps:
            period = opp["month"]
            product = opp["product"]
            segment = opp["segment"]
            key = (period, product, segment)

            if opp["stage"] == "Closed Won":
                agg[key]["closed_won_amount"] += opp["amount"]
                agg[key]["wins"] += 1
                agg[key]["deal_sizes"].append(opp["amount"])
                agg[key]["cycle_days_list"].append(opp.get("cycle_days", 90))
                if opp.get("type") == "New Business":
                    agg[key]["new_logos"] += 1
            elif opp["stage"] == "Closed Lost":
                agg[key]["losses"] += 1
                if opp.get("type") == "Churn":
                    agg[key]["churned_amount"] += abs(opp["amount"])
            elif opp["stage"] not in ("Closed Won", "Closed Lost"):
                agg[key]["pipeline_amount"] += opp["amount"] * opp["win_probability"] / 100

        rows = []
        for (period, product, segment), data in agg.items():
            wins = data["wins"]
            losses = data["losses"]
            total = wins + losses
            win_rate = wins / total if total > 0 else WIN_RATES.get(product, 0.3)
            avg_deal = (
                sum(data["deal_sizes"]) / len(data["deal_sizes"])
                if data["deal_sizes"] else DEAL_SIZE_RANGES[product][0]
            )
            avg_cycle = (
                int(sum(data["cycle_days_list"]) / len(data["cycle_days_list"]))
                if data["cycle_days_list"] else CYCLE_DAYS.get(product, 90)
            )

            rows.append({
                "period": period,
                "source_product": product,
                "source_segment": segment,
                "pipeline_amount": round(data["pipeline_amount"], 2),
                "closed_won_amount": round(data["closed_won_amount"], 2),
                "new_logos": data["new_logos"],
                "churned_amount": round(data["churned_amount"], 2),
                "avg_deal_size": round(avg_deal, 2),
                "win_rate": round(win_rate, 4),
                "avg_cycle_days": avg_cycle,
            })

        return sorted(rows, key=lambda r: (r["period"], r["source_product"]))

    def _build_pipeline_summary(self, opps: list[dict]) -> dict:
        """High-level pipeline summary by quarter and product."""
        from collections import defaultdict
        summary: dict = defaultdict(lambda: defaultdict(lambda: {
            "pipeline": 0.0, "closed_won": 0.0, "new_logos": 0, "churn": 0.0
        }))

        for opp in opps:
            q = opp["quarter"]
            p = opp["product"]
            if opp["stage"] == "Closed Won":
                summary[q][p]["closed_won"] += opp["amount"]
                if opp.get("type") == "New Business":
                    summary[q][p]["new_logos"] += 1
            elif opp.get("type") == "Churn":
                summary[q][p]["churn"] += abs(opp["amount"])
            elif opp["stage"] not in ("Closed Lost",):
                summary[q][p]["pipeline"] += opp["amount"] * opp["win_probability"] / 100

        return {q: dict(products) for q, products in summary.items()}

    @staticmethod
    def _stage_probability(stage: str) -> int:
        """Salesforce standard stage → win probability %."""
        probs = {
            "Prospecting": 10,
            "Qualification": 20,
            "Needs Analysis": 25,
            "Value Proposition": 40,
            "Decision Makers": 50,
            "Perception Analysis": 60,
            "Proposal/Price Quote": 70,
            "Negotiation/Review": 85,
            "Closed Won": 100,
            "Closed Lost": 0,
        }
        return probs.get(stage, 50)

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def _store_data(self, org_id: str, raw: dict, db: Client) -> dict:
        """Upsert revenue rows into crm_revenue_data."""
        rows = raw.get("revenue_by_period", [])
        if not rows:
            return {"records_synced": 0, "records_mapped": 0}

        stored = 0
        for row in rows:
            record = {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "connector_type": self.connector_type,
                "period": row["period"],
                "source_product": row["source_product"],
                "source_segment": row["source_segment"],
                "pipeline_amount": row["pipeline_amount"],
                "closed_won_amount": row["closed_won_amount"],
                "new_logos": row["new_logos"],
                "churned_amount": row["churned_amount"],
                "avg_deal_size": row["avg_deal_size"],
                "win_rate": row["win_rate"],
                "avg_cycle_days": row["avg_cycle_days"],
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                db.table("crm_revenue_data").upsert(record, on_conflict="org_id,connector_type,period,source_product,source_segment").execute()
                stored += 1
            except Exception:
                # Table may not exist yet in test env — skip gracefully
                pass

        return {"records_synced": stored, "records_mapped": stored}

    def get_mock_data(self, org_id: str = "mock") -> dict:
        """Synchronous helper to get mock data without DB (for seeding/testing)."""
        import asyncio
        return asyncio.get_event_loop().run_until_complete(self._fetch_raw_data(org_id))

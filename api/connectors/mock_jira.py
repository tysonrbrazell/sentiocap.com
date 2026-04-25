"""
Mock JIRA Connector for SentioCap.

Generates realistic JIRA project/sprint/issue data for a financial data
& analytics company (modelled after MSCI). Covers Q4-2024 through Q2-2025.

Projects map to investment themes. Some are healthy (high velocity, few bugs),
others are unhealthy (declining velocity, bug-heavy, scope creep) to demonstrate
Sentinel signals 21-25.

Swapping mock → real = replace _fetch_raw_data() with Jira REST API calls.
"""
from __future__ import annotations

import random
import uuid
from datetime import datetime, date, timedelta, timezone
from typing import Any

from supabase import Client

from .base import BaseConnector, SyncResult


# ---------------------------------------------------------------------------
# Project definitions
# ---------------------------------------------------------------------------

PROJECTS = {
    "Custom-Indexes": {
        "key": "CIDX",
        "team_size": 10,
        "health": "healthy",
        "investment_hint": "Custom Indexes",
        "l2_category": "CTB-GRW",
    },
    "FI-Proprietary": {
        "key": "FIPR",
        "team_size": 8,
        "health": "healthy",
        "investment_hint": "Fixed Income Index",
        "l2_category": "CTB-GRW",
    },
    "Insights-Platform": {
        "key": "INSP",
        "team_size": 12,
        "health": "healthy",
        "investment_hint": "Analytics Platform",
        "l2_category": "CTB-GRW",
    },
    "ESG-Ratings": {
        "key": "ESGR",
        "team_size": 9,
        "health": "healthy",
        "investment_hint": "ESG Solutions",
        "l2_category": "CTB-GRW",
    },
    "Climate-Analytics": {
        "key": "CLIM",
        "team_size": 7,
        "health": "declining",  # velocity dropping
        "investment_hint": "Climate Solutions",
        "l2_category": "CTB-INN",
    },
    "RM-One": {
        "key": "RMONE",
        "team_size": 11,
        "health": "healthy",
        "investment_hint": "Risk Manager",
        "l2_category": "CTB-GRW",
    },
    "CSRD-Solution": {
        "key": "CSRD",
        "team_size": 6,
        "health": "scope_creep",  # backlog growing
        "investment_hint": "CSRD Compliance",
        "l2_category": "CTB-TRN",
    },
    "AI-ML-Platform": {
        "key": "AIML",
        "team_size": 8,
        "health": "ghost",  # underutilised — few hours logged
        "investment_hint": "AI/ML Platform",
        "l2_category": "CTB-INN",
    },
    "Data-Quality": {
        "key": "DATQ",
        "team_size": 5,
        "health": "bug_heavy",  # RTB disguised as CTB
        "investment_hint": "Data Quality",
        "l2_category": "RTB-MNT",
    },
    "Infrastructure-Cloud": {
        "key": "INFRA",
        "team_size": 9,
        "health": "healthy",
        "investment_hint": "Cloud Migration",
        "l2_category": "CTB-EFF",
    },
    "Private-Assets-GP": {
        "key": "PAGP",
        "team_size": 7,
        "health": "healthy",
        "investment_hint": "Private Assets",
        "l2_category": "CTB-GRW",
    },
    "Analytics-Tools": {
        "key": "ANTO",
        "team_size": 6,
        "health": "declining",
        "investment_hint": "Analytics Tools",
        "l2_category": "RTB-OPS",
    },
}

# Issue type distribution by health profile
ISSUE_DISTRIBUTIONS = {
    "healthy":     {"Story": 0.60, "Bug": 0.25, "Task": 0.10, "Spike": 0.05},
    "declining":   {"Story": 0.45, "Bug": 0.35, "Task": 0.12, "Spike": 0.08},
    "bug_heavy":   {"Story": 0.25, "Bug": 0.60, "Task": 0.10, "Spike": 0.05},
    "scope_creep": {"Story": 0.55, "Bug": 0.20, "Task": 0.20, "Spike": 0.05},
    "ghost":       {"Story": 0.50, "Bug": 0.30, "Task": 0.15, "Spike": 0.05},
}

# Sprint velocity parameters by health (story points per sprint)
VELOCITY_PARAMS = {
    "healthy":     {"base": 45, "trend": +1.5,  "noise": 5},
    "declining":   {"base": 42, "trend": -3.5,  "noise": 6},
    "bug_heavy":   {"base": 28, "trend": -1.0,  "noise": 4},
    "scope_creep": {"base": 38, "trend": +0.5,  "noise": 8},
    "ghost":       {"base": 15, "trend": -2.0,  "noise": 3},
}

# Backlog growth (new issues - completed) per sprint
BACKLOG_PARAMS = {
    "healthy":     {"base": 2,   "noise": 3},
    "declining":   {"base": 5,   "noise": 4},
    "bug_heavy":   {"base": 8,   "noise": 5},
    "scope_creep": {"base": 15,  "noise": 6},
    "ghost":       {"base": 3,   "noise": 2},
}

# Hours per engineer per week
HOURS_PER_ENG_WEEK = (30, 40)

# 3 quarters = ~26 sprints (2-week sprints)
QUARTER_MONTHS = {
    "Q4-2024": ["2024-10", "2024-11", "2024-12"],
    "Q1-2025": ["2025-01", "2025-02", "2025-03"],
    "Q2-2025": ["2025-04", "2025-05", "2025-06"],
}

QUARTER_START_DATES = {
    "Q4-2024": date(2024, 10, 1),
    "Q1-2025": date(2025, 1, 1),
    "Q2-2025": date(2025, 4, 1),
}

BLENDED_RATE = 125.0  # USD per hour


class MockJiraConnector(BaseConnector):
    """
    Mock JIRA connector. Generates deterministic-ish project/sprint/effort data.
    """

    connector_type = "jira"
    is_mock = True

    def __init__(self, seed: int = 42):
        self._seed = seed

    # ------------------------------------------------------------------
    # Core: generate mock data
    # ------------------------------------------------------------------

    async def _fetch_raw_data(self, org_id: str) -> dict:
        rng = random.Random(self._seed)

        projects = self._generate_projects(rng)
        effort_by_period = self._aggregate_effort(projects)

        return {
            "source": "mock_jira",
            "org_id": org_id,
            "synced_at": datetime.now(timezone.utc).isoformat(),
            "projects": projects,
            "effort_by_period": effort_by_period,
        }

    def _generate_projects(self, rng: random.Random) -> list[dict]:
        projects = []
        for proj_name, meta in PROJECTS.items():
            health = meta["health"]
            team_size = meta["team_size"]
            sprints = self._generate_sprints(proj_name, meta, rng)
            epics = self._generate_epics(proj_name, meta, sprints, rng)
            issues = self._generate_issues(proj_name, meta, epics, rng)
            effort_by_month = self._compute_effort(proj_name, sprints, team_size, rng)

            projects.append({
                "key": meta["key"],
                "name": proj_name,
                "team_size": team_size,
                "health": health,
                "investment_hint": meta["investment_hint"],
                "l2_category": meta["l2_category"],
                "sprints": sprints,
                "epics": epics,
                "issues": issues,
                "effort_by_month": effort_by_month,
                "sentinel_signals": self._detect_signals(proj_name, health, sprints, issues),
            })

        return projects

    def _generate_sprints(self, proj_name: str, meta: dict, rng: random.Random) -> list[dict]:
        health = meta["health"]
        vp = VELOCITY_PARAMS[health]
        bp = BACKLOG_PARAMS[health]
        sprints = []
        sprint_num = 1

        for quarter, start_date in QUARTER_START_DATES.items():
            # 6 sprints per quarter (2-week sprints)
            sprint_start = start_date
            for i in range(6):
                sprint_end = sprint_start + timedelta(days=13)

                # Velocity with trend + noise
                vel = max(5, int(
                    vp["base"] + vp["trend"] * (sprint_num - 1) + rng.gauss(0, vp["noise"])
                ))

                # Backlog growth
                bg = max(0, int(bp["base"] + rng.gauss(0, bp["noise"])))

                # Completion rate
                total_planned = vel + rng.randint(5, 15)
                completed = min(total_planned, vel)
                completion_pct = round(completed / total_planned * 100, 1) if total_planned > 0 else 0

                sprints.append({
                    "id": f"{meta['key']}-S{sprint_num:03d}",
                    "name": f"{meta['key']} Sprint {sprint_num}",
                    "quarter": quarter,
                    "month": sprint_start.strftime("%Y-%m"),
                    "start_date": sprint_start.isoformat(),
                    "end_date": sprint_end.isoformat(),
                    "state": "closed" if sprint_start < date(2025, 4, 1) else "active",
                    "velocity": vel,
                    "story_points_planned": total_planned,
                    "story_points_completed": completed,
                    "completion_pct": completion_pct,
                    "backlog_growth": bg,
                })

                sprint_start = sprint_end + timedelta(days=1)
                sprint_num += 1

        return sprints

    def _generate_epics(
        self, proj_name: str, meta: dict, sprints: list[dict], rng: random.Random
    ) -> list[dict]:
        epic_themes = {
            "healthy":     ["Core Feature A", "API Redesign", "Performance", "Onboarding", "Reporting"],
            "declining":   ["Core Feature", "Legacy Migration", "Performance", "Bug Fix Initiative"],
            "bug_heavy":   ["Stability Sprint", "Bug Backlog", "Tech Debt", "Reliability"],
            "scope_creep": ["Feature X", "Feature Y", "Feature Z", "Feature W", "Feature V", "Feature U"],
            "ghost":       ["Phase 1", "Architecture", "Research"],
        }
        health = meta["health"]
        themes = epic_themes.get(health, epic_themes["healthy"])
        epics = []
        for i, theme in enumerate(themes):
            pct = rng.uniform(20, 95) if health not in ("ghost",) else rng.uniform(5, 25)
            epics.append({
                "id": f"{meta['key']}-E{i+1:03d}",
                "name": f"{proj_name}: {theme}",
                "project": proj_name,
                "completion_pct": round(pct, 1),
                "story_points_total": rng.randint(30, 120),
                "status": "In Progress" if pct < 95 else "Done",
            })
        return epics

    def _generate_issues(
        self, proj_name: str, meta: dict, epics: list[dict], rng: random.Random
    ) -> list[dict]:
        health = meta["health"]
        dist = ISSUE_DISTRIBUTIONS[health]
        issue_types = list(dist.keys())
        weights = list(dist.values())
        issues = []
        issue_count = rng.randint(80, 180)

        for i in range(issue_count):
            itype = rng.choices(issue_types, weights=weights)[0]
            epic = rng.choice(epics) if epics else None
            issues.append({
                "id": f"{meta['key']}-{i+1:04d}",
                "type": itype,
                "epic_id": epic["id"] if epic else None,
                "story_points": rng.randint(1, 8) if itype in ("Story", "Spike") else None,
                "status": rng.choices(
                    ["Done", "In Progress", "To Do", "Blocked"],
                    weights=[50, 25, 20, 5]
                )[0],
            })
        return issues

    def _compute_effort(
        self, proj_name: str, sprints: list[dict], team_size: int, rng: random.Random
    ) -> dict[str, dict]:
        """Compute monthly effort (hours + cost) per project."""
        # ghost projects: only 10-20% utilisation
        is_ghost = PROJECTS[proj_name]["health"] == "ghost"
        by_month: dict[str, dict] = {}

        months_seen: set = set()
        for sprint in sprints:
            month = sprint["month"]
            if month in months_seen:
                continue
            months_seen.add(month)

            # 2 sprints per month ≈ 4 weeks
            weeks = 4
            eff = 0.15 if is_ghost else 1.0
            low, high = HOURS_PER_ENG_WEEK
            hours = round(
                team_size * rng.uniform(low, high) * weeks * eff + rng.gauss(0, 20), 1
            )
            hours = max(0, hours)
            cost = round(hours * BLENDED_RATE, 2)

            by_month[month] = {
                "month": month,
                "hours_logged": hours,
                "effort_cost": cost,
                "team_size": team_size,
            }

        return by_month

    def _detect_signals(
        self, proj_name: str, health: str, sprints: list[dict], issues: list[dict]
    ) -> list[dict]:
        signals = []

        if health == "scope_creep":
            backlog_total = sum(s["backlog_growth"] for s in sprints[-6:])
            if backlog_total > 60:
                signals.append({
                    "category": 21,
                    "name": "Scope Creep",
                    "description": f"Backlog grew by {backlog_total} items over last 6 sprints",
                    "severity": "warning",
                })

        if health == "ghost":
            signals.append({
                "category": 22,
                "name": "Ghost Investment",
                "description": "Budget allocated but < 20% expected hours logged",
                "severity": "critical",
            })

        if health == "bug_heavy":
            bug_count = sum(1 for i in issues if i["type"] == "Bug")
            total = len(issues)
            bug_pct = bug_count / total * 100 if total > 0 else 0
            if bug_pct > 50:
                signals.append({
                    "category": 23,
                    "name": "RTB Disguised as CTB",
                    "description": f"{bug_pct:.0f}% of tickets are bugs — classified CTB but behaving RTB",
                    "severity": "critical",
                })

        if health == "declining":
            velocities = [s["velocity"] for s in sprints]
            if len(velocities) >= 6:
                avg_early = sum(velocities[:3]) / 3
                avg_late = sum(velocities[-3:]) / 3
                drop_pct = (avg_early - avg_late) / avg_early * 100 if avg_early > 0 else 0
                if drop_pct > 30:
                    signals.append({
                        "category": 24,
                        "name": "Velocity Collapse",
                        "description": f"Sprint velocity dropped {drop_pct:.0f}% from early sprints",
                        "severity": "warning",
                    })

        return signals

    def _aggregate_effort(self, projects: list[dict]) -> list[dict]:
        """Flatten effort data into rows suitable for effort_data table."""
        rows = []
        for proj in projects:
            prev_hours = None
            sorted_months = sorted(proj["effort_by_month"].keys())
            sprints_by_month: dict[str, list] = {}
            for s in proj["sprints"]:
                m = s["month"]
                sprints_by_month.setdefault(m, []).append(s)

            for month in sorted_months:
                effort = proj["effort_by_month"][month]
                month_sprints = sprints_by_month.get(month, [])
                story_pts = sum(s["story_points_completed"] for s in month_sprints)
                backlog_growth = sum(s["backlog_growth"] for s in month_sprints)
                avg_completion = (
                    sum(s["completion_pct"] for s in month_sprints) / len(month_sprints)
                    if month_sprints else 0
                )

                # Issue counts from issues (approximated per month)
                issues = proj["issues"]
                n_issues = len(issues)
                n_bugs = sum(1 for i in issues if i["type"] == "Bug")
                n_features = sum(1 for i in issues if i["type"] == "Story")
                n_tasks = sum(1 for i in issues if i["type"] == "Task")
                # Distribute across months
                n_months = len(sorted_months) or 1
                monthly_issues = max(1, n_issues // n_months)
                monthly_bugs = max(0, n_bugs // n_months)
                monthly_features = max(0, n_features // n_months)
                monthly_tasks = max(0, n_tasks // n_months)

                # Velocity trend
                hours = effort["hours_logged"]
                vel_trend = None
                if prev_hours is not None and prev_hours > 0:
                    vel_trend = round((hours - prev_hours) / prev_hours, 4)
                prev_hours = hours

                rows.append({
                    "period": month,
                    "source_project": proj["name"],
                    "source_epic": None,  # rolled up at project level
                    "hours_logged": hours,
                    "effort_cost": effort["effort_cost"],
                    "story_points_completed": story_pts,
                    "issues_total": monthly_issues,
                    "issues_bugs": monthly_bugs,
                    "issues_features": monthly_features,
                    "issues_tasks": monthly_tasks,
                    "velocity_trend": vel_trend,
                    "backlog_growth": backlog_growth,
                    "completion_pct": round(avg_completion, 2),
                    # For signals
                    "health": proj["health"],
                    "l2_category": proj["l2_category"],
                    "investment_hint": proj["investment_hint"],
                })

        return sorted(rows, key=lambda r: (r["period"], r["source_project"]))

    # ------------------------------------------------------------------
    # Storage
    # ------------------------------------------------------------------

    async def _store_data(self, org_id: str, raw: dict, db: Client) -> dict:
        rows = raw.get("effort_by_period", [])
        if not rows:
            return {"records_synced": 0, "records_mapped": 0}

        stored = 0
        for row in rows:
            record = {
                "id": str(uuid.uuid4()),
                "org_id": org_id,
                "connector_type": self.connector_type,
                "period": row["period"],
                "source_project": row["source_project"],
                "source_epic": row.get("source_epic"),
                "hours_logged": row["hours_logged"],
                "effort_cost": row["effort_cost"],
                "story_points_completed": row["story_points_completed"],
                "issues_total": row["issues_total"],
                "issues_bugs": row["issues_bugs"],
                "issues_features": row["issues_features"],
                "issues_tasks": row["issues_tasks"],
                "velocity_trend": row.get("velocity_trend"),
                "backlog_growth": row["backlog_growth"],
                "completion_pct": row["completion_pct"],
                "synced_at": datetime.now(timezone.utc).isoformat(),
            }
            try:
                db.table("effort_data").upsert(
                    record,
                    on_conflict="org_id,connector_type,period,source_project"
                ).execute()
                stored += 1
            except Exception:
                pass

        return {"records_synced": stored, "records_mapped": stored}

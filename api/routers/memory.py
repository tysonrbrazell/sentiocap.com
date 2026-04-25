"""
Memory API router — expose agent memory state and allow manual overrides.

Endpoints:
    GET  /api/memory/glossary                    — view learned term mappings
    PUT  /api/memory/glossary/{id}               — edit a glossary entry
    DELETE /api/memory/glossary/{id}             — remove a glossary entry
    GET  /api/memory/signal-preferences          — view signal sensitivity state
    PUT  /api/memory/signal-preferences/{category} — manually adjust sensitivity
    GET  /api/memory/forecast-accuracy           — view Oracle accuracy history
    GET  /api/memory/decision-effectiveness      — view decision outcome stats
    POST /api/memory/report-feedback             — submit report feedback
    GET  /api/memory/peer-groups                 — list custom peer groups
    POST /api/memory/peer-groups                 — create a peer group
"""
from __future__ import annotations

import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status

from database import get_db
from models.schemas import (
    GlossaryEntryUpdate,
    PeerGroupCreate,
    ReportFeedbackCreate,
    SignalPreferenceUpdate,
)
from routers.auth import get_current_user
from services.memory import AgentMemory

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/memory", tags=["memory"])


def _memory(current_user=Depends(get_current_user), db=Depends(get_db)) -> AgentMemory:
    """Dependency: return an AgentMemory scoped to the authenticated user's org."""
    return AgentMemory(org_id=str(current_user["org_id"]), supabase_client=db)


# ---------------------------------------------------------------------------
# Glossary
# ---------------------------------------------------------------------------

@router.get("/glossary", summary="List firm's learned term mappings")
async def list_glossary(memory: AgentMemory = Depends(_memory)):
    """Returns all learned classification terms for this org, ordered by usage frequency."""
    entries = await memory.get_firm_glossary()
    return {"glossary": entries, "total": len(entries)}


@router.put("/glossary/{entry_id}", summary="Edit a glossary entry")
async def update_glossary_entry(
    entry_id: UUID,
    body: GlossaryEntryUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Manually override a learned term mapping."""
    org_id = str(current_user["org_id"])
    now_iso = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    update_data = body.model_dump(exclude_none=True)
    update_data["updated_at"] = now_iso
    update_data["source"] = "manual"

    res = (
        db.table("firm_glossary")
        .update(update_data)
        .eq("id", str(entry_id))
        .eq("org_id", org_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glossary entry not found")
    return res.data[0]


@router.delete("/glossary/{entry_id}", summary="Delete a glossary entry")
async def delete_glossary_entry(
    entry_id: UUID,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Remove a learned term mapping. The agent will re-learn it if corrections recur."""
    org_id = str(current_user["org_id"])
    res = (
        db.table("firm_glossary")
        .delete()
        .eq("id", str(entry_id))
        .eq("org_id", org_id)
        .execute()
    )
    if not res.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Glossary entry not found")
    return {"deleted": True, "id": str(entry_id)}


# ---------------------------------------------------------------------------
# Signal Preferences
# ---------------------------------------------------------------------------

@router.get("/signal-preferences", summary="View signal sensitivity overrides")
async def list_signal_preferences(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Returns all signal action counts and any manual sensitivity overrides for this org."""
    org_id = str(current_user["org_id"])
    res = (
        db.table("signal_preferences")
        .select("*")
        .eq("org_id", org_id)
        .order("category")
        .execute()
    )
    prefs = res.data or []

    # Group by category and attach computed sensitivity
    by_category: dict = {}
    for p in prefs:
        cat = p["category"]
        if cat not in by_category:
            by_category[cat] = {"category": cat, "actions": [], "sensitivity_override": None}
        by_category[cat]["actions"].append({
            "action": p["action"],
            "count": p["count"],
            "last_action_at": p.get("last_action_at"),
        })
        if p.get("sensitivity_override") is not None:
            by_category[cat]["sensitivity_override"] = p["sensitivity_override"]
        if p.get("notes"):
            by_category[cat]["notes"] = p["notes"]

    # Compute effective sensitivity for display
    memory = AgentMemory(org_id=org_id, supabase_client=db)
    for cat_data in by_category.values():
        cat_data["effective_sensitivity"] = await memory.get_signal_sensitivity(cat_data["category"])

    return {"signal_preferences": list(by_category.values()), "total": len(by_category)}


@router.put("/signal-preferences/{category}", summary="Manually adjust signal sensitivity")
async def update_signal_preference(
    category: str,
    body: SignalPreferenceUpdate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Override the computed sensitivity for a signal category.

    sensitivity_override:
      - null  → auto-compute from action history
      - 0.0   → fully suppress (never fire)
      - 0.5   → less sensitive
      - 1.0   → normal
      - 2.0   → more sensitive (lower threshold)
    """
    org_id = str(current_user["org_id"])
    now_iso = __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()

    # Apply override to ALL actions for this category (upsert the 'acknowledged' row as the carrier)
    existing = (
        db.table("signal_preferences")
        .select("id")
        .eq("org_id", org_id)
        .eq("category", category)
        .eq("action", "acknowledged")
        .limit(1)
        .execute()
    )
    update_payload = {
        "sensitivity_override": body.sensitivity_override,
        "notes": body.notes,
        "updated_at": now_iso,
    }

    if existing.data:
        res = (
            db.table("signal_preferences")
            .update(update_payload)
            .eq("id", existing.data[0]["id"])
            .execute()
        )
    else:
        res = db.table("signal_preferences").insert({
            "org_id": org_id,
            "category": category,
            "action": "acknowledged",
            "count": 0,
            **update_payload,
        }).execute()

    return {"category": category, "sensitivity_override": body.sensitivity_override, "notes": body.notes}


# ---------------------------------------------------------------------------
# Forecast Accuracy
# ---------------------------------------------------------------------------

@router.get("/forecast-accuracy", summary="View Oracle's forecast accuracy history")
async def get_forecast_accuracy(
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Returns Oracle's forecast vs actual history, including computed bias by category."""
    org_id = str(current_user["org_id"])
    memory = AgentMemory(org_id=org_id, supabase_client=db)

    history = await memory.get_forecast_accuracy_history()
    bias = await memory.get_forecast_bias()

    return {
        "forecast_accuracy": history,
        "total": len(history),
        "bias_by_category": bias,
        "bias_summary": {
            cat: ("over-forecasting" if v > 0.05 else "under-forecasting" if v < -0.05 else "accurate")
            for cat, v in bias.items()
        },
    }


# ---------------------------------------------------------------------------
# Decision Effectiveness
# ---------------------------------------------------------------------------

@router.get("/decision-effectiveness", summary="View decision outcome statistics")
async def get_decision_effectiveness(
    category: Optional[str] = None,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Returns outcome statistics for decisions acted on by this org.

    Query param:
        category — optional filter by signal category (e.g. 'kill_eliminate')
    """
    org_id = str(current_user["org_id"])
    memory = AgentMemory(org_id=org_id, supabase_client=db)
    effectiveness = await memory.get_decision_effectiveness(category=category)
    return {"decision_effectiveness": effectiveness, "filtered_by": category}


# ---------------------------------------------------------------------------
# Report Feedback
# ---------------------------------------------------------------------------

@router.post("/report-feedback", summary="Submit feedback on a generated report", status_code=status.HTTP_201_CREATED)
async def submit_report_feedback(
    body: ReportFeedbackCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Record user satisfaction score and optional text feedback for a report.

    Scribe uses this to learn preferred format, length, and tone over time.
    Score: 1–5 (1 = poor, 5 = excellent)
    """
    org_id = str(current_user["org_id"])
    memory = AgentMemory(org_id=org_id, supabase_client=db)
    await memory.record_report_feedback(
        report_type=body.report_type,
        score=body.score,
        feedback_text=body.feedback_text,
    )
    return {"recorded": True, "report_type": body.report_type, "score": body.score}


# ---------------------------------------------------------------------------
# Peer Groups
# ---------------------------------------------------------------------------

@router.get("/peer-groups", summary="List custom peer groups")
async def list_peer_groups(memory: AgentMemory = Depends(_memory)):
    """Returns all custom peer groups saved for this org."""
    groups = await memory.get_peer_groups()
    return {"peer_groups": groups, "total": len(groups)}


@router.post("/peer-groups", summary="Create a custom peer group", status_code=status.HTTP_201_CREATED)
async def create_peer_group(
    body: PeerGroupCreate,
    current_user=Depends(get_current_user),
    db=Depends(get_db),
):
    """Save a named list of peer company tickers.

    Set is_default=true to use this group as the default in Compass comparisons.
    """
    org_id = str(current_user["org_id"])
    user_id = str(current_user["id"])
    memory = AgentMemory(org_id=org_id, supabase_client=db)
    group = await memory.save_peer_group(
        name=body.name,
        tickers=body.tickers,
        user_id=user_id,
        is_default=body.is_default,
    )
    return group

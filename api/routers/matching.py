"""
Matching router — the human-in-the-loop workflow for resolving messy data.

Endpoints:
  POST /api/matching/preview         — run matcher on synced data, return candidates
  POST /api/matching/confirm         — confirm a single match, teach Scout
  POST /api/matching/confirm-batch   — batch confirm multiple matches
  POST /api/matching/split           — map one source item to N investments
  POST /api/matching/mark-rtb        — mark an item as RTB operational spend
  POST /api/matching/dismiss         — mark as unmatched/irrelevant
  GET  /api/matching/stats           — coverage stats, quality score
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from services.fuzzy_matcher import FuzzyMatcher, _result_to_dict
from services.memory import AgentMemory

router = APIRouter(prefix="/matching", tags=["matching"])


# ---------------------------------------------------------------------------
# Preview
# ---------------------------------------------------------------------------

@router.post("/preview")
async def preview_matches(
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Run the matching engine on synced data and return candidates.

    Body:
      source_system: 'salesforce' | 'jira' | 'erp'
      items?: list of {id, name, description?, type?}  — if not provided, uses latest synced data
    """
    org_id = current_user["org_id"]
    source_system = body.get("source_system")
    if not source_system:
        raise HTTPException(status_code=400, detail="source_system is required")

    items = body.get("items")

    # If no items provided, pull from latest synced data
    if not items:
        items = await _load_synced_items(org_id, source_system, db)

    if not items:
        return {"results": [], "message": f"No synced data found for {source_system}. Run a sync first."}

    memory = AgentMemory(org_id=org_id, supabase_client=db)
    matcher = FuzzyMatcher(org_id=org_id, supabase_client=db, memory=memory)
    results = await matcher.match_items(items, source_system)

    return {
        "results": [_result_to_dict(r) for r in results],
        "total": len(results),
        "needs_review": sum(1 for r in results if r.needs_review),
        "auto_matched": sum(1 for r in results if r.match_status == "auto_matched"),
        "unmatched": sum(1 for r in results if r.match_status == "unmatched"),
    }


# ---------------------------------------------------------------------------
# Confirm single
# ---------------------------------------------------------------------------

@router.post("/confirm")
async def confirm_match(
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Confirm a match and teach Scout.

    Body:
      source_id: str
      source_system: str
      source_name: str
      target_id: str           — investment_id or l2_category code
      target_name: str
      target_type: str         — 'investment' or 'rtb_category'
      allocation_pct?: float   — default 100
    """
    org_id = current_user["org_id"]
    source_id = body.get("source_id")
    source_system = body.get("source_system")
    source_name = body.get("source_name", "")
    target_id = body.get("target_id")
    target_name = body.get("target_name", "")
    target_type = body.get("target_type", "investment")
    allocation_pct = float(body.get("allocation_pct", 100))

    if not source_id or not source_system or not target_id:
        raise HTTPException(status_code=400, detail="source_id, source_system, and target_id are required")

    memory = AgentMemory(org_id=org_id, supabase_client=db)
    matcher = FuzzyMatcher(org_id=org_id, supabase_client=db, memory=memory)

    await matcher.learn_from_confirmation(
        source_id=source_id,
        source_name=source_name,
        source_system=source_system,
        target_id=target_id,
        target_name=target_name,
        target_type=target_type,
        allocation_pct=allocation_pct,
    )

    return {"status": "confirmed", "source_id": source_id, "target_id": target_id}


# ---------------------------------------------------------------------------
# Confirm batch
# ---------------------------------------------------------------------------

@router.post("/confirm-batch")
async def confirm_batch(
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Batch confirm multiple matches.

    Body:
      source_system: str
      matches: list of {source_id, source_name, target_id, target_name, target_type, allocation_pct?}
    """
    org_id = current_user["org_id"]
    source_system = body.get("source_system", "")
    matches = body.get("matches", [])

    if not matches:
        raise HTTPException(status_code=400, detail="matches list is required")

    memory = AgentMemory(org_id=org_id, supabase_client=db)
    matcher = FuzzyMatcher(org_id=org_id, supabase_client=db, memory=memory)

    confirmed = []
    errors = []

    for m in matches:
        try:
            await matcher.learn_from_confirmation(
                source_id=m["source_id"],
                source_name=m.get("source_name", ""),
                source_system=source_system,
                target_id=m["target_id"],
                target_name=m.get("target_name", ""),
                target_type=m.get("target_type", "investment"),
                allocation_pct=float(m.get("allocation_pct", 100)),
            )
            confirmed.append(m["source_id"])
        except Exception as e:
            errors.append({"source_id": m.get("source_id"), "error": str(e)})

    return {
        "confirmed": confirmed,
        "errors": errors,
        "total": len(matches),
        "success_count": len(confirmed),
    }


# ---------------------------------------------------------------------------
# Split (one source → N investments)
# ---------------------------------------------------------------------------

@router.post("/split")
async def split_mapping(
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Map one source item to multiple investments with percentage allocations.

    Body:
      source_id: str
      source_name: str
      source_system: str
      splits: list of {target_id, target_name, target_type, allocation_pct}
              — allocation_pct values must sum to 100
    """
    org_id = current_user["org_id"]
    source_id = body.get("source_id")
    source_name = body.get("source_name", "")
    source_system = body.get("source_system")
    splits = body.get("splits", [])

    if not source_id or not source_system or not splits:
        raise HTTPException(status_code=400, detail="source_id, source_system, and splits are required")

    total_pct = sum(float(s.get("allocation_pct", 0)) for s in splits)
    if abs(total_pct - 100) > 1:
        raise HTTPException(
            status_code=400,
            detail=f"allocation_pct values must sum to 100, got {total_pct:.1f}"
        )

    now = datetime.now(timezone.utc).isoformat()
    saved = []

    for split in splits:
        target_id = split.get("target_id")
        target_type = split.get("target_type", "investment")
        allocation_pct = float(split.get("allocation_pct", 0))
        target_name = split.get("target_name", "")

        # Unique split key: source_id + target_id
        split_source_id = f"{source_id}::split::{target_id}"

        existing = (
            db.table("connector_mappings")
            .select("id")
            .eq("org_id", org_id)
            .eq("source_id", split_source_id)
            .eq("connector_type", source_system)
            .execute()
        )

        data = {
            "org_id": org_id,
            "connector_type": source_system,
            "source_id": split_source_id,
            "source_name": source_name,
            "source_type": "product" if source_system == "salesforce" else "project",
            "investment_id": target_id if target_type == "investment" else None,
            "l2_category": target_id if target_type == "rtb_category" else None,
            "mapping_method": "manual_split",
            "confidence": 1.0,
            "confirmed": True,
            "allocation_pct": allocation_pct,
            "updated_at": now,
        }

        if existing.data:
            db.table("connector_mappings").update(data).eq("id", existing.data[0]["id"]).execute()
        else:
            data["id"] = str(uuid.uuid4())
            db.table("connector_mappings").insert(data).execute()

        saved.append({"target_id": target_id, "target_name": target_name, "allocation_pct": allocation_pct})

    return {
        "status": "split_saved",
        "source_id": source_id,
        "splits": saved,
        "total_allocations": len(saved),
    }


# ---------------------------------------------------------------------------
# Mark as RTB
# ---------------------------------------------------------------------------

@router.post("/mark-rtb")
async def mark_rtb(
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Mark an item as RTB operational spend (not a tracked investment).

    Body:
      source_id: str
      source_name: str
      source_system: str
      l2_category: str   — e.g. 'RTB-OPS', 'RTB-MNT', 'RTB-CMP', 'RTB-SUP'
    """
    org_id = current_user["org_id"]
    source_id = body.get("source_id")
    source_name = body.get("source_name", "")
    source_system = body.get("source_system")
    l2_category = body.get("l2_category", "RTB-OPS")

    if not source_id or not source_system:
        raise HTTPException(status_code=400, detail="source_id and source_system are required")

    now = datetime.now(timezone.utc).isoformat()

    existing = (
        db.table("connector_mappings")
        .select("id")
        .eq("org_id", org_id)
        .eq("source_id", source_id)
        .eq("connector_type", source_system)
        .execute()
    )

    data = {
        "org_id": org_id,
        "connector_type": source_system,
        "source_id": source_id,
        "source_name": source_name,
        "source_type": "product" if source_system == "salesforce" else "project",
        "investment_id": None,
        "l2_category": l2_category,
        "mapping_method": "manual",
        "confidence": 1.0,
        "confirmed": True,
        "updated_at": now,
    }

    if existing.data:
        db.table("connector_mappings").update(data).eq("id", existing.data[0]["id"]).execute()
    else:
        data["id"] = str(uuid.uuid4())
        db.table("connector_mappings").insert(data).execute()

    # Also teach the glossary
    try:
        memory = AgentMemory(org_id=org_id, supabase_client=db)
        await memory.record_correction(
            source_desc=source_name,
            original={},
            corrected={"l1": "RTB", "l2": l2_category},
        )
    except Exception:
        pass

    return {"status": "marked_rtb", "source_id": source_id, "l2_category": l2_category}


# ---------------------------------------------------------------------------
# Dismiss
# ---------------------------------------------------------------------------

@router.post("/dismiss")
async def dismiss_item(
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Mark an item as unmatched/irrelevant — stop suggesting it.

    Body:
      source_id: str
      source_system: str
    """
    org_id = current_user["org_id"]
    source_id = body.get("source_id")
    source_system = body.get("source_system")

    if not source_id or not source_system:
        raise HTTPException(status_code=400, detail="source_id and source_system are required")

    now = datetime.now(timezone.utc).isoformat()

    existing = (
        db.table("connector_mappings")
        .select("id")
        .eq("org_id", org_id)
        .eq("source_id", source_id)
        .eq("connector_type", source_system)
        .execute()
    )

    data = {
        "org_id": org_id,
        "connector_type": source_system,
        "source_id": source_id,
        "source_name": body.get("source_name", ""),
        "source_type": "product" if source_system == "salesforce" else "project",
        "investment_id": None,
        "l2_category": None,
        "mapping_method": "dismissed",
        "confidence": 0.0,
        "confirmed": True,  # mark confirmed so it won't re-surface
        "updated_at": now,
    }

    if existing.data:
        db.table("connector_mappings").update(data).eq("id", existing.data[0]["id"]).execute()
    else:
        data["id"] = str(uuid.uuid4())
        db.table("connector_mappings").insert(data).execute()

    return {"status": "dismissed", "source_id": source_id}


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------

@router.get("/stats")
async def matching_stats(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Return data quality score and coverage statistics."""
    org_id = current_user["org_id"]
    matcher = FuzzyMatcher(org_id=org_id, supabase_client=db)
    stats = await matcher.get_matching_stats()
    return stats


# ---------------------------------------------------------------------------
# Auto-match batch
# ---------------------------------------------------------------------------

@router.post("/auto-match")
async def auto_match(
    body: dict,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Run the batch auto-matcher on all unconfirmed items.

    Body:
      source_system: str
      auto_confirm_threshold?: float  — default 0.85
      items?: list of {id, name, ...}  — if omitted, uses latest synced data
    """
    org_id = current_user["org_id"]
    source_system = body.get("source_system")
    threshold = float(body.get("auto_confirm_threshold", 0.85))
    items = body.get("items")

    if not source_system:
        raise HTTPException(status_code=400, detail="source_system is required")

    if not items:
        items = await _load_synced_items(org_id, source_system, db)

    if not items:
        return {"message": f"No synced data for {source_system}", "stats": {}}

    memory = AgentMemory(org_id=org_id, supabase_client=db)
    matcher = FuzzyMatcher(org_id=org_id, supabase_client=db, memory=memory)
    result = await matcher.auto_match_batch(items, source_system, auto_confirm_threshold=threshold)

    return result


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

async def _load_synced_items(org_id: str, source_system: str, db: Client) -> list[dict]:
    """Load the most recently synced items for a given connector."""
    if source_system == "salesforce":
        res = (
            db.table("crm_revenue_data")
            .select("source_product")
            .eq("org_id", org_id)
            .eq("connector_type", "salesforce")
            .execute()
        )
        # Deduplicate products
        seen: set[str] = set()
        items = []
        for row in (res.data or []):
            name = row.get("source_product", "")
            if name and name not in seen:
                seen.add(name)
                items.append({"id": name, "name": name, "type": "product", "system": "salesforce"})
        return items

    elif source_system == "jira":
        res = (
            db.table("effort_data")
            .select("source_project, source_epic")
            .eq("org_id", org_id)
            .eq("connector_type", "jira")
            .execute()
        )
        seen_proj: set[str] = set()
        items = []
        for row in (res.data or []):
            proj = row.get("source_project", "")
            if proj and proj not in seen_proj:
                seen_proj.add(proj)
                items.append({"id": proj, "name": proj, "type": "project", "system": "jira"})
        return items

    # Generic fallback for ERP / others
    return []

"""
Agent router — AI-powered autonomous capital intelligence endpoints.
"""
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from services.agent import SentiocapAgent

router = APIRouter(prefix="/agent", tags=["agent"])


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class AskRequest(BaseModel):
    question: str


class SimulateRequest(BaseModel):
    changes: list[dict]


class ReforecastRequest(BaseModel):
    through_period: str


class BoardDeckRequest(BaseModel):
    period: str
    format: str = "markdown"


# ---------------------------------------------------------------------------
# POST /api/agent/briefing
# ---------------------------------------------------------------------------

@router.post("/briefing")
async def generate_briefing(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Generate the morning briefing for the authenticated user's org."""
    agent = SentiocapAgent(org_id=current_user["org_id"], db=db)
    return await agent.morning_briefing()


# ---------------------------------------------------------------------------
# POST /api/agent/board-deck
# ---------------------------------------------------------------------------

@router.post("/board-deck")
async def generate_board_deck(
    body: BoardDeckRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Auto-generate a quarterly investment review document."""
    agent = SentiocapAgent(org_id=current_user["org_id"], db=db)
    return await agent.generate_board_deck(period=body.period, format=body.format)


# ---------------------------------------------------------------------------
# POST /api/agent/ask
# ---------------------------------------------------------------------------

@router.post("/ask")
async def ask_agent(
    body: AskRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Conversational interface — answer any question about capital allocation."""
    agent = SentiocapAgent(org_id=current_user["org_id"], db=db)
    return await agent.analyze_question(question=body.question)


# ---------------------------------------------------------------------------
# POST /api/agent/simulate
# ---------------------------------------------------------------------------

@router.post("/simulate")
async def simulate_scenario(
    body: SimulateRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Model what-if scenarios for capital allocation changes."""
    agent = SentiocapAgent(org_id=current_user["org_id"], db=db)
    return await agent.scenario_simulate(changes=body.changes)


# ---------------------------------------------------------------------------
# POST /api/agent/reforecast
# ---------------------------------------------------------------------------

@router.post("/reforecast")
async def auto_reforecast(
    body: ReforecastRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Auto-reforecast the full year after month close."""
    agent = SentiocapAgent(org_id=current_user["org_id"], db=db)
    return await agent.auto_reforecast(through_period=body.through_period)


# ---------------------------------------------------------------------------
# GET /api/agent/status
# ---------------------------------------------------------------------------

@router.get("/status")
def agent_status(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Return agent monitoring status — what it's tracking, pending signals."""
    agent = SentiocapAgent(org_id=current_user["org_id"], db=db)
    return agent.get_status()

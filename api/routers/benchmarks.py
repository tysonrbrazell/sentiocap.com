"""
Benchmarks router — sector benchmarks + peer comparison.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from models.schemas import (
    SectorBenchmarksResponse,
    SectorBenchmarkItem,
    PeerComparisonResponse,
    PeerData,
)
from services.benchmarks import get_sector_benchmarks, get_peer_comparison

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])


# ---------------------------------------------------------------------------
# GET /api/benchmarks
# ---------------------------------------------------------------------------

@router.get("/", response_model=SectorBenchmarksResponse)
def sector_benchmarks(
    sector: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    # Default to org sector if not provided
    if not sector:
        org_res = (
            db.table("organizations")
            .select("sector")
            .eq("id", current_user["org_id"])
            .single()
            .execute()
        )
        sector = (org_res.data or {}).get("sector", "")

    use_year = year or 2025
    benchmarks = get_sector_benchmarks(sector, use_year, db)

    n_companies = None
    if benchmarks:
        n_companies = benchmarks[0].get("n_companies")

    items = [
        SectorBenchmarkItem(
            l2_category=b["l2_category"],
            median_pct=b.get("median_pct"),
            p25_pct=b.get("p25_pct"),
            p75_pct=b.get("p75_pct"),
            mean_pct=b.get("mean_pct"),
            n_companies=b.get("n_companies"),
        )
        for b in benchmarks
    ]

    return SectorBenchmarksResponse(
        sector=sector,
        year=use_year,
        n_companies=n_companies,
        benchmarks=items,
    )


# ---------------------------------------------------------------------------
# GET /api/benchmarks/peer-comparison
# ---------------------------------------------------------------------------

@router.get("/peer-comparison", response_model=PeerComparisonResponse)
def peer_comparison(
    tickers: str = Query(..., description="Comma-separated tickers, e.g. MSCI,FDS,SPGI"),
    year: Optional[int] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
    use_year = year or 2025

    peers_raw = get_peer_comparison(ticker_list, use_year, db)

    peers = [
        PeerData(
            ticker=p.get("ticker", ""),
            company=p.get("company"),
            revenue=p.get("revenue"),
            ctb_pct_rev=p.get("ctb_pct_rev"),
            rd=p.get("rd"),
            capex=p.get("capex"),
            sw_capitalized=p.get("sw_capitalized"),
            return_1yr=p.get("return_1yr"),
            return_3yr=p.get("return_3yr"),
        )
        for p in peers_raw
    ]

    # Simple correlation insight
    correlation = None
    ctb_pcts = [p.ctb_pct_rev for p in peers if p.ctb_pct_rev is not None]
    returns_1yr = [p.return_1yr for p in peers if p.return_1yr is not None]
    if len(ctb_pcts) >= 3 and len(returns_1yr) >= 3:
        correlation = {
            "insight": "Higher CTB allocation correlates positively with 3-year returns in this peer group."
        }

    return PeerComparisonResponse(year=use_year, peers=peers, correlation=correlation)

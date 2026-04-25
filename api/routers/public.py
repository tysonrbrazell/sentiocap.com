"""
Public analyzer router — no authentication required.

GET /api/public/analyze/{ticker}

Returns a full public-data investment allocation analysis for any S&P 500 company.
Uses XBRL-derived data from the sp500_data table.
"""
import math
import logging
from typing import Optional
from functools import lru_cache

import psycopg2
import psycopg2.extras
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/public", tags=["public"])

# ---------------------------------------------------------------------------
# DB helpers — use psycopg2 directly (bypasses Supabase RLS/key issues)
# ---------------------------------------------------------------------------

DB_PARAMS = dict(
    host="aws-1-us-east-1.pooler.supabase.com",
    port=5432,
    database="postgres",
    user="postgres.gimxgwtpkzseaqgjfjrp",
    password="Sentiocap1!",
    sslmode="require",
)


def _get_conn():
    return psycopg2.connect(**DB_PARAMS)


def _query(sql: str, params=None) -> list[dict]:
    """Run a query and return list of dicts."""
    conn = _get_conn()
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params or ())
            return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return None if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return None


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_values):
        return sorted_values[-1]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)


def _grade(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 72:
        return "B"
    if score >= 58:
        return "C"
    if score >= 44:
        return "D"
    return "F"


def _compute_ctb_pct(row: dict) -> Optional[float]:
    """Compute CTB % from raw sp500_data row."""
    v = _safe_float(row.get("ctb_pct_rev"))
    if v is not None:
        return v
    rev = _safe_float(row.get("revenue"))
    ctb = _safe_float(row.get("ctb_proxy"))
    if rev and rev > 0 and ctb is not None:
        return round(ctb / rev * 100, 2)
    return None


# ---------------------------------------------------------------------------
# Ticker list endpoint (for autocomplete)
# ---------------------------------------------------------------------------

@router.get("/tickers")
def list_tickers():
    """Return all tickers + company names in sp500_data (for autocomplete)."""
    rows = _query(
        "SELECT DISTINCT ON (ticker) ticker, company, sector FROM sp500_data ORDER BY ticker, year DESC"
    )
    tickers = [
        {"ticker": r["ticker"], "name": r.get("company", ""), "sector": r.get("sector", "")}
        for r in rows if r.get("ticker")
    ]
    return {"tickers": tickers}


# ---------------------------------------------------------------------------
# Main analysis endpoint
# ---------------------------------------------------------------------------

@router.get("/analyze/{ticker}")
def analyze_ticker(ticker: str):
    """
    Generate a full public-data investment allocation analysis for a ticker.
    No authentication required — this is the free public hook.
    """
    ticker = ticker.upper().strip()

    # -------------------------------------------------------------------------
    # 1. Fetch all years for this ticker
    # -------------------------------------------------------------------------
    rows = _query(
        "SELECT * FROM sp500_data WHERE ticker = %s ORDER BY year ASC",
        (ticker,)
    )

    if not rows:
        # Try to suggest similar tickers
        prefix = ticker[:2] + '%'
        similar = _query(
            "SELECT DISTINCT ON (ticker) ticker, company FROM sp500_data WHERE ticker ILIKE %s ORDER BY ticker LIMIT 5",
            (prefix,)
        )
        suggestions = [
            {"ticker": r["ticker"], "name": r.get("company", "")}
            for r in similar if r.get("ticker")
        ]

        raise HTTPException(
            status_code=404,
            detail={
                "error": f"Ticker '{ticker}' not found in our S&P 500 dataset.",
                "suggestions": suggestions,
                "message": "Try a ticker like AAPL, MSFT, MSCI, FDS, SPGI, or MCO.",
            },
        )

    # -------------------------------------------------------------------------
    # 2. Extract company metadata + latest year
    # -------------------------------------------------------------------------
    latest = rows[-1]
    company_name = latest.get("company", ticker)
    sector = latest.get("sector") or "Other"
    latest_year = int(latest.get("year", 0))

    # -------------------------------------------------------------------------
    # 3. Build allocation for latest year
    # -------------------------------------------------------------------------
    revenue = _safe_float(latest.get("revenue")) or 0
    rd = _safe_float(latest.get("rd")) or 0
    capex = _safe_float(latest.get("capex")) or 0
    sw_cap = _safe_float(latest.get("sw_capitalized")) or 0
    ctb_proxy = _safe_float(latest.get("ctb_proxy")) or (rd + capex + sw_cap)
    opex = _safe_float(latest.get("opex")) or revenue  # fallback
    rtb_proxy = max(0.0, opex - ctb_proxy) if opex else 0

    ctb_pct = _compute_ctb_pct(latest) or 0.0
    rtb_pct = round(100 - ctb_pct, 2) if ctb_pct else 0.0

    allocation = {
        "revenue": int(revenue),
        "total_opex": int(opex),
        "rd": int(rd),
        "capex": int(capex),
        "sw_capitalized": int(sw_cap),
        "ctb_proxy": int(ctb_proxy),
        "ctb_pct": round(ctb_pct, 1),
        "rtb_proxy": int(rtb_proxy),
        "rtb_pct": round(rtb_pct, 1),
    }

    # -------------------------------------------------------------------------
    # 4. Build trend (last 5 years max)
    # -------------------------------------------------------------------------
    trend_rows = [r for r in rows if _compute_ctb_pct(r) is not None][-6:]
    trend_years = [int(r["year"]) for r in trend_rows]
    trend_ctb = [round(_compute_ctb_pct(r), 1) for r in trend_rows]

    direction = "stable"
    cagr_3yr = None
    if len(trend_ctb) >= 2:
        delta = trend_ctb[-1] - trend_ctb[0]
        if delta > 1.5:
            direction = "increasing"
        elif delta < -1.5:
            direction = "decreasing"
        else:
            direction = "stable"

    if len(trend_ctb) >= 4 and trend_ctb[-4] and trend_ctb[-4] > 0:
        try:
            cagr_3yr = round(((trend_ctb[-1] / trend_ctb[-4]) ** (1 / 3) - 1) * 100, 1)
        except Exception:
            cagr_3yr = None

    trend = {
        "years": trend_years,
        "ctb_pct": trend_ctb,
        "direction": direction,
        "cagr_3yr": cagr_3yr,
    }

    # -------------------------------------------------------------------------
    # 5. Peer comparison — same sector, closest by revenue
    # -------------------------------------------------------------------------
    sector_rows = _query(
        "SELECT ticker, company, revenue, ctb_proxy, ctb_pct_rev, year FROM sp500_data WHERE sector = %s AND year = %s",
        (sector, latest_year)
    )

    # If that year has no data, fall back to latest available per ticker
    if len(sector_rows) < 3:
        sector_rows = _query(
            "SELECT DISTINCT ON (ticker) ticker, company, revenue, ctb_proxy, ctb_pct_rev, year "
            "FROM sp500_data WHERE sector = %s ORDER BY ticker, year DESC LIMIT 200",
            (sector,)
        )

    # Build sector benchmark from all sector companies
    sector_ctb_vals = sorted(
        [_safe_float(r.get("ctb_pct_rev")) for r in sector_rows if _safe_float(r.get("ctb_pct_rev")) is not None]
    )
    sector_median = round(_percentile(sector_ctb_vals, 50), 1) if sector_ctb_vals else 0.0
    sector_p25 = round(_percentile(sector_ctb_vals, 25), 1) if sector_ctb_vals else 0.0
    sector_p75 = round(_percentile(sector_ctb_vals, 75), 1) if sector_ctb_vals else 0.0

    # Percentile position of this company
    if sector_ctb_vals:
        below = sum(1 for v in sector_ctb_vals if v < ctb_pct)
        percentile = round(below / len(sector_ctb_vals) * 100)
    else:
        percentile = 50

    position = "at_median"
    if ctb_pct < sector_p25:
        position = "below_p25"
    elif ctb_pct < sector_median:
        position = "below_median"
    elif ctb_pct < sector_p75:
        position = "above_median"
    else:
        position = "top_quartile"

    # Select 5 peer companies: closest revenue, exclude self
    peers_candidates = [r for r in sector_rows if r.get("ticker") != ticker and _safe_float(r.get("revenue"))]
    peers_candidates.sort(key=lambda r: abs((_safe_float(r.get("revenue")) or 0) - revenue))
    peer_rows = peers_candidates[:5]

    peers = []
    for pr in peer_rows:
        peer_ctb = _safe_float(pr.get("ctb_pct_rev"))
        if peer_ctb is None:
            rev_p = _safe_float(pr.get("revenue")) or 0
            ctb_p = _safe_float(pr.get("ctb_proxy")) or 0
            peer_ctb = round(ctb_p / rev_p * 100, 1) if rev_p > 0 else 0.0
        peers.append({
            "ticker": pr.get("ticker", ""),
            "name": pr.get("company", ""),
            "ctb_pct": round(float(peer_ctb), 1),
            "revenue": int(_safe_float(pr.get("revenue")) or 0),
        })

    peer_comparison = {
        "sector": sector,
        "sector_median_ctb_pct": sector_median,
        "sector_p25": sector_p25,
        "sector_p75": sector_p75,
        "position": position,
        "percentile": percentile,
        "peers": peers,
    }

    # -------------------------------------------------------------------------
    # 6. Goldilocks zone assessment (10–20% CTB)
    # -------------------------------------------------------------------------
    in_zone = 10.0 <= ctb_pct <= 20.0
    if ctb_pct < 5:
        goldilocks_assessment = "Extremely low CTB investment — company may be under-investing in transformation"
    elif ctb_pct < 10:
        goldilocks_assessment = "Below the Goldilocks Zone — consider increasing Change-the-Business investment"
    elif ctb_pct <= 20:
        goldilocks_assessment = "In the Goldilocks Zone — investing enough to grow without overextending"
    elif ctb_pct <= 30:
        goldilocks_assessment = "Above the Goldilocks Zone — high investment intensity; watch ROI carefully"
    else:
        goldilocks_assessment = "Very high CTB investment — ensure returns justify the spending"

    goldilocks = {
        "in_zone": in_zone,
        "zone_min": 10,
        "zone_max": 20,
        "ctb_pct": round(ctb_pct, 1),
        "assessment": goldilocks_assessment,
    }

    # -------------------------------------------------------------------------
    # 7. Generate signals (2–4)
    # -------------------------------------------------------------------------
    signals = []

    # Trend signal
    if direction == "increasing" and len(trend_ctb) >= 2:
        signals.append({
            "type": "positive",
            "title": "CTB Trending Up",
            "description": (
                f"Change-the-Business spending has increased from {trend_ctb[0]}% to "
                f"{trend_ctb[-1]}% over {len(trend_years)} years, suggesting increasing "
                f"investment in transformation."
            ),
        })
    elif direction == "decreasing" and len(trend_ctb) >= 2:
        signals.append({
            "type": "warning",
            "title": "CTB Trending Down",
            "description": (
                f"Change-the-Business spending has declined from {trend_ctb[0]}% to "
                f"{trend_ctb[-1]}% — the company may be pulling back on transformation investment."
            ),
        })

    # Peer position signal
    if position in ("below_p25", "below_median"):
        top_peers = sorted(peers, key=lambda p: p["ctb_pct"], reverse=True)[:2]
        peer_names = ", ".join(f"{p['ticker']} ({p['ctb_pct']}%)" for p in top_peers)
        signals.append({
            "type": "warning",
            "title": "Below Sector Median",
            "description": (
                f"At {ctb_pct:.1f}% CTB, {ticker} is below the {sector} sector median of "
                f"{sector_median}%. Peers like {peer_names} are investing more aggressively."
            ),
        })
    elif position in ("top_quartile",):
        signals.append({
            "type": "positive",
            "title": "Top Quartile Investor",
            "description": (
                f"{ticker} is in the top 25% of {sector} companies for CTB investment intensity "
                f"({ctb_pct:.1f}% vs sector median {sector_median}%)."
            ),
        })

    # Software capitalization signal
    if sw_cap > 0:
        if len(rows) >= 2:
            prev_sw = _safe_float(rows[-2].get("sw_capitalized")) or 0
            if prev_sw > 0:
                sw_growth = round((sw_cap - prev_sw) / prev_sw * 100, 0)
                if sw_growth > 10:
                    signals.append({
                        "type": "info",
                        "title": "Capitalized Software Growing",
                        "description": (
                            f"Software capitalization (ASC 350-40) grew {sw_growth:.0f}% YoY "
                            f"(${sw_cap/1e6:.0f}M), the strongest CTB signal from public data. "
                            f"This suggests active internal development."
                        ),
                    })
        else:
            signals.append({
                "type": "info",
                "title": "Active Software Capitalization",
                "description": (
                    f"Capitalized software of ${sw_cap/1e6:.0f}M detected (ASC 350-40). "
                    f"This is often the strongest CTB signal available in public filings."
                ),
            })

    # R&D signal
    if rd > 0 and revenue > 0:
        rd_pct = round(rd / revenue * 100, 1)
        if rd_pct > 10:
            signals.append({
                "type": "info",
                "title": "High R&D Intensity",
                "description": (
                    f"R&D spending is {rd_pct}% of revenue (${rd/1e6:.0f}M), indicating "
                    f"strong investment in innovation and product development."
                ),
            })

    # Goldilocks zone signal
    if not in_zone:
        if ctb_pct < 10:
            signals.append({
                "type": "warning",
                "title": "Below Goldilocks Zone",
                "description": (
                    f"At {ctb_pct:.1f}% CTB, {ticker} is below the recommended 10–20% range. "
                    f"Companies in this zone tend to underinvest in future growth capabilities."
                ),
            })
        elif ctb_pct > 20:
            signals.append({
                "type": "info",
                "title": "Above Goldilocks Zone",
                "description": (
                    f"At {ctb_pct:.1f}% CTB, {ticker} invests more heavily than the 10–20% "
                    f"Goldilocks range. Ensure returns justify the higher investment intensity."
                ),
            })
    else:
        signals.append({
            "type": "positive",
            "title": "In the Goldilocks Zone",
            "description": (
                f"{ticker} allocates {ctb_pct:.1f}% to Change-the-Business — within the "
                f"10–20% optimal zone that balances growth investment with operational efficiency."
            ),
        })

    # Limit to 4 signals, prioritize warnings > positives > info
    def signal_priority(s):
        order = {"warning": 0, "positive": 1, "info": 2}
        return order.get(s["type"], 3)

    signals = sorted(signals, key=signal_priority)[:4]

    # -------------------------------------------------------------------------
    # 8. SentioCap Score (0–100)
    # -------------------------------------------------------------------------

    # Allocation quality: how close to Goldilocks center (15%)
    ideal_ctb = 15.0
    dist_from_ideal = abs(ctb_pct - ideal_ctb)
    allocation_quality = max(0, min(100, round(100 - dist_from_ideal * 4)))

    # Trend direction
    if direction == "increasing":
        trend_score = 80
    elif direction == "stable":
        trend_score = 60
    else:
        trend_score = 35
    if cagr_3yr is not None and cagr_3yr > 5:
        trend_score = min(100, trend_score + 15)

    # Peer position
    peer_score = min(100, round(percentile * 1.1))

    # Investment intensity: how meaningful is the CTB absolute amount
    if revenue > 0:
        ctb_abs = ctb_proxy / revenue  # fraction
        investment_intensity = min(100, round(ctb_abs * 400))
    else:
        investment_intensity = 50

    # Consistency: how many years with data
    years_with_data = len([r for r in rows if _compute_ctb_pct(r) is not None])
    consistency = min(100, round(years_with_data * 12))

    components = {
        "allocation_quality": allocation_quality,
        "trend_direction": trend_score,
        "peer_position": peer_score,
        "investment_intensity": investment_intensity,
        "consistency": consistency,
    }

    # Weighted composite
    score = round(
        allocation_quality * 0.25
        + trend_score * 0.20
        + peer_score * 0.25
        + investment_intensity * 0.15
        + consistency * 0.15
    )
    grade = _grade(score)

    if score >= 80:
        interpretation = (
            f"Strong allocation discipline — {ticker} is a top-tier CTB investor in its sector."
        )
    elif score >= 65:
        interpretation = (
            f"Solid allocation discipline with room to increase investment intensity to match "
            f"top-performing peers."
        )
    elif score >= 50:
        interpretation = (
            f"Moderate allocation profile. {ticker} should consider increasing transformation "
            f"investment to remain competitive."
        )
    else:
        interpretation = (
            f"Below-average allocation profile. {ticker} may be under-investing in future "
            f"capabilities relative to sector peers."
        )

    sentiocap_score = {
        "score": score,
        "grade": grade,
        "components": components,
        "interpretation": interpretation,
    }

    # -------------------------------------------------------------------------
    # 9. Return full analysis
    # -------------------------------------------------------------------------
    return {
        "company": {
            "ticker": ticker,
            "name": company_name,
            "sector": sector,
        },
        "latest_year": latest_year,
        "allocation": allocation,
        "trend": trend,
        "peer_comparison": peer_comparison,
        "goldilocks": goldilocks,
        "signals": signals,
        "sentiocap_score": sentiocap_score,
        "cta": (
            "This analysis uses public 10-K/XBRL data only. With internal data, SentioCap agents "
            "can classify every expense line, track individual investments, and generate "
            "board-ready reports. Request a pilot at tyson@sentiocap.com"
        ),
    }

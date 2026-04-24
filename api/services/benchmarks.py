"""
Benchmarks service — sector benchmark lookups and peer comparison.
"""
import logging
from typing import Optional
from supabase import Client

logger = logging.getLogger(__name__)


def get_sector_benchmarks(
    sector: str,
    year: int,
    db: Client,
) -> list[dict]:
    """Fetch sector benchmark data for all L2 categories.

    Returns list of benchmark dicts with l2_category, median_pct, p25_pct, p75_pct, etc.
    Falls back to empty list if no data found.
    """
    if not sector:
        return []

    result = (
        db.table("benchmarks")
        .select("*")
        .eq("sector", sector)
        .eq("year", year)
        .order("l2_category")
        .execute()
    )
    benchmarks = result.data or []

    # If no exact year match, try most recent year
    if not benchmarks:
        fallback = (
            db.table("benchmarks")
            .select("*")
            .eq("sector", sector)
            .order("year", desc=True)
            .limit(24)  # up to 3 years × 8 L2 categories
            .execute()
        )
        benchmarks = fallback.data or []

    return benchmarks


def get_peer_comparison(
    tickers: list[str],
    year: int,
    db: Client,
) -> list[dict]:
    """Fetch SP500 data for specific tickers.

    Returns list of company dicts with ticker, company, revenue, ctb_pct_rev, etc.
    """
    if not tickers:
        return []

    result = (
        db.table("sp500_data")
        .select("*")
        .in_("ticker", tickers)
        .eq("year", year)
        .order("ticker")
        .execute()
    )
    peers = result.data or []

    # If no data for the exact year, try the most recent available per ticker
    if not peers:
        fallback = (
            db.table("sp500_data")
            .select("*")
            .in_("ticker", tickers)
            .order("year", desc=True)
            .execute()
        )
        # Keep only the most recent row per ticker
        seen: set[str] = set()
        peers = []
        for row in (fallback.data or []):
            t = row.get("ticker", "")
            if t not in seen:
                seen.add(t)
                peers.append(row)

    return peers


def compute_sector_benchmarks_from_sp500(
    sector: str,
    year: int,
    db: Client,
) -> list[dict]:
    """Derive benchmark stats from SP500 data for a sector/year.

    This is used to refresh the benchmarks table from raw SP500 data.
    Returns list of benchmark dicts (not yet inserted into DB).
    """
    sp_result = (
        db.table("sp500_data")
        .select("ticker, ctb_pct_rev")
        .eq("sector", sector)
        .eq("year", year)
        .execute()
    )
    rows = sp_result.data or []
    if not rows:
        return []

    ctb_values = sorted(r["ctb_pct_rev"] for r in rows if r.get("ctb_pct_rev") is not None)
    if not ctb_values:
        return []

    n = len(ctb_values)
    median = _percentile(ctb_values, 50)
    p25 = _percentile(ctb_values, 25)
    p75 = _percentile(ctb_values, 75)
    mean = sum(ctb_values) / n

    # CTB-GRW gets the bulk allocation; distribute heuristically
    # (real implementation would use more granular XBRL data)
    return [
        {
            "sector": sector,
            "year": year,
            "l2_category": "CTB-GRW",
            "median_pct": round(median * 0.4, 4),
            "p25_pct": round(p25 * 0.4, 4),
            "p75_pct": round(p75 * 0.4, 4),
            "mean_pct": round(mean * 0.4, 4),
            "n_companies": n,
        }
    ]


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Compute a percentile from a pre-sorted list."""
    if not sorted_values:
        return 0.0
    k = (len(sorted_values) - 1) * pct / 100
    f = int(k)
    c = f + 1
    if c >= len(sorted_values):
        return sorted_values[-1]
    return sorted_values[f] + (sorted_values[c] - sorted_values[f]) * (k - f)

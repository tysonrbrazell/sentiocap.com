"""
Upload service — parse CSV and XLSX files into structured row dicts.
"""
import io
import logging
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

MONTH_FIELDS = ["jan", "feb", "mar", "apr", "may", "jun",
                "jul", "aug", "sep", "oct", "nov", "dec"]


def _clean_amount(val) -> float:
    """Convert a cell value to a float, stripping currency symbols and commas."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("$", "").replace(" ", ""))
    except (ValueError, TypeError):
        return 0.0


def parse_upload_file(
    contents: bytes,
    filename: str,
    column_map: dict[str, Optional[str]],
) -> tuple[list[dict], list[str]]:
    """Parse CSV or XLSX file bytes.

    Args:
        contents: raw file bytes
        filename: original filename (used to detect format)
        column_map: mapping of field names → source column names
                    keys: description, cost_center, gl_account,
                          jan…dec (monthly), annual

    Returns:
        (rows, detected_columns)
        rows: list of dicts with source_description, source_cost_center,
              source_gl_account, jan…dec, annual_total
        detected_columns: list of column names found in the file
    """
    filename_lower = filename.lower()
    try:
        if filename_lower.endswith(".xlsx") or filename_lower.endswith(".xls"):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            # Try common encodings
            for enc in ("utf-8", "latin-1", "cp1252"):
                try:
                    df = pd.read_csv(io.BytesIO(contents), encoding=enc)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValueError("Could not decode file with known encodings")
    except Exception as e:
        logger.error(f"Failed to parse upload file: {e}")
        raise

    # Normalize column names: strip whitespace
    df.columns = [str(c).strip() for c in df.columns]
    detected_columns = list(df.columns)

    desc_col = column_map.get("description")
    cc_col = column_map.get("cost_center")
    gl_col = column_map.get("gl_account")
    annual_col = column_map.get("annual")

    rows = []
    for _, row in df.iterrows():
        # Required: description
        if desc_col and desc_col in df.columns:
            description = str(row[desc_col]) if not pd.isna(row[desc_col]) else ""
        else:
            # Try to auto-detect a description-like column
            description = str(row.iloc[0]) if not row.empty else ""

        if not description or description.lower() in ("nan", "none", ""):
            continue

        cost_center = None
        if cc_col and cc_col in df.columns:
            v = row[cc_col]
            cost_center = str(v) if not pd.isna(v) else None

        gl_account = None
        if gl_col and gl_col in df.columns:
            v = row[gl_col]
            gl_account = str(v) if not pd.isna(v) else None

        # Monthly amounts
        monthly: dict[str, float] = {}
        for month in MONTH_FIELDS:
            col_key = column_map.get(month)
            if col_key and col_key in df.columns:
                monthly[month] = _clean_amount(row[col_key])
            else:
                monthly[month] = 0.0

        # Annual total
        if annual_col and annual_col in df.columns:
            annual_total = _clean_amount(row[annual_col])
            # If no monthly breakdown provided, spread evenly
            if sum(monthly.values()) == 0 and annual_total > 0:
                per_month = annual_total / 12
                monthly = {m: per_month for m in MONTH_FIELDS}
        else:
            annual_total = sum(monthly.values())

        rows.append({
            "source_description": description,
            "source_cost_center": cost_center,
            "source_gl_account": gl_account,
            **monthly,
            "annual_total": annual_total,
        })

    return rows, detected_columns


def map_columns(df_columns: list[str]) -> dict[str, Optional[str]]:
    """Auto-detect column mappings from a list of column names.

    Applies fuzzy heuristics to match common column name patterns.
    Returns a column_map dict suitable for parse_upload_file().
    """
    columns_lower = {c.lower(): c for c in df_columns}
    result: dict[str, Optional[str]] = {k: None for k in ["description", "cost_center", "gl_account", "annual"] + MONTH_FIELDS}

    # Description hints
    for hint in ("description", "desc", "expense", "gl description", "account name", "line item", "name"):
        if hint in columns_lower:
            result["description"] = columns_lower[hint]
            break

    # Cost center
    for hint in ("cost center", "costcenter", "cost_center", "cc", "department"):
        if hint in columns_lower:
            result["cost_center"] = columns_lower[hint]
            break

    # GL account
    for hint in ("gl account", "glaccount", "gl_account", "account", "account code", "gl code"):
        if hint in columns_lower:
            result["gl_account"] = columns_lower[hint]
            break

    # Monthly columns — try common patterns
    month_map = {
        "jan": ["jan", "january", "jan amount", "m1"],
        "feb": ["feb", "february", "feb amount", "m2"],
        "mar": ["mar", "march", "mar amount", "m3"],
        "apr": ["apr", "april", "apr amount", "m4"],
        "may": ["may", "may amount", "m5"],
        "jun": ["jun", "june", "jun amount", "m6"],
        "jul": ["jul", "july", "jul amount", "m7"],
        "aug": ["aug", "august", "aug amount", "m8"],
        "sep": ["sep", "september", "sept", "sep amount", "m9"],
        "oct": ["oct", "october", "oct amount", "m10"],
        "nov": ["nov", "november", "nov amount", "m11"],
        "dec": ["dec", "december", "dec amount", "m12"],
    }
    for month, hints in month_map.items():
        for hint in hints:
            if hint in columns_lower:
                result[month] = columns_lower[hint]
                break

    # Annual total
    for hint in ("annual", "total", "annual total", "full year", "yearly"):
        if hint in columns_lower:
            result["annual"] = columns_lower[hint]
            break

    return result

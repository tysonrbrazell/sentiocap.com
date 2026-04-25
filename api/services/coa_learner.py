"""
Chart of Accounts (CoA) Learning Engine — the intelligence layer that makes
Scout smarter about a company's GL structure over time.

Each time a trial balance or GL export is uploaded, CoALearner:
  1. Detects the account code structure (delimiter, segments, ERP fingerprint)
  2. Identifies expense accounts using GAAP/IFRS heuristics
  3. Classifies them using the SentioCap taxonomy (with memory + fuzzy + AI)
  4. Persists the learned chart so future uploads skip the AI step for known accounts
  5. Detects anomalies when amounts deviate from the learned typical
"""
from __future__ import annotations

import json
import logging
import re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-3-5-sonnet-20241022"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

EXPENSE_KEYWORDS = {
    "salary", "salaries", "wage", "wages", "payroll", "compensation",
    "bonus", "benefits", "insurance", "rent", "lease", "utilities",
    "software", "saas", "license", "subscription", "hosting", "cloud",
    "aws", "azure", "gcp", "server", "hardware", "depreciation",
    "amortization", "travel", "entertainment", "consulting", "contractor",
    "professional", "service", "maintenance", "support", "helpdesk",
    "telecom", "internet", "marketing", "advertising", "training",
    "development", "recruiting", "hr", "human", "resources", "office",
    "supplies", "security", "compliance", "audit", "legal", "it",
    "infrastructure", "network", "data", "analytics", "research",
    "cost", "expense", "expenditure", "spending",
}

REVENUE_KEYWORDS = {
    "revenue", "income", "sales", "fee", "fees", "management fee",
    "subscription revenue", "service revenue", "interest income",
}

ASSET_KEYWORDS = {
    "asset", "property", "equipment", "furniture", "vehicle",
    "investment", "receivable", "cash", "bank", "prepaid",
}

LIABILITY_KEYWORDS = {
    "liability", "payable", "debt", "loan", "mortgage", "accrued",
    "deferred", "obligation",
}

# ERP fingerprints
ERP_PATTERNS = {
    "sap": re.compile(r'^\d{10}$'),                         # 10-digit numeric
    "oracle": re.compile(r'^\d{3,5}-\d{2,5}(-\d{2,5})+$'), # dash-separated segments
    "workday": re.compile(r'^[A-Z]{2,4}_\d+$'),             # letters_digits worktags
    "quickbooks": re.compile(r'^\d{4}$'),                   # 4-digit simple
    "netsuite": re.compile(r'^\d{4,5}$'),                   # 4-5 digit simple
}

ANOMALY_THRESHOLD = 0.30  # flag if amount deviates >30% from typical


# ---------------------------------------------------------------------------
# CoALearner
# ---------------------------------------------------------------------------

class CoALearner:
    """Learns a company's GL structure from uploaded data."""

    def __init__(self, org_id: str, supabase_client, memory=None):
        self.org_id = org_id
        self.db = supabase_client
        self.memory = memory
        self.client = Anthropic()

    # =========================================================================
    # Primary entry point
    # =========================================================================

    async def analyze_upload(self, rows: list[dict]) -> dict:
        """Analyze an uploaded trial balance or GL export.

        First upload: detect structure, parse segments, classify accounts.
        Subsequent uploads: recognize known accounts, flag new ones, update amounts.

        rows: list of {account_code, account_name, amount, period?, ...}
        Returns: CoAAnalysis-compatible dict
        """
        if not rows:
            return self._empty_analysis()

        account_codes = [r.get("account_code", "") for r in rows if r.get("account_code")]

        # 1. Detect or load structure
        structure = await self._get_or_detect_structure(account_codes)

        # 2. Load known accounts for this org
        known_accounts = await self._load_known_accounts()
        known_by_code = {a["account_code"]: a for a in known_accounts}

        # 3. Parse + enrich each row
        enriched: list[dict] = []
        for row in rows:
            code = str(row.get("account_code", "")).strip()
            name = str(row.get("account_name", "")).strip()
            amount = _parse_float(row.get("amount", 0))

            if not code and not name:
                continue

            segments = await self.parse_account_code(code, structure)
            is_expense = _is_expense_account(code, name, amount, structure)
            account_type = _detect_account_type(code, name, amount, structure)

            enriched.append({
                "account_code": code,
                "account_name": name,
                "amount": amount,
                "segments": segments,
                "is_expense": is_expense,
                "account_type": account_type,
                "is_known": code in known_by_code,
                "known_data": known_by_code.get(code),
            })

        # 4. Classify expense accounts
        expense_accounts = [a for a in enriched if a["is_expense"]]
        classified = await self.classify_accounts(expense_accounts)

        # 5. Detect hierarchy
        hierarchy = await self.detect_hierarchy(enriched)

        # 6. Persist learning
        await self.learn_from_upload(enriched)

        # 7. Detect anomalies
        anomalies = _detect_anomalies(enriched, known_by_code)

        # 8. Build summary
        new_accounts = [a for a in enriched if not a["is_known"]]
        classified_count = sum(1 for a in classified if a.get("classified_l2"))

        return {
            "structure": structure,
            "total_accounts": len(enriched),
            "expense_accounts": len(expense_accounts),
            "classified_accounts": classified_count,
            "new_accounts": len(new_accounts),
            "anomalies": anomalies,
            "accounts": classified,
            "hierarchy": hierarchy,
        }

    # =========================================================================
    # Structure detection
    # =========================================================================

    async def detect_structure(self, account_codes: list[str]) -> dict:
        """Detect the account code structure from a sample of codes."""
        if not account_codes:
            return self._empty_structure()

        # Sample up to 200 codes for analysis
        sample = [c for c in account_codes if c][:200]

        # --- Detect delimiter ---
        delimiter_counts: Counter = Counter()
        for code in sample:
            for delim in ("-", ".", "/"):
                if delim in code:
                    delimiter_counts[delim] += 1

        total = len(sample)
        dominant_delim = ""
        if delimiter_counts:
            best_delim, best_count = delimiter_counts.most_common(1)[0]
            if best_count / total >= 0.5:
                dominant_delim = best_delim

        # --- Detect segments ---
        if dominant_delim:
            segment_counts = Counter(len(c.split(dominant_delim)) for c in sample)
            num_segments = segment_counts.most_common(1)[0][0]
        else:
            num_segments = 1

        # --- Segment definitions ---
        segment_definitions = []
        if dominant_delim and num_segments > 1:
            # Analyze each position
            positions: list[list[str]] = [[] for _ in range(num_segments)]
            for code in sample:
                parts = code.split(dominant_delim)
                for i, part in enumerate(parts[:num_segments]):
                    positions[i].append(part)

            for i, parts in enumerate(positions):
                avg_len = sum(len(p) for p in parts) / len(parts) if parts else 0
                is_numeric = all(p.isdigit() for p in parts if p)
                seg_type = "expense_type" if i == 0 else ("cost_center" if i == 1 else "sub_account")
                segment_definitions.append({
                    "position": i,
                    "name": seg_type,
                    "avg_length": round(avg_len, 1),
                    "is_numeric": is_numeric,
                    "type": seg_type,
                    "examples": list(set(parts[:3])),
                })
        else:
            # Single segment — just note the length
            avg_len = sum(len(c) for c in sample) / len(sample) if sample else 0
            segment_definitions.append({
                "position": 0,
                "name": "account_code",
                "avg_length": round(avg_len, 1),
                "is_numeric": all(c.isdigit() for c in sample if c),
                "type": "account_code",
                "examples": list(set(sample[:3])),
            })

        # --- ERP detection ---
        detected_erp = "unknown"
        erp_confidence = 0.4
        for erp_name, pattern in ERP_PATTERNS.items():
            matches = sum(1 for c in sample if pattern.match(c))
            if matches / total >= 0.7:
                detected_erp = erp_name
                erp_confidence = round(matches / total, 2)
                break

        # Handle Workday: worktags often contain letters
        if detected_erp == "unknown":
            has_letters = sum(1 for c in sample if any(ch.isalpha() for ch in c))
            if has_letters / total >= 0.5:
                detected_erp = "workday"
                erp_confidence = 0.6

        # --- Range detection ---
        numeric_codes = []
        for c in sample:
            root = c.split(dominant_delim)[0] if dominant_delim else c
            try:
                numeric_codes.append(int(root))
            except ValueError:
                pass

        expense_range_start = None
        expense_range_end = None
        revenue_range_start = None
        revenue_range_end = None

        if numeric_codes:
            # Standard US GAAP ranges
            expense_nums = [n for n in numeric_codes if 5000 <= n <= 9999]
            revenue_nums = [n for n in numeric_codes if 4000 <= n <= 4999]
            if expense_nums:
                expense_range_start = str(min(expense_nums))
                expense_range_end = str(max(expense_nums))
            if revenue_nums:
                revenue_range_start = str(min(revenue_nums))
                revenue_range_end = str(max(revenue_nums))

        return {
            "delimiter": dominant_delim,
            "num_segments": num_segments,
            "segment_definitions": segment_definitions,
            "expense_range_start": expense_range_start,
            "expense_range_end": expense_range_end,
            "revenue_range_start": revenue_range_start,
            "revenue_range_end": revenue_range_end,
            "detected_erp": detected_erp,
            "detection_confidence": erp_confidence,
            "samples_analyzed": total,
        }

    async def _get_or_detect_structure(self, account_codes: list[str]) -> dict:
        """Load existing structure from DB or detect and save a new one."""
        try:
            res = (
                self.db.table("coa_structure")
                .select("*")
                .eq("org_id", self.org_id)
                .limit(1)
                .execute()
            )
            if res.data:
                existing = res.data[0]
                # Update samples_analyzed count
                new_count = (existing.get("samples_analyzed") or 0) + len(account_codes)
                self.db.table("coa_structure").update({
                    "samples_analyzed": new_count,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }).eq("id", existing["id"]).execute()
                return existing
        except Exception as e:
            logger.warning(f"_get_or_detect_structure load failed: {e}")

        # First time — detect and save
        structure = await self.detect_structure(account_codes)
        try:
            self.db.table("coa_structure").insert({
                "org_id": self.org_id,
                "delimiter": structure["delimiter"],
                "num_segments": structure["num_segments"],
                "segment_definitions": structure["segment_definitions"],
                "expense_range_start": structure["expense_range_start"],
                "expense_range_end": structure["expense_range_end"],
                "revenue_range_start": structure["revenue_range_start"],
                "revenue_range_end": structure["revenue_range_end"],
                "detected_erp": structure["detected_erp"],
                "detection_confidence": structure["detection_confidence"],
                "samples_analyzed": structure["samples_analyzed"],
            }).execute()
        except Exception as e:
            logger.warning(f"_get_or_detect_structure save failed: {e}")

        return structure

    # =========================================================================
    # Account code parsing
    # =========================================================================

    async def parse_account_code(self, code: str, structure: dict) -> dict:
        """Parse an account code into segments using the learned structure."""
        if not code:
            return {}

        delimiter = structure.get("delimiter", "")
        seg_defs = structure.get("segment_definitions", [])

        if delimiter and delimiter in code:
            parts = code.split(delimiter)
        else:
            parts = [code]

        result: dict[str, Optional[str]] = {
            "category": None,
            "cost_center": None,
            "sub_account": None,
            "location": None,
        }

        for i, part in enumerate(parts):
            if i < len(seg_defs):
                seg_name = seg_defs[i].get("name", "")
                if i == 0 or seg_name == "expense_type" or seg_name == "account_code":
                    result["category"] = part
                elif seg_name == "cost_center" or i == 1:
                    result["cost_center"] = part
                elif seg_name == "sub_account" or i == 2:
                    result["sub_account"] = part
                elif seg_name == "location" or i == 3:
                    result["location"] = part
            else:
                # More segments than defined — append to sub_account
                if result["sub_account"]:
                    result["sub_account"] += f"{delimiter}{part}"
                else:
                    result["sub_account"] = part

        return result

    # =========================================================================
    # Expense account detection
    # =========================================================================

    async def detect_expense_accounts(self, accounts: list[dict]) -> list[dict]:
        """Determine which accounts are expense accounts."""
        result = []
        for acct in accounts:
            code = acct.get("account_code", "")
            name = acct.get("account_name", "")
            amount = _parse_float(acct.get("amount", 0))
            structure = acct.get("_structure", {})
            is_expense = _is_expense_account(code, name, amount, structure)
            result.append({**acct, "is_expense": is_expense})
        return result

    # =========================================================================
    # Classification
    # =========================================================================

    async def classify_accounts(self, accounts: list[dict]) -> list[dict]:
        """Classify all expense accounts into the SentioCap taxonomy.

        Priority:
        1. Previously known account (DB lookup by code)
        2. Firm glossary (memory)
        3. Network intelligence
        4. Fuzzy / keyword match via existing confirmed classifications
        5. AI classification (Claude)
        """
        if not accounts:
            return []

        # Load known accounts to check against
        known_accounts = await self._load_known_accounts()
        known_by_code = {a["account_code"]: a for a in known_accounts}

        # Load firm glossary for name-based lookup
        glossary = {}
        if self.memory:
            try:
                gl = await self.memory.get_firm_glossary()
                glossary = {g["firm_term"].lower(): g for g in gl}
            except Exception:
                pass

        results = []
        # Batch accounts that need AI classification
        needs_ai: list[dict] = []

        for acct in accounts:
            code = acct.get("account_code", "")
            name = acct.get("account_name", "")
            name_lower = name.lower().strip()

            # 1. Exact code match in known accounts
            if code and code in known_by_code:
                known = known_by_code[code]
                results.append({
                    **acct,
                    "classified_l1": known.get("classified_l1"),
                    "classified_l2": known.get("classified_l2"),
                    "classified_l3": known.get("classified_l3"),
                    "classified_l4": known.get("classified_l4"),
                    "classification_confidence": known.get("classification_confidence", 0.9),
                    "classification_source": "known_account",
                })
                continue

            # 2. Firm glossary lookup
            if name_lower in glossary:
                entry = glossary[name_lower]
                results.append({
                    **acct,
                    "classified_l1": entry.get("mapped_l1"),
                    "classified_l2": entry.get("mapped_l2"),
                    "classified_l3": entry.get("mapped_l3"),
                    "classified_l4": entry.get("mapped_l4"),
                    "classification_confidence": entry.get("confidence", 0.85),
                    "classification_source": "glossary",
                })
                continue

            # 3. Network intelligence query
            network_result = None
            if self.memory:
                try:
                    network_result = await self.memory.query_network(
                        "gl_account_classification", name_lower
                    )
                except Exception:
                    pass

            if network_result and network_result.get("data"):
                data = network_result["data"]
                results.append({
                    **acct,
                    "classified_l1": data.get("l1"),
                    "classified_l2": data.get("l2"),
                    "classified_l3": data.get("l3"),
                    "classified_l4": data.get("l4"),
                    "classification_confidence": float(network_result.get("confidence", 0.75)),
                    "classification_source": "network",
                })
                continue

            # Queue for AI
            needs_ai.append(acct)

        # AI classify in batches
        if needs_ai:
            ai_results = await self._ai_classify_accounts(needs_ai)
            results.extend(ai_results)

        return results

    async def _ai_classify_accounts(self, accounts: list[dict]) -> list[dict]:
        """Use Claude to classify a batch of GL accounts."""
        if not accounts:
            return []

        # Build firm context from memory
        firm_context = ""
        if self.memory:
            try:
                firm_context = await self.memory.build_classification_context()
            except Exception:
                pass

        system_prompt = """You are an expert IT financial analyst classifying GL accounts into the SentioCap taxonomy.

## Taxonomy

L1: RTB (Run The Business) | CTB (Change The Business)

L2 Categories:
- L2-INF: Infrastructure & Platforms
- L2-APP: Applications & Software
- L2-DAT: Data & Analytics
- L2-SEC: Security & Compliance
- L2-OPS: IT Operations & Support
- L2-PEO: People & Talent
- L2-INO: Innovation & R&D
- L2-PRO: Process & Transformation

L3 Domains: L3-CLD, L3-NET, L3-SFT, L3-DEV, L3-ANL, L3-HCM, L3-CYB, L3-CHG

L4 Codes: L4-CLD-001 (Cloud Compute), L4-CLD-002 (Cloud Storage), L4-SFT-001 (SaaS),
L4-SFT-002 (On-Prem), L4-DEV-001 (App Dev), L4-DEV-002 (DevOps), L4-ANL-001 (BI),
L4-ANL-002 (Data Eng), L4-HCM-001 (IT Staff), L4-HCM-002 (Contractor), L4-HCM-003 (Training),
L4-CYB-001 (Security SW), L4-CYB-002 (PenTest), L4-CHG-001 (Change Mgmt), L4-CHG-002 (Process)

Rules:
- Salary/headcount → RTB/L2-PEO/L3-HCM/L4-HCM-001
- SaaS subscriptions for existing tools → RTB/L2-APP/L3-SFT/L4-SFT-001
- New software development → CTB/L2-APP/L3-DEV/L4-DEV-001
- Cloud hosting (existing) → RTB/L2-INF/L3-CLD/L4-CLD-001
- Security tools → RTB/L2-SEC/L3-CYB/L4-CYB-001

Return ONLY a JSON array in the same order as input:
[{"account_code": "...", "l1": "RTB", "l2": "L2-INF", "l3": "L3-CLD", "l4": "L4-CLD-001", "confidence": 0.85, "reasoning": "..."}]"""

        BATCH = 25
        results = []

        for i in range(0, len(accounts), BATCH):
            batch = accounts[i:i + BATCH]
            items = [
                {"account_code": a.get("account_code", ""), "account_name": a.get("account_name", ""), "amount": a.get("amount", 0)}
                for a in batch
            ]

            user_msg = f"""Classify these GL accounts:

{json.dumps(items, indent=2)}

{firm_context}

Return ONLY a JSON array."""

            try:
                response = self.client.messages.create(
                    model=MODEL,
                    max_tokens=2048,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_msg}],
                )
                raw = response.content[0].text.strip()
                if raw.startswith("```"):
                    parts = raw.split("```")
                    raw = parts[1] if len(parts) > 1 else raw
                    if raw.startswith("json"):
                        raw = raw[4:]
                parsed = json.loads(raw.strip())
            except Exception as e:
                logger.warning(f"AI classification batch failed: {e}")
                parsed = []

            # Map results back
            parsed_by_code = {p.get("account_code", ""): p for p in parsed}
            for acct in batch:
                code = acct.get("account_code", "")
                p = parsed_by_code.get(code, {})
                results.append({
                    **acct,
                    "classified_l1": p.get("l1"),
                    "classified_l2": p.get("l2"),
                    "classified_l3": p.get("l3"),
                    "classified_l4": p.get("l4"),
                    "classification_confidence": float(p.get("confidence", 0.5)),
                    "classification_source": "ai",
                    "reasoning": p.get("reasoning"),
                })

                # Contribute to network intelligence
                if self.memory and p.get("l2") and float(p.get("confidence", 0)) >= 0.7:
                    try:
                        name_lower = acct.get("account_name", "").lower().strip()
                        await self.memory.contribute_to_network(
                            "gl_account_classification",
                            name_lower,
                            {
                                "l1": p.get("l1"),
                                "l2": p.get("l2"),
                                "l3": p.get("l3"),
                                "l4": p.get("l4"),
                            },
                        )
                    except Exception:
                        pass

        return results

    # =========================================================================
    # Hierarchy detection
    # =========================================================================

    async def detect_hierarchy(self, accounts: list[dict]) -> dict:
        """Detect if the CoA has a hierarchical structure."""
        codes = [a.get("account_code", "") for a in accounts if a.get("account_code")]
        names = [a.get("account_name", "") for a in accounts if a.get("account_name")]

        # Detect summary/header rows (accounts with 'Total' in name)
        totals = [n for n in names if "total" in n.lower()]

        # Detect parent-child by numeric proximity
        # e.g. 5000 is parent of 5010, 5020, 5030
        parents: dict[str, list[str]] = {}
        numeric_codes = []
        for code in codes:
            try:
                root = int(code.split("-")[0].split(".")[0])
                numeric_codes.append((root, code))
            except ValueError:
                pass

        numeric_codes.sort()
        for i, (num, code) in enumerate(numeric_codes):
            # Round down to nearest 100 to find potential parent
            potential_parent_num = (num // 100) * 100
            potential_parent_code = str(potential_parent_num)
            # Check if this parent exists in our codes
            actual_codes = {c for _, c in numeric_codes}
            if potential_parent_code in actual_codes and potential_parent_code != code:
                parents.setdefault(potential_parent_code, []).append(code)

        return {
            "has_totals": len(totals) > 0,
            "total_rows": totals[:5],
            "detected_parents": len(parents),
            "parent_map": {k: v for k, v in list(parents.items())[:10]},  # sample
        }

    # =========================================================================
    # Learning + persistence
    # =========================================================================

    async def learn_from_upload(self, rows: list[dict]) -> None:
        """Update the CoA after each upload."""
        if not rows:
            return

        known_accounts = await self._load_known_accounts()
        known_by_code = {a["account_code"]: a for a in known_accounts}

        now = datetime.now(timezone.utc).isoformat()
        insert_rows = []
        update_ops = []

        for row in rows:
            code = str(row.get("account_code", "")).strip()
            name = str(row.get("account_name", "")).strip()
            if not code:
                continue

            amount = _parse_float(row.get("amount", 0))
            segments = row.get("segments", {}) or {}

            if code in known_by_code:
                existing = known_by_code[code]
                # Update rolling average for typical monthly amount
                times_seen = (existing.get("times_seen") or 1)
                typical = existing.get("typical_monthly_amount")
                if typical is None:
                    new_typical = amount
                else:
                    new_typical = (float(typical) * times_seen + amount) / (times_seen + 1)

                update_ops.append({
                    "id": existing["id"],
                    "times_seen": times_seen + 1,
                    "last_seen_at": now,
                    "typical_monthly_amount": round(new_typical, 2),
                    "updated_at": now,
                })
            else:
                # New account
                classified = row.get("classified_l1") is not None
                insert_rows.append({
                    "org_id": self.org_id,
                    "account_code": code,
                    "account_name": name,
                    "account_name_normalized": name.lower().strip(),
                    "segment_category": segments.get("category"),
                    "segment_cost_center": segments.get("cost_center"),
                    "segment_sub": segments.get("sub_account"),
                    "segment_location": segments.get("location"),
                    "classified_l1": row.get("classified_l1"),
                    "classified_l2": row.get("classified_l2"),
                    "classified_l3": row.get("classified_l3"),
                    "classified_l4": row.get("classified_l4"),
                    "classification_confidence": row.get("classification_confidence", 0.5) if classified else 0.5,
                    "classification_source": row.get("classification_source", "ai"),
                    "account_type": row.get("account_type", "expense"),
                    "is_expense": row.get("is_expense", False),
                    "typical_monthly_amount": amount,
                    "times_seen": 1,
                    "last_seen_at": now,
                })

        # Batch insert new accounts
        if insert_rows:
            for i in range(0, len(insert_rows), 50):
                try:
                    self.db.table("chart_of_accounts").insert(insert_rows[i:i + 50]).execute()
                except Exception as e:
                    logger.warning(f"CoA insert batch failed: {e}")

        # Batch update known accounts
        for op in update_ops:
            try:
                acct_id = op.pop("id")
                self.db.table("chart_of_accounts").update(op).eq("id", acct_id).execute()
            except Exception as e:
                logger.warning(f"CoA update failed: {e}")

    # =========================================================================
    # Smart column detection
    # =========================================================================

    async def get_smart_columns(self, headers: list[str], sample_rows: list) -> dict:
        """Auto-detect what each column contains in an uploaded file."""
        result: dict[str, str] = {}
        headers_lower = {h.lower().strip(): h for h in headers}

        # --- Header-based detection ---
        account_aliases = {
            "acct", "account", "account #", "gl account", "account code",
            "gl code", "account number", "acct no", "account no",
        }
        name_aliases = {
            "description", "account name", "account description", "desc",
            "gl description", "name", "line item",
        }
        amount_aliases = {
            "balance", "amount", "net", "total", "ytd", "annual",
            "full year", "yearly",
        }
        debit_aliases = {"debit", "dr", "debit amount"}
        credit_aliases = {"credit", "cr", "credit amount"}
        period_aliases = {
            "period", "month", "date", "fiscal period", "fiscal month",
            "accounting period",
        }
        dept_aliases = {
            "dept", "department", "cost center", "cc", "business unit",
            "bu", "division",
        }

        for h_lower, h_orig in headers_lower.items():
            if h_lower in account_aliases:
                result[h_orig] = "account_code"
            elif h_lower in name_aliases:
                result[h_orig] = "account_name"
            elif h_lower in amount_aliases:
                result[h_orig] = "amount"
            elif h_lower in debit_aliases:
                result[h_orig] = "debit"
            elif h_lower in credit_aliases:
                result[h_orig] = "credit"
            elif h_lower in period_aliases:
                result[h_orig] = "period"
            elif h_lower in dept_aliases:
                result[h_orig] = "department"

        # --- Data-pattern-based detection for remaining columns ---
        untyped = [h for h in headers if h not in result]
        if untyped and sample_rows:
            for h in untyped:
                col_idx = headers.index(h)
                values = []
                for row in sample_rows[:20]:
                    if isinstance(row, (list, tuple)) and col_idx < len(row):
                        values.append(str(row[col_idx]).strip())
                    elif isinstance(row, dict):
                        values.append(str(row.get(h, "")).strip())

                if not values:
                    continue

                detected = _detect_column_type_by_data(h, values)
                if detected:
                    result[h] = detected

        return result

    # =========================================================================
    # Summary generation
    # =========================================================================

    async def generate_upload_summary(self) -> dict:
        """Generate a summary of what Scout has learned about this org's CoA."""
        # Load structure
        structure_res = (
            self.db.table("coa_structure")
            .select("*")
            .eq("org_id", self.org_id)
            .limit(1)
            .execute()
        )
        structure = (structure_res.data or [{}])[0]

        # Account stats
        accounts_res = (
            self.db.table("chart_of_accounts")
            .select("account_code, classified_l2, classification_confidence, is_expense, typical_monthly_amount")
            .eq("org_id", self.org_id)
            .execute()
        )
        accounts = accounts_res.data or []

        total = len(accounts)
        expense_accounts = [a for a in accounts if a.get("is_expense")]
        classified = [a for a in expense_accounts if a.get("classified_l2")]

        # Top categories by typical amount
        l2_totals: dict[str, float] = {}
        for a in classified:
            l2 = a.get("classified_l2", "")
            amt = float(a.get("typical_monthly_amount") or 0)
            l2_totals[l2] = l2_totals.get(l2, 0) + amt

        total_amount = sum(l2_totals.values())
        top_categories = sorted(
            [{"l2": l2, "amount": round(amt, 2), "pct": round(amt / total_amount * 100, 1) if total_amount else 0}
             for l2, amt in l2_totals.items()],
            key=lambda x: x["amount"],
            reverse=True,
        )[:5]

        # Anomalies
        anomaly_count = 0
        try:
            all_accounts = (
                self.db.table("chart_of_accounts")
                .select("typical_monthly_amount, times_seen")
                .eq("org_id", self.org_id)
                .execute()
            )
            # Simple proxy: accounts with high variance (would need time-series for real anomalies)
            anomaly_count = sum(
                1 for a in (all_accounts.data or [])
                if (a.get("times_seen") or 0) >= 2
                and (a.get("typical_monthly_amount") or 0) > 0
            )
        except Exception:
            pass

        erp = structure.get("detected_erp", "unknown")
        delimiter = structure.get("delimiter", "")
        num_segs = structure.get("num_segments", 1)
        structure_desc = f"{num_segs} segment{'s' if num_segs != 1 else ''}"
        if delimiter:
            structure_desc += f", {delimiter!r}-delimited"

        return {
            "detected_erp": erp,
            "structure": structure_desc,
            "total_accounts": total,
            "expense_accounts": len(expense_accounts),
            "classified_accounts": len(classified),
            "classification_coverage": round(len(classified) / len(expense_accounts) * 100, 1) if expense_accounts else 0,
            "top_categories": top_categories,
            "new_accounts_since_last": 0,  # updated by analyze_upload
            "anomalies_detected": anomaly_count,
        }

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _load_known_accounts(self) -> list[dict]:
        """Load all known accounts for this org from DB."""
        try:
            res = (
                self.db.table("chart_of_accounts")
                .select("*")
                .eq("org_id", self.org_id)
                .execute()
            )
            return res.data or []
        except Exception as e:
            logger.warning(f"_load_known_accounts failed: {e}")
            return []

    def _empty_analysis(self) -> dict:
        return {
            "structure": self._empty_structure(),
            "total_accounts": 0,
            "expense_accounts": 0,
            "classified_accounts": 0,
            "new_accounts": 0,
            "anomalies": [],
            "accounts": [],
            "hierarchy": {},
        }

    def _empty_structure(self) -> dict:
        return {
            "delimiter": "",
            "num_segments": 1,
            "segment_definitions": [],
            "expense_range_start": None,
            "expense_range_end": None,
            "revenue_range_start": None,
            "revenue_range_end": None,
            "detected_erp": "unknown",
            "detection_confidence": 0.0,
            "samples_analyzed": 0,
        }


# ---------------------------------------------------------------------------
# Module-level helpers
# ---------------------------------------------------------------------------

def _parse_float(val: Any) -> float:
    """Safely parse a value to float."""
    if val is None:
        return 0.0
    try:
        return float(str(val).replace(",", "").replace("$", "").strip())
    except (ValueError, TypeError):
        return 0.0


def _is_expense_account(code: str, name: str, amount: float, structure: dict) -> bool:
    """Heuristic: is this a GL account Scout should classify?"""
    name_lower = name.lower()
    code_root = code.split("-")[0].split(".")[0] if code else ""

    # 1. Revenue/asset/liability keywords → not expense
    for kw in REVENUE_KEYWORDS | ASSET_KEYWORDS | LIABILITY_KEYWORDS:
        if kw in name_lower and kw not in EXPENSE_KEYWORDS:
            return False

    # 2. Expense keywords in name
    for kw in EXPENSE_KEYWORDS:
        if kw in name_lower:
            return True

    # 3. Account code range heuristic (US GAAP: 5000-9999 = expense)
    expense_start = structure.get("expense_range_start")
    expense_end = structure.get("expense_range_end")
    if code_root.isdigit():
        num = int(code_root)
        if expense_start and expense_end:
            if int(expense_start) <= num <= int(expense_end):
                return True
        elif 5000 <= num <= 9999:
            return True

    # 4. Debit balance (positive amount in standard expense accounts)
    if amount > 0 and code_root.isdigit():
        num = int(code_root)
        if 4000 <= num <= 9999:
            return True

    return False


def _detect_account_type(code: str, name: str, amount: float, structure: dict) -> str:
    """Classify the broad account type."""
    name_lower = name.lower()
    code_root = code.split("-")[0].split(".")[0] if code else ""

    for kw in REVENUE_KEYWORDS:
        if kw in name_lower:
            return "revenue"
    for kw in ASSET_KEYWORDS:
        if kw in name_lower:
            return "asset"
    for kw in LIABILITY_KEYWORDS:
        if kw in name_lower:
            return "liability"
    for kw in EXPENSE_KEYWORDS:
        if kw in name_lower:
            return "expense"

    if code_root.isdigit():
        num = int(code_root)
        if 1000 <= num <= 1999:
            return "asset"
        elif 2000 <= num <= 2999:
            return "liability"
        elif num == 3000 or 3000 <= num <= 3999:
            return "equity"
        elif 4000 <= num <= 4999:
            return "revenue"
        elif 5000 <= num <= 9999:
            return "expense"

    return "unknown"


def _detect_anomalies(enriched: list[dict], known_by_code: dict) -> list[dict]:
    """Flag accounts whose current amount deviates >30% from typical."""
    anomalies = []
    for acct in enriched:
        code = acct.get("account_code", "")
        if code not in known_by_code:
            continue
        known = known_by_code[code]
        typical = known.get("typical_monthly_amount")
        current = _parse_float(acct.get("amount", 0))
        if not typical or typical == 0:
            continue
        deviation = abs(current - float(typical)) / float(typical)
        if deviation > ANOMALY_THRESHOLD:
            anomalies.append({
                "account_code": code,
                "account_name": acct.get("account_name", ""),
                "current_amount": current,
                "typical_amount": float(typical),
                "deviation_pct": round(deviation * 100, 1),
                "direction": "over" if current > float(typical) else "under",
            })
    return anomalies


def _detect_column_type_by_data(header: str, values: list[str]) -> Optional[str]:
    """Detect column type from data patterns."""
    non_empty = [v for v in values if v and v.lower() not in ("nan", "none", "")]
    if not non_empty:
        return None

    # Numeric check
    numeric_count = sum(1 for v in non_empty if re.match(r'^-?[\d,.$]+$', v))
    numeric_pct = numeric_count / len(non_empty)

    if numeric_pct >= 0.8:
        # Could be amount or account code
        has_decimal = any("." in v for v in non_empty)
        avg_len = sum(len(v.replace(",", "").replace("$", "")) for v in non_empty) / len(non_empty)
        if avg_len <= 6 and not has_decimal:
            return "account_code"
        return "amount"

    # Date-like check
    date_patterns = [
        re.compile(r'^\d{4}-\d{2}$'),          # YYYY-MM
        re.compile(r'^\d{2}/\d{4}$'),           # MM/YYYY
        re.compile(r'^Q[1-4]-\d{4}$'),          # QX-YYYY
        re.compile(r'^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)', re.IGNORECASE),
    ]
    date_count = sum(1 for v in non_empty if any(p.match(v) for p in date_patterns))
    if date_count / len(non_empty) >= 0.5:
        return "period"

    # Text that looks like an account name (longer strings)
    avg_text_len = sum(len(v) for v in non_empty) / len(non_empty)
    if avg_text_len > 15:
        return "account_name"

    # Short repeating text → department
    unique_pct = len(set(non_empty)) / len(non_empty)
    if unique_pct < 0.3 and avg_text_len < 20:
        return "department"

    return None

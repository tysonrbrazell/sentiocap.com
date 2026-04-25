"""
Fuzzy Matching Engine — the core system that makes sense of messy enterprise data.

Implements a multi-layer matching pipeline:
  Layer 1: Confirmed mappings (instant, 99%)
  Layer 2: Firm glossary lookup (fast, high confidence)
  Layer 3: Exact name match (fast, 95%)
  Layer 4: Fuzzy string match (fast, variable)
  Layer 5: Keyword extraction match (medium, 60-80%)
  Layer 6: AI reasoning via Claude (slower, for ambiguous cases)

Additional signal methods:
  - People overlap (same engineers across systems)
  - Temporal correlation (activity spikes)
"""
from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Optional

from anthropic import Anthropic

logger = logging.getLogger(__name__)

MODEL = "claude-3-5-sonnet-20241022"

# ---------------------------------------------------------------------------
# Common abbreviation expansions
# ---------------------------------------------------------------------------

ABBREVIATIONS: dict[str, str] = {
    "fi": "fixed income",
    "esg": "esg",
    "aiml": "ai",
    "ai/ml": "ai",
    "ml": "machine learning",
    "crm": "crm",
    "erp": "erp",
    "bi": "business intelligence",
    "mkt": "marketing",
    "ops": "operations",
    "infra": "infrastructure",
    "dev": "development",
    "prod": "production",
    "mgmt": "management",
    "svc": "service",
    "svcs": "services",
    "plat": "platform",
    "idx": "index",
    "idxs": "indexes",
    "anl": "analytics",
    "rtb": "run the business",
    "ctb": "change the business",
}

# Suffixes/words to strip during normalization
NOISE_SUFFIXES = [
    "project", "initiative", "program", "phase", "v2", "v3", "v4",
    "2024", "2025", "2026", "fy24", "fy25", "fy26", "q1", "q2", "q3", "q4",
    "enhancement", "enhancements", "update", "updates", "implementation",
    "rollout", "launch", "relaunch",
]

# Domain + action keywords to keep
DOMAIN_KEYWORDS = {
    "index", "indexes", "indices", "analytics", "esg", "climate", "risk",
    "portfolio", "trading", "data", "platform", "cloud", "migration",
    "modernization", "infrastructure", "api", "integration", "reporting",
    "dashboard", "engine", "model", "models", "ai", "ml", "automation",
    "digital", "transformation", "optimization", "core", "system",
    "management", "security", "compliance", "identity", "network",
    "operations", "support", "research", "innovation", "service", "services",
    "fixed", "income", "equity", "alternatives", "multi", "asset",
    "client", "customer", "market", "benchmark", "factor", "quant",
    "quantitative", "systematic", "active", "passive",
}

ACTION_KEYWORDS = {
    "migration", "modernization", "launch", "enhancement", "replacement",
    "build", "rebuild", "upgrade", "redesign", "consolidation", "expansion",
    "rollout", "implementation", "development", "replatform", "decommission",
}

STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "for", "to", "in", "on", "at",
    "with", "by", "from", "is", "it", "as", "new", "our", "its",
}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class MatchCandidate:
    target_id: str           # investment ID or RTB category code
    target_name: str         # investment name or L2 category
    target_type: str         # 'investment' or 'rtb_category'
    confidence: float        # 0-1
    match_method: str        # which method produced this match
    reasoning: str           # why this match was suggested
    allocation_pct: float = 100.0  # for split mappings


@dataclass
class MatchResult:
    source_id: str           # ID in external system
    source_name: str         # name in external system
    source_type: str         # 'product', 'project', 'epic', 'cost_center'
    source_system: str       # 'salesforce', 'jira', 'erp'
    candidates: list[MatchCandidate] = field(default_factory=list)
    best_match: Optional[MatchCandidate] = None
    needs_review: bool = True
    match_status: str = "unmatched"  # 'auto_matched', 'needs_review', 'unmatched'


# ---------------------------------------------------------------------------
# FuzzyMatcher
# ---------------------------------------------------------------------------

class FuzzyMatcher:
    """Makes sense of messy enterprise data by matching across systems."""

    def __init__(self, org_id: str, supabase_client, memory=None):
        self.org_id = org_id
        self.db = supabase_client
        self.memory = memory
        self.client = Anthropic()

    # =========================================================================
    # Public API
    # =========================================================================

    async def match_items(self, items: list[dict], source_system: str) -> list[MatchResult]:
        """Match a batch of items from an external system to investments/categories.

        items: list of {id, name, description?, metadata?} from the external system
        source_system: 'salesforce', 'jira', 'erp'

        Returns ranked candidates for each item.
        """
        # 1. Load all investments for this org
        inv_res = (
            self.db.table("investments")
            .select("id, name, l2_category, description, status")
            .eq("org_id", self.org_id)
            .execute()
        )
        investments = inv_res.data or []

        # 2. Load firm glossary from memory (name variants we've learned)
        glossary = await self._load_glossary()

        # 3. Load existing confirmed mappings
        conf_res = (
            self.db.table("connector_mappings")
            .select("source_id, source_system, investment_id, l2_category, source_name")
            .eq("org_id", self.org_id)
            .eq("confirmed", True)
            .execute()
        )
        confirmed: dict[str, dict] = {}
        for row in (conf_res.data or []):
            key = f"{row['source_system']}:{row['source_id']}"
            confirmed[key] = row

        # 4. Match each item through the pipeline
        results = []
        for item in items:
            try:
                result = await self._match_single(
                    item, source_system, investments, glossary, confirmed
                )
                results.append(result)
            except Exception as e:
                logger.error(f"match_single failed for {item.get('id')}: {e}")
                results.append(MatchResult(
                    source_id=item.get("id", ""),
                    source_name=item.get("name", ""),
                    source_type=item.get("type", "product"),
                    source_system=source_system,
                    candidates=[],
                    best_match=None,
                    needs_review=True,
                    match_status="unmatched",
                ))

        return results

    async def auto_match_batch(
        self,
        items: list[dict],
        source_system: str,
        auto_confirm_threshold: float = 0.85,
    ) -> dict:
        """Match a batch and auto-confirm high-confidence matches.

        Returns categorized results with stats.
        """
        results = await self.match_items(items, source_system)

        auto_matched = []
        needs_review = []
        unmatched = []

        for result in results:
            if result.best_match and result.best_match.confidence >= auto_confirm_threshold:
                # Auto-save this confirmed mapping
                await self._save_mapping(result, result.best_match, confirmed=True)
                auto_matched.append(result)
            elif result.best_match and result.best_match.confidence >= 0.5:
                needs_review.append(result)
            else:
                unmatched.append(result)

        total = len(results)
        return {
            "auto_matched": [_result_to_dict(r) for r in auto_matched],
            "needs_review": [_result_to_dict(r) for r in needs_review],
            "unmatched": [_result_to_dict(r) for r in unmatched],
            "stats": {
                "total": total,
                "auto_matched": len(auto_matched),
                "review_count": len(needs_review),
                "unmatched_count": len(unmatched),
                "auto_matched_pct": round(len(auto_matched) / total * 100, 1) if total else 0,
                "review_pct": round(len(needs_review) / total * 100, 1) if total else 0,
                "unmatched_pct": round(len(unmatched) / total * 100, 1) if total else 0,
            },
        }

    async def learn_from_confirmation(
        self,
        source_id: str,
        source_name: str,
        source_system: str,
        target_id: str,
        target_name: str,
        target_type: str = "investment",
        allocation_pct: float = 100.0,
    ) -> None:
        """When a user confirms a match, teach Scout for next time.

        1. Save/update connector_mapping with confirmed=True
        2. Update firm_glossary via memory so this variant is remembered
        3. Look for similar unconfirmed mappings to propagate to
        """
        # 1. Save confirmed mapping
        now = datetime.now(timezone.utc).isoformat()
        existing = (
            self.db.table("connector_mappings")
            .select("id")
            .eq("org_id", self.org_id)
            .eq("source_id", source_id)
            .eq("connector_type", source_system)
            .execute()
        )

        mapping_data = {
            "org_id": self.org_id,
            "connector_type": source_system,
            "source_id": source_id,
            "source_name": source_name,
            "source_type": "product" if source_system == "salesforce" else "project",
            "investment_id": target_id if target_type == "investment" else None,
            "l2_category": target_id if target_type == "rtb_category" else None,
            "mapping_method": "manual",
            "confidence": 1.0,
            "confirmed": True,
            "updated_at": now,
        }

        if existing.data:
            self.db.table("connector_mappings").update(mapping_data).eq(
                "id", existing.data[0]["id"]
            ).execute()
        else:
            mapping_data["id"] = str(uuid.uuid4())
            self.db.table("connector_mappings").insert(mapping_data).execute()

        # 2. Upsert into firm_glossary so future matches recognize this name variant
        if self.memory:
            try:
                await self.memory.record_correction(
                    source_desc=source_name,
                    original={},
                    corrected={"l1": target_type, "l2": target_name},
                )
            except Exception as e:
                logger.warning(f"Glossary update failed: {e}")

        # 3. Find similar unconfirmed mappings and propagate confidence boost
        await self._propagate_learning(source_name, target_id, target_type, source_system)

    # =========================================================================
    # Core matching pipeline
    # =========================================================================

    async def _match_single(
        self,
        item: dict,
        source_system: str,
        investments: list[dict],
        glossary: list[dict],
        confirmed: dict[str, dict],
    ) -> MatchResult:
        """Match a single item through the full pipeline."""
        source_id = item.get("id", "")
        source_name = item.get("name", "")
        source_type = item.get("type", "product" if source_system == "salesforce" else "project")
        source_desc = item.get("description", "")

        result = MatchResult(
            source_id=source_id,
            source_name=source_name,
            source_type=source_type,
            source_system=source_system,
        )

        candidates: list[MatchCandidate] = []

        # ------------------------------------------------------------------
        # Layer 1: Previously confirmed mappings (instant, 99% confidence)
        # ------------------------------------------------------------------
        conf_key = f"{source_system}:{source_id}"
        if conf_key in confirmed:
            conf = confirmed[conf_key]
            target_id = conf.get("investment_id") or conf.get("l2_category", "")
            target_type = "investment" if conf.get("investment_id") else "rtb_category"
            # Look up target name
            target_name = self._resolve_target_name(target_id, target_type, investments)
            candidates.append(MatchCandidate(
                target_id=target_id,
                target_name=target_name,
                target_type=target_type,
                confidence=0.99,
                match_method="confirmed_mapping",
                reasoning="Previously confirmed by a user — highest trust.",
            ))
            # Short-circuit — no need to run further layers
            result.candidates = candidates
            result.best_match = candidates[0]
            result.needs_review = False
            result.match_status = "auto_matched"
            return result

        # ------------------------------------------------------------------
        # Layer 2: Firm glossary lookup (fast, 90% confidence)
        # ------------------------------------------------------------------
        norm_source = self._normalize_name(source_name)
        for entry in glossary:
            term = entry.get("firm_term", "")
            if not term:
                continue
            norm_term = self._normalize_name(term)
            if norm_term == norm_source or norm_term in norm_source or norm_source in norm_term:
                # Glossary hit — map to investment if possible
                mapped_l2 = entry.get("mapped_l2", "")
                # Try to find an investment matching this l2 category
                matched_inv = next(
                    (inv for inv in investments if inv.get("l2_category") == mapped_l2), None
                )
                if matched_inv:
                    candidates.append(MatchCandidate(
                        target_id=matched_inv["id"],
                        target_name=matched_inv["name"],
                        target_type="investment",
                        confidence=0.90,
                        match_method="glossary",
                        reasoning=f"Firm glossary: '{term}' → {mapped_l2}",
                    ))

        # ------------------------------------------------------------------
        # Layer 3: Exact name match (fast, 95% confidence)
        # ------------------------------------------------------------------
        for inv in investments:
            norm_inv = self._normalize_name(inv["name"])
            if norm_inv == norm_source:
                candidates.append(MatchCandidate(
                    target_id=inv["id"],
                    target_name=inv["name"],
                    target_type="investment",
                    confidence=0.95,
                    match_method="exact_name",
                    reasoning=f"Normalized name '{norm_source}' matches exactly.",
                ))

        # ------------------------------------------------------------------
        # Layer 4: Fuzzy string matching (fast, variable confidence)
        # ------------------------------------------------------------------
        for inv in investments:
            # Skip if we already have a high-confidence match for this investment
            existing_conf = max(
                (c.confidence for c in candidates if c.target_id == inv["id"]),
                default=0.0,
            )
            if existing_conf >= 0.9:
                continue

            sim = self._string_similarity(source_name, inv["name"])
            if sim >= 0.5:
                candidates.append(MatchCandidate(
                    target_id=inv["id"],
                    target_name=inv["name"],
                    target_type="investment",
                    confidence=round(sim * 0.9, 3),  # scale: fuzzy is less certain than exact
                    match_method="fuzzy_string",
                    reasoning=f"String similarity {sim:.0%} between '{source_name}' and '{inv['name']}'.",
                ))

        # ------------------------------------------------------------------
        # Layer 5: Keyword extraction match (60-80%)
        # ------------------------------------------------------------------
        source_text = f"{source_name} {source_desc}".strip()
        source_kws = self._extract_keywords(source_text)

        if source_kws:
            for inv in investments:
                existing_conf = max(
                    (c.confidence for c in candidates if c.target_id == inv["id"]),
                    default=0.0,
                )
                if existing_conf >= 0.7:
                    continue

                inv_text = f"{inv['name']} {inv.get('description', '')}".strip()
                inv_kws = self._extract_keywords(inv_text)
                overlap = self._keyword_overlap(source_kws, inv_kws)

                if overlap >= 0.2:
                    kw_conf = round(0.4 + (overlap * 0.4), 3)  # maps 0.2-1.0 → 0.48-0.80
                    candidates.append(MatchCandidate(
                        target_id=inv["id"],
                        target_name=inv["name"],
                        target_type="investment",
                        confidence=kw_conf,
                        match_method="keyword_overlap",
                        reasoning=(
                            f"Keyword overlap {overlap:.0%}. "
                            f"Shared: {', '.join(sorted(source_kws & inv_kws)[:5])}"
                        ),
                    ))

        # ------------------------------------------------------------------
        # Layer 6: AI reasoning (slower, only when best is still < 0.7)
        # ------------------------------------------------------------------
        # Deduplicate: keep highest confidence per target_id
        deduped = _dedup_candidates(candidates)
        best_so_far = max((c.confidence for c in deduped), default=0.0)

        if best_so_far < 0.70 and investments:
            try:
                ai_candidates = await self._ai_match(item, investments)
                deduped = _dedup_candidates(deduped + ai_candidates)
            except Exception as e:
                logger.warning(f"AI match failed for '{source_name}': {e}")

        # Final sort: highest confidence first
        deduped.sort(key=lambda c: c.confidence, reverse=True)

        result.candidates = deduped[:5]  # top 5 only
        result.best_match = deduped[0] if deduped else None

        # Determine status
        if result.best_match:
            best_conf = result.best_match.confidence
            # Check for a close runner-up (within 10 points)
            runner_up_close = (
                len(deduped) >= 2 and
                (deduped[0].confidence - deduped[1].confidence) < 0.10
            )
            if best_conf >= 0.85 and not runner_up_close:
                result.needs_review = False
                result.match_status = "auto_matched"
            elif best_conf >= 0.5:
                result.needs_review = True
                result.match_status = "needs_review"
            else:
                result.needs_review = True
                result.match_status = "unmatched"
        else:
            result.needs_review = True
            result.match_status = "unmatched"

        return result

    # =========================================================================
    # Name normalization & similarity
    # =========================================================================

    def _normalize_name(self, name: str) -> str:
        """Normalize a name for comparison."""
        if not name:
            return ""

        text = name.lower().strip()

        # Expand known abbreviations
        for abbr, expansion in ABBREVIATIONS.items():
            # Only match whole words
            text = re.sub(r'\b' + re.escape(abbr) + r'\b', expansion, text)

        # Remove special chars except hyphens and spaces
        text = re.sub(r'[^a-z0-9\s\-]', ' ', text)

        # Remove noise suffixes
        for suffix in NOISE_SUFFIXES:
            text = re.sub(r'\b' + re.escape(suffix) + r'\b', '', text)

        # Collapse whitespace
        text = re.sub(r'\s+', ' ', text).strip()

        return text

    def _string_similarity(self, a: str, b: str) -> float:
        """Compute string similarity between two names using multiple methods."""
        if not a or not b:
            return 0.0

        na = self._normalize_name(a)
        nb = self._normalize_name(b)

        if not na or not nb:
            return 0.0

        # Method 1: SequenceMatcher ratio
        seq_ratio = SequenceMatcher(None, na, nb).ratio()

        # Method 2: Containment (one is substring of the other)
        containment = 0.0
        if na in nb or nb in na:
            shorter = min(len(na), len(nb))
            longer = max(len(na), len(nb))
            containment = shorter / longer if longer > 0 else 0.0

        # Method 3: Token overlap (Jaccard on word sets)
        tokens_a = set(na.split())
        tokens_b = set(nb.split())
        if tokens_a and tokens_b:
            intersection = tokens_a & tokens_b
            union = tokens_a | tokens_b
            token_overlap = len(intersection) / len(union)
        else:
            token_overlap = 0.0

        # Method 4: Acronym match (first letters of source words vs target)
        acronym_score = self._acronym_similarity(a, b)

        return max(seq_ratio, containment, token_overlap, acronym_score)

    def _acronym_similarity(self, a: str, b: str) -> float:
        """Check if one string's acronym matches the other string."""
        def make_acronym(s: str) -> str:
            return ''.join(w[0] for w in s.lower().split() if w and w not in STOPWORDS)

        acr_a = make_acronym(a)
        acr_b = make_acronym(b)
        norm_a = self._normalize_name(a).replace(' ', '')
        norm_b = self._normalize_name(b).replace(' ', '')

        if acr_a and len(acr_a) >= 2 and acr_a == norm_b[:len(acr_a)]:
            return 0.75
        if acr_b and len(acr_b) >= 2 and acr_b == norm_a[:len(acr_b)]:
            return 0.75
        return 0.0

    # =========================================================================
    # Keyword extraction
    # =========================================================================

    def _extract_keywords(self, text: str) -> set[str]:
        """Extract meaningful keywords from a name or description."""
        if not text:
            return set()

        words = re.sub(r'[^a-z0-9\s]', ' ', text.lower()).split()

        keywords = set()
        for word in words:
            if len(word) < 2:
                continue
            if word in STOPWORDS:
                continue
            if word in DOMAIN_KEYWORDS or word in ACTION_KEYWORDS:
                keywords.add(word)
            elif len(word) >= 4:
                # Include longer words that aren't common noise
                keywords.add(word)

        return keywords

    def _keyword_overlap(self, keywords_a: set, keywords_b: set) -> float:
        """Compute Jaccard similarity between keyword sets."""
        if not keywords_a or not keywords_b:
            return 0.0
        intersection = keywords_a & keywords_b
        union = keywords_a | keywords_b
        return len(intersection) / len(union)

    # =========================================================================
    # AI reasoning
    # =========================================================================

    async def _ai_match(self, item: dict, investments: list[dict]) -> list[MatchCandidate]:
        """Use Claude to reason about ambiguous matches."""
        system_prompt = """You are a data matching expert for a financial planning system.
Your job is to match items from external systems (Salesforce products, JIRA projects, GL cost centers)
to internal investment categories.

Rules:
- If there's a clear match, say so with high confidence (0.85+)
- If the item could map to multiple investments, suggest a split with percentages (must sum to 100)
- If the item is operational/maintenance (not an investment), set is_rtb=true with the appropriate L2 category
- If you're genuinely unsure, say so — don't force a match; use confidence < 0.5
- Consider name similarity, domain overlap, and common sense

RTB L2 categories: RTB-OPS (operations), RTB-MNT (maintenance), RTB-CMP (compliance), RTB-SUP (support)
CTB L2 categories: CTB-GRW (growth), CTB-TRN (transformation), CTB-EFF (efficiency), CTB-INN (innovation)

Return ONLY valid JSON:
{
  "matches": [
    {"investment_id": "...", "confidence": 0.85, "reasoning": "...", "allocation_pct": 100}
  ],
  "is_rtb": false,
  "rtb_l2": null,
  "notes": "..."
}"""

        inv_list = [
            {"id": inv["id"], "name": inv["name"], "l2": inv.get("l2_category", "")}
            for inv in investments[:50]  # cap to avoid token overflow
        ]

        user_msg = f"""Match this item to one of the available investments:

Item:
  Name: {item.get('name', '')}
  Description: {item.get('description', '')}
  System: {item.get('system', 'unknown')}
  Metadata: {json.dumps(item.get('metadata', {}), default=str)}

Available investments:
{json.dumps(inv_list, indent=2)}

Return only valid JSON."""

        try:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_msg}],
            )
            raw = response.content[0].text.strip()
            # Strip markdown fences
            if raw.startswith("```"):
                parts = raw.split("```")
                raw = parts[1] if len(parts) > 1 else raw
                if raw.startswith("json"):
                    raw = raw[4:]
            parsed = json.loads(raw.strip())
        except Exception as e:
            logger.warning(f"_ai_match parse failed: {e}")
            return []

        candidates: list[MatchCandidate] = []

        if parsed.get("is_rtb"):
            rtb_l2 = parsed.get("rtb_l2") or "RTB-OPS"
            candidates.append(MatchCandidate(
                target_id=rtb_l2,
                target_name=rtb_l2,
                target_type="rtb_category",
                confidence=0.75,
                match_method="ai_reasoning",
                reasoning=parsed.get("notes", "AI identified this as operational/RTB spend."),
            ))
        else:
            inv_map = {inv["id"]: inv for inv in investments}
            for match in parsed.get("matches", []):
                inv_id = match.get("investment_id", "")
                inv = inv_map.get(inv_id)
                if inv:
                    candidates.append(MatchCandidate(
                        target_id=inv_id,
                        target_name=inv["name"],
                        target_type="investment",
                        confidence=float(match.get("confidence", 0.5)),
                        match_method="ai_reasoning",
                        reasoning=match.get("reasoning", "AI-suggested match."),
                        allocation_pct=float(match.get("allocation_pct", 100)),
                    ))

        return candidates

    # =========================================================================
    # Advanced matching signals
    # =========================================================================

    async def match_people_overlap(self, source_system: str) -> dict:
        """Match by analyzing which people work across systems.

        If the same engineer appears in JIRA project X and is the owner
        of Salesforce deals for product Y, that's a strong signal.

        Returns: {jira_project: {salesforce_product: overlap_score}}
        """
        # Fetch effort data (JIRA) for this org
        effort_res = (
            self.db.table("effort_data")
            .select("source_project, source_epic")
            .eq("org_id", self.org_id)
            .execute()
        )
        # Fetch CRM data (Salesforce)
        crm_res = (
            self.db.table("crm_revenue_data")
            .select("source_product")
            .eq("org_id", self.org_id)
            .execute()
        )

        # In production: cross-reference people/owners across both datasets
        # For now, return a structure that can be enriched once people data is available
        jira_projects = list({r["source_project"] for r in (effort_res.data or []) if r.get("source_project")})
        sf_products = list({r["source_product"] for r in (crm_res.data or []) if r.get("source_product")})

        # Placeholder: compute name-based overlap as a proxy until people data exists
        result: dict[str, dict[str, float]] = {}
        for project in jira_projects:
            result[project] = {}
            for product in sf_products:
                sim = self._string_similarity(project, product)
                if sim >= 0.3:
                    result[project][product] = round(sim * 0.75, 3)  # people signal is weaker than name

        return result

    async def match_temporal_correlation(self, source_system: str) -> dict:
        """Match by analyzing temporal patterns.

        If JIRA velocity spikes correlate with Salesforce pipeline creation
        for certain products, that's a signal.

        Returns: {jira_project: {salesforce_product: correlation_score}}
        """
        # Fetch time-series effort data
        effort_res = (
            self.db.table("effort_data")
            .select("source_project, period, story_points_completed")
            .eq("org_id", self.org_id)
            .order("period")
            .execute()
        )
        crm_res = (
            self.db.table("crm_revenue_data")
            .select("source_product, period, pipeline_amount")
            .eq("org_id", self.org_id)
            .order("period")
            .execute()
        )

        # Group by project/product and period
        jira_by_project: dict[str, dict[str, float]] = {}
        for row in (effort_res.data or []):
            proj = row.get("source_project", "")
            period = row.get("period", "")
            if proj and period:
                jira_by_project.setdefault(proj, {})[period] = float(row.get("story_points_completed") or 0)

        crm_by_product: dict[str, dict[str, float]] = {}
        for row in (crm_res.data or []):
            prod = row.get("source_product", "")
            period = row.get("period", "")
            if prod and period:
                crm_by_product.setdefault(prod, {})[period] = float(row.get("pipeline_amount") or 0)

        result: dict[str, dict[str, float]] = {}
        for project, jira_ts in jira_by_project.items():
            result[project] = {}
            for product, crm_ts in crm_by_product.items():
                # Find common periods
                common_periods = sorted(set(jira_ts.keys()) & set(crm_ts.keys()))
                if len(common_periods) < 3:
                    continue
                jira_vals = [jira_ts[p] for p in common_periods]
                crm_vals = [crm_ts[p] for p in common_periods]
                corr = _pearson_correlation(jira_vals, crm_vals)
                if corr >= 0.3:
                    result[project][product] = round(corr * 0.65, 3)  # temporal is weakest signal

        return result

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _load_glossary(self) -> list[dict]:
        """Load firm glossary from DB or memory service."""
        if self.memory:
            try:
                return await self.memory.get_firm_glossary()
            except Exception:
                pass
        # Fallback: direct DB query
        try:
            res = (
                self.db.table("firm_glossary")
                .select("*")
                .eq("org_id", self.org_id)
                .order("usage_count", desc=True)
                .execute()
            )
            return res.data or []
        except Exception:
            return []

    def _resolve_target_name(self, target_id: str, target_type: str, investments: list[dict]) -> str:
        """Look up the display name for a target."""
        if target_type == "rtb_category":
            return target_id
        for inv in investments:
            if inv["id"] == target_id:
                return inv["name"]
        return target_id

    async def _save_mapping(self, result: MatchResult, candidate: MatchCandidate, confirmed: bool = False) -> None:
        """Persist a mapping to connector_mappings."""
        now = datetime.now(timezone.utc).isoformat()
        try:
            existing = (
                self.db.table("connector_mappings")
                .select("id")
                .eq("org_id", self.org_id)
                .eq("source_id", result.source_id)
                .eq("connector_type", result.source_system)
                .execute()
            )
            data = {
                "org_id": self.org_id,
                "connector_type": result.source_system,
                "source_id": result.source_id,
                "source_name": result.source_name,
                "source_type": result.source_type,
                "investment_id": candidate.target_id if candidate.target_type == "investment" else None,
                "l2_category": candidate.target_id if candidate.target_type == "rtb_category" else None,
                "mapping_method": candidate.match_method,
                "confidence": candidate.confidence,
                "confirmed": confirmed,
                "updated_at": now,
            }
            if existing.data:
                self.db.table("connector_mappings").update(data).eq("id", existing.data[0]["id"]).execute()
            else:
                data["id"] = str(uuid.uuid4())
                self.db.table("connector_mappings").insert(data).execute()
        except Exception as e:
            logger.warning(f"_save_mapping failed: {e}")

    async def _propagate_learning(
        self,
        source_name: str,
        target_id: str,
        target_type: str,
        source_system: str,
    ) -> None:
        """Propagate a confirmed mapping to similar unconfirmed items."""
        try:
            # Find unconfirmed mappings for the same system
            unconf_res = (
                self.db.table("connector_mappings")
                .select("id, source_name")
                .eq("org_id", self.org_id)
                .eq("connector_type", source_system)
                .eq("confirmed", False)
                .execute()
            )
            for row in (unconf_res.data or []):
                sim = self._string_similarity(source_name, row.get("source_name", ""))
                if sim >= 0.85:
                    # High similarity — boost this mapping's confidence and target
                    updates: dict = {"confidence": min(0.85, sim)}
                    if target_type == "investment":
                        updates["investment_id"] = target_id
                    else:
                        updates["l2_category"] = target_id
                    self.db.table("connector_mappings").update(updates).eq("id", row["id"]).execute()
        except Exception as e:
            logger.warning(f"_propagate_learning failed: {e}")

    async def get_matching_stats(self) -> dict:
        """Compute data quality score and coverage stats for this org."""
        try:
            # Total mappings
            total_res = (
                self.db.table("connector_mappings")
                .select("id, confirmed, confidence, connector_type")
                .eq("org_id", self.org_id)
                .execute()
            )
            rows = total_res.data or []
            total = len(rows)
            if total == 0:
                return {
                    "total": 0,
                    "confirmed": 0,
                    "auto_matched": 0,
                    "needs_review": 0,
                    "unmatched": 0,
                    "quality_score": 0,
                    "by_system": {},
                }

            confirmed_count = sum(1 for r in rows if r.get("confirmed"))
            auto_matched = sum(1 for r in rows if not r.get("confirmed") and r.get("confidence", 0) >= 0.85)
            needs_review = sum(
                1 for r in rows
                if not r.get("confirmed") and 0.5 <= r.get("confidence", 0) < 0.85
            )
            unmatched = sum(1 for r in rows if r.get("confidence", 0) < 0.5)

            # Quality score: weighted by confidence
            quality_score = (
                (confirmed_count * 1.0 + auto_matched * 0.85) / total * 100
                if total > 0 else 0
            )

            by_system: dict[str, dict] = {}
            for row in rows:
                sys = row.get("connector_type", "unknown")
                if sys not in by_system:
                    by_system[sys] = {"total": 0, "confirmed": 0}
                by_system[sys]["total"] += 1
                if row.get("confirmed"):
                    by_system[sys]["confirmed"] += 1

            return {
                "total": total,
                "confirmed": confirmed_count,
                "auto_matched": auto_matched,
                "needs_review": needs_review,
                "unmatched": unmatched,
                "quality_score": round(quality_score, 1),
                "by_system": by_system,
            }
        except Exception as e:
            logger.error(f"get_matching_stats failed: {e}")
            return {"total": 0, "confirmed": 0, "auto_matched": 0, "needs_review": 0, "unmatched": 0, "quality_score": 0, "by_system": {}}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _dedup_candidates(candidates: list[MatchCandidate]) -> list[MatchCandidate]:
    """Keep the highest-confidence candidate per target_id."""
    best: dict[str, MatchCandidate] = {}
    for c in candidates:
        key = f"{c.target_type}:{c.target_id}"
        if key not in best or c.confidence > best[key].confidence:
            best[key] = c
    return list(best.values())


def _result_to_dict(result: MatchResult) -> dict:
    """Serialize a MatchResult to a plain dict for API responses."""
    return {
        "source_id": result.source_id,
        "source_name": result.source_name,
        "source_type": result.source_type,
        "source_system": result.source_system,
        "match_status": result.match_status,
        "needs_review": result.needs_review,
        "best_match": _candidate_to_dict(result.best_match) if result.best_match else None,
        "candidates": [_candidate_to_dict(c) for c in result.candidates],
    }


def _candidate_to_dict(c: MatchCandidate) -> dict:
    return {
        "target_id": c.target_id,
        "target_name": c.target_name,
        "target_type": c.target_type,
        "confidence": c.confidence,
        "match_method": c.match_method,
        "reasoning": c.reasoning,
        "allocation_pct": c.allocation_pct,
    }


def _pearson_correlation(x: list[float], y: list[float]) -> float:
    """Compute Pearson correlation coefficient."""
    n = len(x)
    if n < 2:
        return 0.0
    mean_x = sum(x) / n
    mean_y = sum(y) / n
    dx = [v - mean_x for v in x]
    dy = [v - mean_y for v in y]
    num = sum(a * b for a, b in zip(dx, dy))
    den = (sum(a ** 2 for a in dx) ** 0.5) * (sum(b ** 2 for b in dy) ** 0.5)
    return num / den if den != 0 else 0.0

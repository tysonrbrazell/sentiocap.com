"""
Base connector class for all SentioCap integrations.
Each connector pulls data from an external system (Salesforce, JIRA, ERP, etc.)
and normalises it into SentioCap's unified schema.
"""
from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import Client


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SyncResult:
    """Returned by every connector.sync() call."""
    connector_type: str
    org_id: str
    status: str  # 'completed' | 'failed' | 'partial'
    records_synced: int = 0
    records_mapped: int = 0
    errors: list[dict] = field(default_factory=list)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    data: dict[str, Any] = field(default_factory=dict)  # raw synced data

    def to_dict(self) -> dict:
        return {
            "connector_type": self.connector_type,
            "org_id": self.org_id,
            "status": self.status,
            "records_synced": self.records_synced,
            "records_mapped": self.records_mapped,
            "errors": self.errors,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


@dataclass
class MappingResult:
    """Result of mapping a source item to an investment."""
    source_id: str
    source_name: str
    source_type: str  # 'product', 'project', 'epic', 'campaign'
    investment_id: Optional[str] = None
    investment_name: Optional[str] = None
    l2_category: Optional[str] = None
    mapping_method: str = "ai"  # 'ai', 'manual', 'rule'
    confidence: float = 0.5
    confirmed: bool = False


# ---------------------------------------------------------------------------
# Base connector
# ---------------------------------------------------------------------------

class BaseConnector(ABC):
    """
    Abstract base for all connectors. Implementations handle:
    - OAuth / token management
    - Data fetch from external system
    - Normalisation into SentioCap schema
    - Storage in Supabase tables

    Mock connectors override `_fetch_raw_data` to return synthetic data
    instead of hitting an external API. This makes swapping mock → real
    a single-line change.
    """

    connector_type: str = "base"
    is_mock: bool = False
    BLENDED_HOURLY_RATE: float = 125.0  # USD — orgs can override

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def connect(self, org_id: str, auth_code: Optional[str] = None, db: Optional[Client] = None) -> dict:
        """
        Initiate OAuth connection (or enable mock).
        Returns the connector_config record.
        """
        if db is None:
            raise ValueError("db client required")

        # Upsert connector_config
        existing = (
            db.table("connector_configs")
            .select("*")
            .eq("org_id", org_id)
            .eq("connector_type", self.connector_type)
            .execute()
        )

        config_data = {
            "org_id": org_id,
            "connector_type": self.connector_type,
            "status": "connected",
            "config": {"mock": self.is_mock},
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        if not self.is_mock and auth_code:
            tokens = await self._exchange_auth_code(auth_code, org_id)
            config_data.update(tokens)

        if existing.data:
            result = (
                db.table("connector_configs")
                .update(config_data)
                .eq("org_id", org_id)
                .eq("connector_type", self.connector_type)
                .execute()
            )
        else:
            config_data["id"] = str(uuid.uuid4())
            result = db.table("connector_configs").insert(config_data).execute()

        return result.data[0] if result.data else config_data

    async def disconnect(self, org_id: str, db: Optional[Client] = None) -> None:
        """Revoke tokens and mark connector as disconnected."""
        if db is None:
            raise ValueError("db client required")

        db.table("connector_configs").update({
            "status": "disconnected",
            "access_token": None,
            "refresh_token": None,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }).eq("org_id", org_id).eq("connector_type", self.connector_type).execute()

    async def sync(self, org_id: str, db: Optional[Client] = None) -> SyncResult:
        """
        Pull data from external system → store in Supabase.
        Subclasses implement _fetch_raw_data().
        """
        if db is None:
            raise ValueError("db client required")

        result = SyncResult(
            connector_type=self.connector_type,
            org_id=org_id,
            status="running",
            started_at=datetime.now(timezone.utc),
        )

        # Mark connector as syncing
        cfg = db.table("connector_configs").select("id").eq("org_id", org_id).eq(
            "connector_type", self.connector_type
        ).execute()
        connector_id = cfg.data[0]["id"] if cfg.data else None

        if connector_id:
            db.table("connector_configs").update({
                "status": "syncing",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", connector_id).execute()

        try:
            raw = await self._fetch_raw_data(org_id)
            stored = await self._store_data(org_id, raw, db)
            result.records_synced = stored.get("records_synced", 0)
            result.records_mapped = stored.get("records_mapped", 0)
            result.data = raw
            result.status = "completed"
        except Exception as exc:
            result.status = "failed"
            result.errors.append({"message": str(exc), "type": type(exc).__name__})

        result.completed_at = datetime.now(timezone.utc)

        # Write sync record
        if connector_id:
            sync_record = {
                "id": str(uuid.uuid4()),
                "connector_id": connector_id,
                "org_id": org_id,
                "status": result.status,
                "started_at": result.started_at.isoformat(),
                "completed_at": result.completed_at.isoformat(),
                "records_synced": result.records_synced,
                "records_mapped": result.records_mapped,
                "errors": result.errors,
            }
            db.table("connector_syncs").insert(sync_record).execute()

            db.table("connector_configs").update({
                "status": "connected" if result.status == "completed" else "error",
                "last_sync_at": result.completed_at.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }).eq("id", connector_id).execute()

        return result

    async def get_status(self, org_id: str, db: Optional[Client] = None) -> dict:
        """Return connector config + recent sync history."""
        if db is None:
            raise ValueError("db client required")

        cfg = (
            db.table("connector_configs")
            .select("*")
            .eq("org_id", org_id)
            .eq("connector_type", self.connector_type)
            .execute()
        )
        if not cfg.data:
            return {"connector_type": self.connector_type, "status": "disconnected"}

        config = cfg.data[0]
        syncs = (
            db.table("connector_syncs")
            .select("*")
            .eq("connector_id", config["id"])
            .order("created_at", desc=True)
            .limit(10)
            .execute()
        )

        config["recent_syncs"] = syncs.data or []
        return config

    async def map_to_investments(
        self,
        org_id: str,
        items: list[dict],
        db: Optional[Client] = None,
    ) -> list[MappingResult]:
        """
        AI-assisted mapping of source items (products, projects, epics)
        to investments. Uses name similarity as a proxy for AI matching.
        Real implementation would call an LLM for semantic matching.
        """
        if db is None:
            return []

        # Fetch existing investments for this org
        inv_result = (
            db.table("investments")
            .select("id, name, l2_category")
            .eq("org_id", org_id)
            .execute()
        )
        investments = inv_result.data or []

        mappings: list[MappingResult] = []
        for item in items:
            best_match = None
            best_score = 0.0

            source_name_lower = item.get("name", "").lower()
            for inv in investments:
                inv_name_lower = inv["name"].lower()
                # Simple word-overlap score (proxy for LLM semantic match)
                src_words = set(source_name_lower.split())
                inv_words = set(inv_name_lower.split())
                if src_words and inv_words:
                    overlap = len(src_words & inv_words) / max(len(src_words), len(inv_words))
                    if overlap > best_score:
                        best_score = overlap
                        best_match = inv

            mapping = MappingResult(
                source_id=item.get("id", ""),
                source_name=item.get("name", ""),
                source_type=item.get("type", "product"),
                investment_id=best_match["id"] if best_match and best_score > 0.3 else None,
                investment_name=best_match["name"] if best_match and best_score > 0.3 else None,
                l2_category=best_match.get("l2_category") if best_match else None,
                mapping_method="ai",
                confidence=round(best_score, 2),
                confirmed=False,
            )
            mappings.append(mapping)

        return mappings

    # ------------------------------------------------------------------
    # Abstract / overridable methods
    # ------------------------------------------------------------------

    @abstractmethod
    async def _fetch_raw_data(self, org_id: str) -> dict:
        """
        Fetch raw data from external system (or generate mock data).
        Returns a dict with keys specific to the connector type.
        """
        ...

    async def _store_data(self, org_id: str, raw: dict, db: Client) -> dict:
        """
        Store normalised data in Supabase. Override per connector type.
        Returns {"records_synced": N, "records_mapped": M}
        """
        return {"records_synced": 0, "records_mapped": 0}

    async def _exchange_auth_code(self, auth_code: str, org_id: str) -> dict:
        """
        Exchange OAuth auth_code for access/refresh tokens.
        Override per connector. Returns token fields to merge into config.
        """
        return {}

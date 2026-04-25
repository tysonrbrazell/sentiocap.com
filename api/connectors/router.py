"""
Connectors router — manage data integrations with Salesforce, JIRA, ERPs.

Endpoints:
  GET    /api/connectors                        — list all connectors
  POST   /api/connectors/{type}/connect         — OAuth or enable mock
  POST   /api/connectors/{type}/disconnect      — revoke & disconnect
  POST   /api/connectors/{type}/sync            — trigger sync
  GET    /api/connectors/{type}/status          — status + sync history
  GET    /api/connectors/{type}/data/revenue    — synced CRM revenue data
  GET    /api/connectors/{type}/data/effort     — synced JIRA effort data
  GET    /api/connectors/{type}/mappings        — product→investment mappings
  PUT    /api/connectors/{type}/mappings/{id}   — confirm or change mapping
"""
from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from supabase import Client

from database import get_db
from routers.auth import get_current_user
from models.schemas import (
    ConnectorConfigResponse,
    ConnectorSyncResponse,
    ConnectorMappingResponse,
    CrmRevenueDataResponse,
    EffortDataResponse,
    ConnectorConnectRequest,
    MappingUpdateRequest,
    SyncResult as SyncResultSchema,
)
from connectors.mock_salesforce import MockSalesforceConnector
from connectors.mock_jira import MockJiraConnector
from services.investment_cost import InvestmentCostReconciler

router = APIRouter(prefix="/connectors", tags=["connectors"])

# ---------------------------------------------------------------------------
# Connector registry
# ---------------------------------------------------------------------------

MOCK_CONNECTORS = {
    "salesforce": MockSalesforceConnector(),
    "jira": MockJiraConnector(),
}

SUPPORTED_TYPES = list(MOCK_CONNECTORS.keys()) + [
    "hubspot", "dynamics", "workday", "sap", "servicenow"
]


def _get_connector(connector_type: str):
    """Return the appropriate connector instance."""
    if connector_type in MOCK_CONNECTORS:
        return MOCK_CONNECTORS[connector_type]
    raise HTTPException(
        status_code=400,
        detail=f"Connector type '{connector_type}' not yet implemented. "
               f"Supported: {', '.join(MOCK_CONNECTORS.keys())}"
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("", response_model=list[ConnectorConfigResponse])
async def list_connectors(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """List all connectors for the org with their current status."""
    org_id = current_user["org_id"]

    # Fetch existing configs
    result = (
        db.table("connector_configs")
        .select("*")
        .eq("org_id", org_id)
        .execute()
    )
    configured = {r["connector_type"]: r for r in (result.data or [])}

    # Return all supported types, filling in defaults for unconfigured ones
    connectors = []
    for ctype in SUPPORTED_TYPES:
        if ctype in configured:
            cfg = configured[ctype]
        else:
            cfg = {
                "id": None,
                "org_id": org_id,
                "connector_type": ctype,
                "status": "disconnected",
                "last_sync_at": None,
                "sync_frequency": "daily",
                "config": {},
                "created_at": None,
                "updated_at": None,
            }

        # Attach recent sync stats
        if cfg.get("id"):
            syncs = (
                db.table("connector_syncs")
                .select("records_synced, status, completed_at")
                .eq("connector_id", cfg["id"])
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )
            cfg["last_sync"] = syncs.data[0] if syncs.data else None
        else:
            cfg["last_sync"] = None

        connectors.append(cfg)

    return connectors


@router.post("/{connector_type}/connect")
async def connect_connector(
    connector_type: str,
    body: ConnectorConnectRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Initiate OAuth or enable mock connector."""
    org_id = current_user["org_id"]
    connector = _get_connector(connector_type)
    config = await connector.connect(
        org_id=org_id,
        auth_code=body.auth_code,
        db=db,
    )
    return {"status": "connected", "connector": config}


@router.post("/{connector_type}/disconnect")
async def disconnect_connector(
    connector_type: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Disconnect and revoke tokens."""
    org_id = current_user["org_id"]
    connector = _get_connector(connector_type)
    await connector.disconnect(org_id=org_id, db=db)
    return {"status": "disconnected", "connector_type": connector_type}


@router.post("/{connector_type}/sync")
async def trigger_sync(
    connector_type: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Trigger a data sync for the connector."""
    org_id = current_user["org_id"]

    # Check connector is connected
    cfg = (
        db.table("connector_configs")
        .select("status")
        .eq("org_id", org_id)
        .eq("connector_type", connector_type)
        .execute()
    )
    if not cfg.data or cfg.data[0]["status"] == "disconnected":
        raise HTTPException(
            status_code=400,
            detail=f"Connector '{connector_type}' is not connected. Connect it first."
        )

    connector = _get_connector(connector_type)
    result = await connector.sync(org_id=org_id, db=db)

    return {
        "status": result.status,
        "records_synced": result.records_synced,
        "records_mapped": result.records_mapped,
        "errors": result.errors,
        "started_at": result.started_at.isoformat() if result.started_at else None,
        "completed_at": result.completed_at.isoformat() if result.completed_at else None,
    }


@router.get("/{connector_type}/status")
async def connector_status(
    connector_type: str,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get connector config and sync history."""
    org_id = current_user["org_id"]
    connector = _get_connector(connector_type)
    status = await connector.get_status(org_id=org_id, db=db)
    return status


@router.get("/{connector_type}/data/revenue", response_model=list[CrmRevenueDataResponse])
async def get_revenue_data(
    connector_type: str,
    period: Optional[str] = Query(None, description="Filter by period YYYY-MM"),
    product: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """View synced CRM revenue data."""
    org_id = current_user["org_id"]

    # If no DB data, return mock data directly (useful before first sync)
    q = (
        db.table("crm_revenue_data")
        .select("*")
        .eq("org_id", org_id)
        .eq("connector_type", connector_type)
    )
    if period:
        q = q.eq("period", period)
    if product:
        q = q.eq("source_product", product)

    result = q.order("period").order("source_product").execute()

    if not result.data and connector_type == "salesforce":
        # Return mock data in response format
        connector = MOCK_CONNECTORS.get("salesforce")
        if connector:
            raw = await connector._fetch_raw_data(org_id)
            rows = raw.get("revenue_by_period", [])
            if period:
                rows = [r for r in rows if r["period"] == period]
            if product:
                rows = [r for r in rows if r["source_product"] == product]
            return [
                {**r, "id": None, "org_id": org_id, "connector_type": "salesforce",
                 "investment_id": None, "synced_at": None, "created_at": None}
                for r in rows
            ]

    return result.data or []


@router.get("/{connector_type}/data/effort", response_model=list[EffortDataResponse])
async def get_effort_data(
    connector_type: str,
    period: Optional[str] = Query(None),
    project: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """View synced JIRA effort data."""
    org_id = current_user["org_id"]

    q = (
        db.table("effort_data")
        .select("*")
        .eq("org_id", org_id)
        .eq("connector_type", connector_type)
    )
    if period:
        q = q.eq("period", period)
    if project:
        q = q.eq("source_project", project)

    result = q.order("period").order("source_project").execute()

    if not result.data and connector_type == "jira":
        connector = MOCK_CONNECTORS.get("jira")
        if connector:
            raw = await connector._fetch_raw_data(org_id)
            rows = raw.get("effort_by_period", [])
            if period:
                rows = [r for r in rows if r["period"] == period]
            if project:
                rows = [r for r in rows if r["source_project"] == project]
            return [
                {**r, "id": None, "org_id": org_id, "connector_type": "jira",
                 "investment_id": None, "synced_at": None, "created_at": None}
                for r in rows
            ]

    return result.data or []


@router.get("/{connector_type}/mappings", response_model=list[ConnectorMappingResponse])
async def get_mappings(
    connector_type: str,
    confirmed_only: bool = Query(False),
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """View product→investment mappings for this connector."""
    org_id = current_user["org_id"]

    q = (
        db.table("connector_mappings")
        .select("*")
        .eq("org_id", org_id)
        .eq("connector_type", connector_type)
    )
    if confirmed_only:
        q = q.eq("confirmed", True)

    result = q.order("source_name").execute()
    return result.data or []


@router.get("/unified-cost")
async def unified_cost(
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Get unified investment cost view across all 3 layers + revenue."""
    org_id = current_user["org_id"]
    reconciler = InvestmentCostReconciler(db)
    views = await reconciler.reconcile_all(org_id)
    return [v.to_dict() for v in views]


@router.put("/{connector_type}/mappings/{mapping_id}", response_model=ConnectorMappingResponse)
async def update_mapping(
    connector_type: str,
    mapping_id: str,
    body: MappingUpdateRequest,
    current_user: dict = Depends(get_current_user),
    db: Client = Depends(get_db),
):
    """Confirm or change a product→investment mapping."""
    org_id = current_user["org_id"]

    existing = (
        db.table("connector_mappings")
        .select("*")
        .eq("id", mapping_id)
        .eq("org_id", org_id)
        .execute()
    )
    if not existing.data:
        raise HTTPException(status_code=404, detail="Mapping not found")

    updates: dict[str, Any] = {"mapping_method": "manual"}
    if body.investment_id is not None:
        updates["investment_id"] = str(body.investment_id)
    if body.l2_category is not None:
        updates["l2_category"] = body.l2_category
    if body.confirmed is not None:
        updates["confirmed"] = body.confirmed
    if body.confirmed:
        updates["confidence"] = 1.0

    result = (
        db.table("connector_mappings")
        .update(updates)
        .eq("id", mapping_id)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=500, detail="Update failed")

    return result.data[0]

"""
Documents router — upload, parse, detect structure, map taxonomy, extract financials.

Endpoints:
  POST   /api/documents/upload
  POST   /api/documents/{id}/parse
  POST   /api/documents/{id}/detect-structure
  POST   /api/documents/{id}/map-taxonomy
  PUT    /api/documents/{id}/mappings/{mapping_id}
  POST   /api/documents/{id}/extract
  GET    /api/documents/{id}/report
  GET    /api/documents
"""
from __future__ import annotations

import json
import logging
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Body, status
from pydantic import BaseModel

from services.document_parser import (
    DocumentParser,
    TaxonomyMapping,
    CategoryMapping,
    get_parser,
)

logger = logging.getLogger(__name__)
router = APIRouter(tags=["documents"])

# ---------------------------------------------------------------------------
# Storage — lightweight JSON-on-disk store (no DB required)
# ---------------------------------------------------------------------------

STORAGE_DIR = Path("/data/.openclaw/workspace/sentiocap/api/storage/documents")
UPLOAD_DIR = STORAGE_DIR / "uploads"
META_DIR = STORAGE_DIR / "meta"

for _d in (UPLOAD_DIR, META_DIR):
    _d.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {"pdf", "pptx", "xlsx", "xls", "csv"}


def _meta_path(doc_id: str) -> Path:
    return META_DIR / f"{doc_id}.json"


def _load_meta(doc_id: str) -> dict:
    p = _meta_path(doc_id)
    if not p.exists():
        raise HTTPException(status_code=404, detail=f"Document {doc_id} not found")
    return json.loads(p.read_text())


def _save_meta(doc_id: str, meta: dict) -> None:
    _meta_path(doc_id).write_text(json.dumps(meta, indent=2, default=str))


def _all_meta() -> list[dict]:
    results = []
    for f in sorted(META_DIR.glob("*.json")):
        try:
            results.append(json.loads(f.read_text()))
        except Exception:
            pass
    return results


def _safe_asdict(obj: Any) -> Any:
    """Recursively convert dataclasses to dicts, handling nested objects."""
    try:
        return asdict(obj)
    except TypeError:
        return obj


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------


class MappingUpdate(BaseModel):
    mapped_l1: Optional[str] = None
    mapped_l2: Optional[str] = None
    mapped_l3: Optional[str] = None
    mapped_l4: Optional[str] = None
    confidence: Optional[float] = None
    reasoning: Optional[str] = None
    needs_review: Optional[bool] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/upload", status_code=status.HTTP_201_CREATED)
async def upload_document(file: UploadFile = File(...)):
    """
    Upload a financial document (PDF, PPTX, XLSX, CSV).
    Returns a document_id for subsequent processing steps.
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    doc_id = str(uuid.uuid4())
    save_path = UPLOAD_DIR / f"{doc_id}.{ext}"

    content = await file.read()
    save_path.write_bytes(content)

    meta = {
        "id": doc_id,
        "filename": file.filename,
        "file_type": ext,
        "file_path": str(save_path),
        "file_size_bytes": len(content),
        "uploaded_at": datetime.now(timezone.utc).isoformat(),
        "status": "uploaded",
        "parsed": None,
        "structure": None,
        "mapping": None,
        "classified": None,
    }
    _save_meta(doc_id, meta)
    logger.info(f"Document uploaded: {doc_id} ({file.filename}, {len(content)} bytes)")

    return {
        "document_id": doc_id,
        "filename": file.filename,
        "file_type": ext,
        "file_size_bytes": len(content),
        "status": "uploaded",
    }


@router.post("/{doc_id}/parse")
async def parse_document(doc_id: str):
    """
    Parse the document — extract raw text, tables, and sections.
    Returns a summary of the ParsedDocument.
    """
    meta = _load_meta(doc_id)
    parser: DocumentParser = get_parser()

    try:
        parsed = await parser.parse_document(meta["file_path"], meta["file_type"])
    except Exception as e:
        logger.error(f"Parse failed for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Parse failed: {str(e)}")

    # Store parsed result in meta (summary only — full text is large)
    parsed_summary = {
        "char_count": len(parsed.raw_text),
        "table_count": len(parsed.tables),
        "section_count": len(parsed.sections),
        "metadata": parsed.metadata,
        "table_summaries": [t.to_dict() for t in parsed.tables[:20]],
        "raw_text_preview": parsed.raw_text[:2000],
        "sections": [{"heading": s.heading, "level": s.level} for s in parsed.sections[:50]],
    }

    # Save full raw_text for later AI steps
    raw_path = UPLOAD_DIR / f"{doc_id}.raw.txt"
    raw_path.write_text(parsed.raw_text)

    meta["status"] = "parsed"
    meta["parsed"] = parsed_summary
    meta["raw_text_path"] = str(raw_path)
    _save_meta(doc_id, meta)

    return {
        "document_id": doc_id,
        "status": "parsed",
        **parsed_summary,
    }


@router.post("/{doc_id}/detect-structure")
async def detect_structure(doc_id: str):
    """
    Run AI structure detection on the parsed document.
    Returns the DetectedStructure with hierarchy levels and categories.
    """
    meta = _load_meta(doc_id)
    if not meta.get("parsed"):
        raise HTTPException(status_code=400, detail="Document must be parsed first. Call /parse.")

    parser: DocumentParser = get_parser()

    # Reconstruct minimal ParsedDocument for structure detection
    raw_text_path = meta.get("raw_text_path")
    raw_text = Path(raw_text_path).read_text() if raw_text_path else ""

    from services.document_parser import ParsedDocument, ExtractedTable, Section
    parsed = ParsedDocument(
        raw_text=raw_text,
        tables=[
            ExtractedTable(
                headers=t["headers"],
                rows=t.get("sample_rows", []),
                page_or_slide=t.get("page_or_slide", 0),
                title=t.get("title", ""),
            )
            for t in meta["parsed"].get("table_summaries", [])
        ],
        sections=[
            Section(heading=s["heading"], content="", level=s.get("level", 1))
            for s in meta["parsed"].get("sections", [])
        ],
        metadata=meta["parsed"].get("metadata", {}),
    )

    try:
        structure = await parser.detect_structure(parsed)
    except Exception as e:
        logger.error(f"detect_structure failed for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Structure detection failed: {str(e)}")

    structure_dict = _safe_asdict(structure)
    meta["status"] = "structure_detected"
    meta["structure"] = structure_dict
    _save_meta(doc_id, meta)

    return {
        "document_id": doc_id,
        "status": "structure_detected",
        **structure_dict,
    }


@router.post("/{doc_id}/map-taxonomy")
async def map_taxonomy(doc_id: str):
    """
    Run AI taxonomy mapping — maps the firm's categories to SentioCap L1-L4.
    Returns a TaxonomyMapping with confidence scores and review flags.
    """
    meta = _load_meta(doc_id)
    if not meta.get("structure"):
        raise HTTPException(
            status_code=400, detail="Structure must be detected first. Call /detect-structure."
        )

    parser: DocumentParser = get_parser()

    # Reconstruct DetectedStructure
    from services.document_parser import DetectedStructure, HierarchyLevel, DetectedCategory

    s = meta["structure"]
    structure = DetectedStructure(
        structure_tier=s["structure_tier"],
        hierarchy_levels=[
            HierarchyLevel(**h) for h in s.get("hierarchy_levels", [])
        ],
        has_rtb_ctb_split=s["has_rtb_ctb_split"],
        has_department_breakdown=s["has_department_breakdown"],
        has_investment_tracking=s["has_investment_tracking"],
        has_kpis=s["has_kpis"],
        detected_categories=[
            DetectedCategory(**c) for c in s.get("detected_categories", [])
        ],
        currency=s["currency"],
        fiscal_period=s.get("fiscal_period", ""),
        confidence=s["confidence"],
    )

    try:
        mapping = await parser.map_to_taxonomy(structure)
    except Exception as e:
        logger.error(f"map_to_taxonomy failed for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Taxonomy mapping failed: {str(e)}")

    mapping_dict = _safe_asdict(mapping)
    # Add stable IDs to each mapping for update endpoint
    for i, m in enumerate(mapping_dict["mappings"]):
        m["mapping_id"] = i

    meta["status"] = "taxonomy_mapped"
    meta["mapping"] = mapping_dict
    _save_meta(doc_id, meta)

    return {
        "document_id": doc_id,
        "status": "taxonomy_mapped",
        **mapping_dict,
    }


@router.put("/{doc_id}/mappings/{mapping_id}")
async def update_mapping(doc_id: str, mapping_id: int, update: MappingUpdate):
    """
    Update a specific mapping (user correction).
    Marks the mapping as manually reviewed and updates confidence to 1.0.
    """
    meta = _load_meta(doc_id)
    if not meta.get("mapping"):
        raise HTTPException(status_code=400, detail="No taxonomy mapping exists for this document.")

    mappings = meta["mapping"].get("mappings", [])
    target = next((m for m in mappings if m.get("mapping_id") == mapping_id), None)
    if target is None:
        raise HTTPException(status_code=404, detail=f"Mapping {mapping_id} not found")

    # Apply updates
    update_data = update.model_dump(exclude_none=True)
    target.update(update_data)
    target["manually_reviewed"] = True
    if "confidence" not in update_data:
        target["confidence"] = 1.0  # User-confirmed = full confidence
    target["needs_review"] = False

    _save_meta(doc_id, meta)
    logger.info(f"Mapping {mapping_id} updated for document {doc_id}")

    return {
        "document_id": doc_id,
        "mapping_id": mapping_id,
        "updated": True,
        **target,
    }


@router.post("/{doc_id}/extract")
async def extract_financials(doc_id: str):
    """
    Extract and classify financial data using confirmed mappings.
    Returns ClassifiedData with line items, totals, and AI insights.
    """
    meta = _load_meta(doc_id)
    if not meta.get("mapping"):
        raise HTTPException(status_code=400, detail="Taxonomy mapping must exist. Call /map-taxonomy.")

    parser: DocumentParser = get_parser()

    # Reconstruct ParsedDocument
    raw_text_path = meta.get("raw_text_path")
    raw_text = Path(raw_text_path).read_text() if raw_text_path else ""

    from services.document_parser import ParsedDocument, TaxonomyMapping, CategoryMapping

    mapping_data = meta["mapping"]
    mapping = TaxonomyMapping(
        mappings=[
            CategoryMapping(
                source_name=m["source_name"],
                source_level=m.get("source_level", ""),
                mapped_l1=m["mapped_l1"],
                mapped_l2=m["mapped_l2"],
                mapped_l3=m["mapped_l3"],
                mapped_l4=m["mapped_l4"],
                confidence=m.get("confidence", 0.5),
                reasoning=m.get("reasoning", ""),
                needs_review=m.get("needs_review", False),
                allocation_pct=m.get("allocation_pct", 1.0),
            )
            for m in mapping_data.get("mappings", [])
        ],
        unmapped=mapping_data.get("unmapped", []),
        summary=mapping_data.get("summary", ""),
    )

    parsed = ParsedDocument(
        raw_text=raw_text,
        tables=[],
        sections=[],
        metadata=meta.get("parsed", {}).get("metadata", {}),
    )

    try:
        classified = await parser.extract_financials(parsed, mapping)
    except Exception as e:
        logger.error(f"extract_financials failed for {doc_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Financial extraction failed: {str(e)}")

    classified_dict = _safe_asdict(classified)
    meta["status"] = "classified"
    meta["classified"] = classified_dict
    _save_meta(doc_id, meta)

    return {
        "document_id": doc_id,
        "status": "classified",
        **classified_dict,
    }


@router.get("/{doc_id}/report")
async def get_report(doc_id: str):
    """
    Return the full analysis: structure + mappings + classified data + insights.
    """
    meta = _load_meta(doc_id)

    return {
        "document_id": doc_id,
        "filename": meta.get("filename"),
        "file_type": meta.get("file_type"),
        "status": meta.get("status"),
        "uploaded_at": meta.get("uploaded_at"),
        "parsed_summary": meta.get("parsed"),
        "structure": meta.get("structure"),
        "mapping": meta.get("mapping"),
        "classified": meta.get("classified"),
    }


@router.get("")
async def list_documents():
    """
    List all uploaded documents with their current status.
    """
    docs = _all_meta()
    return {
        "count": len(docs),
        "documents": [
            {
                "id": d.get("id"),
                "filename": d.get("filename"),
                "file_type": d.get("file_type"),
                "status": d.get("status"),
                "uploaded_at": d.get("uploaded_at"),
                "file_size_bytes": d.get("file_size_bytes"),
            }
            for d in docs
        ],
    }

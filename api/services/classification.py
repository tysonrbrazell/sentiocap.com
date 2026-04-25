"""
AI Classification service using Anthropic Claude.

Implements:
- classify_single()  → single expense classification
- classify_batch()   → batch of up to 100 items
"""
import json
import logging
from typing import Optional

import anthropic

from config import settings
from services.memory import AgentMemory

logger = logging.getLogger(__name__)

MODEL = "claude-3-5-sonnet-20241022"
BATCH_SIZE = 25  # items per API call

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = """You are an expert IT financial analyst specializing in technology spend classification. Your role is to classify enterprise IT expenses using the Investment Intent Taxonomy described below.

## Investment Intent Taxonomy

### L1 — Intent (choose one)
- RTB (Run The Business): Operational spend that maintains existing capabilities, keeps the lights on, and sustains current business operations. Examples: software maintenance, IT support staff, recurring SaaS subscriptions for existing tools, infrastructure hosting for current systems.
- CTB (Change The Business): Investment spend that builds new capabilities, transforms operations, or delivers future business value. Examples: new software development, digital transformation projects, implementing a new platform, AI/ML initiatives, innovation R&D. IMPORTANT: Any expense capitalized under ASC 350-40 (internal-use software development) must be classified as CTB, regardless of description.

### L2 — Category (choose one)
- L2-INF (Infrastructure & Platforms): Physical and virtual infrastructure — servers, storage, cloud compute, networking hardware, hosting environments.
- L2-APP (Applications & Software): Business applications, SaaS tools, ERP/CRM systems, software licenses.
- L2-DAT (Data & Analytics): Data warehousing, BI tools, analytics platforms, data engineering, reporting.
- L2-SEC (Security & Compliance): Cybersecurity tools, compliance programs, identity management, penetration testing, SOC/NOC operations.
- L2-OPS (IT Operations & Support): Help desk, IT service management, monitoring, incident response, ITSM tooling.
- L2-PEO (People & Talent): IT staff salaries, contractor fees, consulting, training, certifications, talent acquisition for IT roles.
- L2-INO (Innovation & R&D): Research projects, proof-of-concept work, emerging technology exploration, AI/ML experimentation.
- L2-PRO (Process & Transformation): Business process redesign, change management, digital transformation programs, organizational change.

### L3 — Domain (choose one)
- L3-CLD (Cloud & Hosting): Cloud services, hosting, colocation
- L3-NET (Networking & Connectivity): Networks, WAN, LAN, connectivity
- L3-SFT (Software Licensing): Software licenses, SaaS subscriptions
- L3-DEV (Development & Engineering): Software development, DevOps, engineering tools
- L3-ANL (Analytics & BI): Business intelligence, analytics, data platforms
- L3-HCM (Human Capital Management): Staffing, contractors, HR for IT roles
- L3-CYB (Cybersecurity): Security tooling, compliance, risk management
- L3-CHG (Change Management & Training): Training, change programs, transformation

### L4 — Activity
Select the most specific matching L4 code from the list below, or if no standard code fits, return the closest match with a note.

Standard L4 codes:
- L4-CLD-001: Public Cloud Compute (L3-CLD)
- L4-CLD-002: Cloud Storage (L3-CLD)
- L4-CLD-003: Cloud Networking (L3-CLD)
- L4-NET-001: WAN / SD-WAN (L3-NET)
- L4-NET-002: LAN Infrastructure (L3-NET)
- L4-SFT-001: SaaS Subscriptions (L3-SFT)
- L4-SFT-002: On-Prem Software Licenses (L3-SFT)
- L4-DEV-001: Application Development (L3-DEV)
- L4-DEV-002: DevOps Tooling (L3-DEV)
- L4-ANL-001: BI & Reporting Tools (L3-ANL)
- L4-ANL-002: Data Engineering (L3-ANL)
- L4-HCM-001: IT Staff Salaries (L3-HCM)
- L4-HCM-002: Contractor / Consulting (L3-HCM)
- L4-HCM-003: Training & Certification (L3-HCM)
- L4-CYB-001: Security Software (L3-CYB)
- L4-CYB-002: Penetration Testing (L3-CYB)
- L4-CHG-001: Change Management (L3-CHG)
- L4-CHG-002: Process Redesign (L3-CHG)

## Classification Rules
1. If the GL Account contains "capitalized" or "ASC 350-40" keywords, always classify as CTB.
2. When in doubt between RTB and CTB, ask: "Is this maintaining something existing (RTB) or building something new (CTB)?"
3. Prefer specificity: choose the L2/L3 that best matches the primary purpose, not a generic catch-all.
4. Confidence reflects your certainty given the available information. Low confidence often means the description is vague or could fit multiple categories.

## Output Format
Return ONLY a valid JSON object. No explanation text outside the JSON.

{
  "l1": "RTB" | "CTB",
  "l2": "<L2 code>",
  "l3": "<L3 code>",
  "l4": "<L4 code>",
  "confidence": <float between 0.0 and 1.0>,
  "reasoning": "<1-2 sentence explanation of why this classification was chosen>"
}"""

BATCH_EXTRA = """
## Batch Mode Instructions
You will receive an array of expenses (10–50 items). Classify each one independently, but maintain consistency across the batch:
- If multiple expenses from the same vendor appear, apply the same classification unless the descriptions clearly differ.
- If a cost center pattern clearly indicates a function (e.g., "CC-SEC" always = L2-SEC), apply it consistently.
- Return a JSON array in the same order as the input. Each element matches the single-item output schema plus an "id" field from the input.
- Do not skip any items. If an item is completely unclassifiable, return confidence: 0.1 and your best guess.
"""

SINGLE_USER_TEMPLATE = """Classify this expense:

Description: {description}
Cost Center: {cost_center}
GL Account: {gl_account}
Amount: {amount}

If the expense is capitalized under ASC 350-40, classify as CTB.
Return only valid JSON."""

BATCH_USER_TEMPLATE = """Classify the following expenses. Return a JSON array with one classification object per expense, in the same order as the input.

Expenses:
{expenses_json}

Each output object must include the original "id" field plus: l1, l2, l3, l4, confidence, reasoning.
Return only the JSON array. No other text."""


def _get_client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _safe_parse(raw_text: str) -> dict | list:
    """Parse JSON from Claude response, stripping markdown fences if present."""
    text = raw_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        text = parts[1] if len(parts) > 1 else text
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def _fallback_single() -> dict:
    return {
        "l1": "RTB",
        "l2": "L2-OPS",
        "l3": "L3-SFT",
        "l4": "L4-SFT-001",
        "confidence": 0.1,
        "reasoning": "Classification failed — manual review required.",
    }


def classify_single(
    description: str,
    cost_center: Optional[str] = None,
    gl_account: Optional[str] = None,
    amount: Optional[str] = None,
    memory: Optional["AgentMemory"] = None,
) -> dict:
    """Classify a single expense item. Returns dict with l1/l2/l3/l4/confidence/reasoning.

    If memory is provided, prior classifications and firm glossary context are injected
    into the system prompt so Scout learns from past corrections.
    """
    import asyncio

    client = _get_client()

    # Build memory-enhanced system prompt
    system = SYSTEM_PROMPT
    if memory is not None:
        try:
            loop = asyncio.new_event_loop()
            firm_context = loop.run_until_complete(memory.build_classification_context())
            loop.close()
            if firm_context:
                system = SYSTEM_PROMPT + "\n\n## Firm-Specific Terminology\n" + firm_context
        except Exception as mem_err:
            logger.warning(f"Memory context fetch failed: {mem_err}")

    user_msg = SINGLE_USER_TEMPLATE.format(
        description=description,
        cost_center=cost_center or "N/A",
        gl_account=gl_account or "N/A",
        amount=amount or "N/A",
    )
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = response.content[0].text
        result = _safe_parse(raw)
        if isinstance(result, dict):
            return result
        return _fallback_single()
    except Exception as e:
        logger.error(f"classify_single failed: {e}")
        return _fallback_single()


def classify_batch(items: list[dict], memory: Optional["AgentMemory"] = None) -> list[dict]:
    """Classify a list of expense items. Each item must have 'id' and 'description'.

    If memory is provided, firm glossary context is injected into the batch system prompt.
    Returns list of classification dicts (each with 'id' + l1/l2/l3/l4/confidence/reasoning).
    """
    if not items:
        return []

    import asyncio

    client = _get_client()
    batch_system = SYSTEM_PROMPT + "\n" + BATCH_EXTRA

    # Inject firm-specific glossary context from memory
    if memory is not None:
        try:
            loop = asyncio.new_event_loop()
            firm_context = loop.run_until_complete(memory.build_classification_context())
            loop.close()
            if firm_context:
                batch_system = batch_system + "\n\n## Firm-Specific Terminology\n" + firm_context
        except Exception as mem_err:
            logger.warning(f"Memory context fetch failed: {mem_err}")

    all_results: list[dict] = []

    def _fallback_item(item_id: str) -> dict:
        return {
            "id": item_id,
            **_fallback_single(),
        }

    # Process in chunks
    for chunk_start in range(0, len(items), BATCH_SIZE):
        chunk = items[chunk_start: chunk_start + BATCH_SIZE]
        expenses_json = json.dumps(
            [
                {
                    "id": item["id"],
                    "description": item.get("description", ""),
                    "cost_center": item.get("cost_center") or "N/A",
                    "gl_account": item.get("gl_account") or "N/A",
                    "amount": item.get("amount", 0),
                }
                for item in chunk
            ],
            indent=2,
        )

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=4096,
                system=batch_system,
                messages=[
                    {
                        "role": "user",
                        "content": BATCH_USER_TEMPLATE.format(expenses_json=expenses_json),
                    }
                ],
            )
            raw = response.content[0].text
            parsed = _safe_parse(raw)
            if isinstance(parsed, list):
                all_results.extend(parsed)
            else:
                # Fallback for unexpected format
                for item in chunk:
                    all_results.append(_fallback_item(item["id"]))
        except Exception as e:
            logger.error(f"classify_batch chunk failed: {e}")
            for item in chunk:
                all_results.append(_fallback_item(item["id"]))

    return all_results

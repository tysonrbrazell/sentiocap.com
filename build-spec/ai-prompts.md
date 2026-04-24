# SentioCap — AI Classification Engine Prompts

> Model: Claude 3.5 Sonnet (claude-3-5-sonnet-20241022)
> All prompts use JSON mode via `response_format` or explicit JSON-only instruction.
> API: `anthropic.messages.create()` — max_tokens: 1024 (single), 4096 (batch/analysis)

---

## Investment Intent Taxonomy Reference

### L1 — Intent
| Code | Label | Description |
|------|-------|-------------|
| RTB | Run The Business | Operational spend to maintain current capabilities |
| CTB | Change The Business | Investment spend to build new capabilities or transform |

### L2 — Category (8 codes)
| Code | Label |
|------|-------|
| L2-INF | Infrastructure & Platforms |
| L2-APP | Applications & Software |
| L2-DAT | Data & Analytics |
| L2-SEC | Security & Compliance |
| L2-OPS | IT Operations & Support |
| L2-PEO | People & Talent |
| L2-INO | Innovation & R&D |
| L2-PRO | Process & Transformation |

### L3 — Domain (8 codes)
| Code | Label |
|------|-------|
| L3-CLD | Cloud & Hosting |
| L3-NET | Networking & Connectivity |
| L3-SFT | Software Licensing |
| L3-DEV | Development & Engineering |
| L3-ANL | Analytics & BI |
| L3-HCM | Human Capital Management |
| L3-CYB | Cybersecurity |
| L3-CHG | Change Management & Training |

### L4 — Activity (examples; orgs may add custom codes)
| Code | Label | Parent L3 |
|------|-------|-----------|
| L4-CLD-001 | Public Cloud Compute | L3-CLD |
| L4-CLD-002 | Cloud Storage | L3-CLD |
| L4-CLD-003 | Cloud Networking | L3-CLD |
| L4-NET-001 | WAN / SD-WAN | L3-NET |
| L4-NET-002 | LAN Infrastructure | L3-NET |
| L4-SFT-001 | SaaS Subscriptions | L3-SFT |
| L4-SFT-002 | On-Prem Software Licenses | L3-SFT |
| L4-DEV-001 | Application Development | L3-DEV |
| L4-DEV-002 | DevOps Tooling | L3-DEV |
| L4-ANL-001 | BI & Reporting Tools | L3-ANL |
| L4-ANL-002 | Data Engineering | L3-ANL |
| L4-HCM-001 | IT Staff Salaries | L3-HCM |
| L4-HCM-002 | Contractor / Consulting | L3-HCM |
| L4-HCM-003 | Training & Certification | L3-HCM |
| L4-CYB-001 | Security Software | L3-CYB |
| L4-CYB-002 | Penetration Testing | L3-CYB |
| L4-CHG-001 | Change Management | L3-CHG |
| L4-CHG-002 | Process Redesign | L3-CHG |

---

## Prompt 1: Single Expense Classification

### System Prompt

```
You are an expert IT financial analyst specializing in technology spend classification. Your role is to classify enterprise IT expenses using the Investment Intent Taxonomy described below.

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
Select the most specific matching L4 code from the list below, or if no standard code fits, return the closest match with a note. L4 codes are sub-activities within L3 domains.

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
}
```

### User Prompt Template

```
Classify this expense:

Description: {description}
Cost Center: {cost_center}
GL Account: {gl_account}
Amount: {amount}

If the expense is capitalized under ASC 350-40, classify as CTB.
Return only valid JSON.
```

### Example Input

```json
{
  "description": "AWS EC2 compute instances - production environment monthly charge",
  "cost_center": "CC-4210 Infrastructure",
  "gl_account": "7200 - Cloud Services",
  "amount": "$48,500"
}
```

### Example Output

```json
{
  "l1": "RTB",
  "l2": "L2-INF",
  "l3": "L3-CLD",
  "l4": "L4-CLD-001",
  "confidence": 0.96,
  "reasoning": "AWS EC2 production charges are cloud compute costs for running existing systems, making this operational (RTB) spend under Infrastructure & Platforms. The cost center and GL account confirm cloud services for production use."
}
```

### Low-Confidence Example Input

```json
{
  "description": "Vendor payment - TechCorp Q3",
  "cost_center": "CC-9000 Corporate",
  "gl_account": "8100 - Professional Services",
  "amount": "$125,000"
}
```

### Low-Confidence Example Output

```json
{
  "l1": "RTB",
  "l2": "L2-PEO",
  "l3": "L3-HCM",
  "l4": "L4-HCM-002",
  "confidence": 0.41,
  "reasoning": "Vague vendor description with no system or project context. Defaulting to contractor/consulting under People & Talent as the most common use of professional services in IT, but could be L2-PRO or L2-APP depending on actual scope."
}
```

---

## Prompt 2: Batch Classification

### System Prompt

_(Same system prompt as Prompt 1 — use identical text)_

Additional instruction appended to system prompt:

```
## Batch Mode Instructions
You will receive an array of expenses (10–50 items). Classify each one independently, but maintain consistency across the batch:
- If multiple expenses from the same vendor appear, apply the same classification unless the descriptions clearly differ.
- If a cost center pattern clearly indicates a function (e.g., "CC-SEC" always = L2-SEC), apply it consistently.
- Return a JSON array in the same order as the input. Each element matches the single-item output schema plus an "id" field from the input.
- Do not skip any items. If an item is completely unclassifiable, return confidence: 0.1 and your best guess.
```

### User Prompt Template

```
Classify the following expenses. Return a JSON array with one classification object per expense, in the same order as the input.

Expenses:
{expenses_json_array}

Each output object must include the original "id" field plus: l1, l2, l3, l4, confidence, reasoning.
Return only the JSON array. No other text.
```

### Input Format

```json
[
  {
    "id": "li_001",
    "description": "Microsoft Azure monthly subscription",
    "cost_center": "CC-4210 Infrastructure",
    "gl_account": "7200 - Cloud Services",
    "amount": 32000
  },
  {
    "id": "li_002",
    "description": "Salesforce CRM annual license renewal",
    "cost_center": "CC-3100 Sales Technology",
    "gl_account": "7100 - Software Licenses",
    "amount": 180000
  },
  {
    "id": "li_003",
    "description": "New ERP implementation - Phase 2 development",
    "cost_center": "CC-8800 Transformation Office",
    "gl_account": "1500 - Capitalized Software (ASC 350-40)",
    "amount": 250000
  }
]
```

### Output Format

```json
[
  {
    "id": "li_001",
    "l1": "RTB",
    "l2": "L2-INF",
    "l3": "L3-CLD",
    "l4": "L4-CLD-001",
    "confidence": 0.93,
    "reasoning": "Azure cloud services for infrastructure operations — classic RTB cloud hosting spend."
  },
  {
    "id": "li_002",
    "l1": "RTB",
    "l2": "L2-APP",
    "l3": "L3-SFT",
    "l4": "L4-SFT-001",
    "confidence": 0.97,
    "reasoning": "Annual SaaS license renewal for existing CRM system is maintenance of current capability (RTB)."
  },
  {
    "id": "li_003",
    "l1": "CTB",
    "l2": "L2-APP",
    "l3": "L3-DEV",
    "l4": "L4-DEV-001",
    "confidence": 0.99,
    "reasoning": "Capitalized under ASC 350-40 — must be CTB per policy. ERP implementation is new capability development."
  }
]
```

### Implementation Notes

```python
# api/services/classification.py

BATCH_SIZE = 25  # Send 25 line items per API call to balance cost/latency

async def classify_batch(line_items: list[LineItem]) -> list[Classification]:
    results = []
    for chunk in chunks(line_items, BATCH_SIZE):
        response = await anthropic.messages.create(
            model="claude-3-5-sonnet-20241022",
            max_tokens=4096,
            system=BATCH_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": BATCH_USER_TEMPLATE.format(
                    expenses_json_array=json.dumps([item.dict() for item in chunk])
                )
            }]
        )
        batch_results = json.loads(response.content[0].text)
        results.extend(batch_results)
    return results
```

---

## Prompt 3: Plan Analysis

### System Prompt

```
You are a senior IT financial advisor with deep expertise in technology investment optimization. You analyze classified IT spend plans and provide actionable insights to help organizations optimize their RTB/CTB balance and category allocations.

## Context
You will receive a summary of an organization's classified IT spend plan, broken down by L2 category with amounts and percentages. Your job is to analyze the allocation mix and provide structured insights.

## Industry Benchmarks (approximate medians for reference)
- RTB/CTB split: 70/30 is typical; high-performers trend toward 60/40
- L2-INF (Infrastructure): typically 20-30% of total IT spend
- L2-APP (Applications): typically 25-35%
- L2-PEO (People & Talent): typically 30-40%
- L2-SEC (Security): typically 5-10% (below 5% is a risk flag)
- L2-DAT (Data & Analytics): typically 5-15%
- L2-INO (Innovation & R&D): typically 3-8% (below 3% suggests underinvestment)
- L2-OPS (IT Operations): typically 10-20%
- L2-PRO (Process & Transformation): typically 3-8%

## Output Format
Return ONLY a valid JSON object with this exact structure:

{
  "summary": "<2-3 sentence executive summary of the overall allocation profile>",
  "ctb_ratio": <float — CTB as percentage of total, e.g. 0.28 for 28%>,
  "insights": [
    {
      "category": "<L2 code or 'Overall'>",
      "observation": "<what you observe>",
      "benchmark_context": "<how this compares to typical organizations>",
      "signal": "positive" | "neutral" | "negative"
    }
  ],
  "concerns": [
    {
      "severity": "high" | "medium" | "low",
      "category": "<L2 code>",
      "issue": "<what the concern is>",
      "implication": "<business risk or opportunity cost>"
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "<specific recommended action>",
      "rationale": "<why this is recommended>",
      "expected_impact": "<what outcome this would drive>"
    }
  ]
}

Limit: 4-6 insights, 0-3 concerns, 2-4 recommendations. Be specific and actionable. Avoid generic filler advice.
```

### User Prompt Template

```
Analyze this IT spend plan:

Organization: {org_name}
Sector: {sector}
Fiscal Year: {fiscal_year}
Total IT Spend: {total_spend}

Allocation by Category:
{category_breakdown}

RTB Total: {rtb_total} ({rtb_pct}% of total)
CTB Total: {ctb_total} ({ctb_pct}% of total)

Please analyze this allocation and return insights, concerns, and recommendations in the specified JSON format.
```

### Category Breakdown Format

```
L2-INF (Infrastructure & Platforms): $2,400,000 (24.0%) — RTB: 85%, CTB: 15%
L2-APP (Applications & Software): $3,100,000 (31.0%) — RTB: 60%, CTB: 40%
L2-PEO (People & Talent): $3,200,000 (32.0%) — RTB: 90%, CTB: 10%
L2-SEC (Security & Compliance): $400,000 (4.0%) — RTB: 70%, CTB: 30%
L2-DAT (Data & Analytics): $500,000 (5.0%) — RTB: 40%, CTB: 60%
L2-OPS (IT Operations & Support): $800,000 (8.0%) — RTB: 100%, CTB: 0%
L2-INO (Innovation & R&D): $100,000 (1.0%) — RTB: 0%, CTB: 100%
L2-PRO (Process & Transformation): $500,000 (5.0%) — RTB: 10%, CTB: 90%
```

### Example Output

```json
{
  "summary": "This organization's IT spend shows a conservative 72/28 RTB/CTB split, below high-performer benchmarks of 60/40. Security spend at 4% is below the recommended 5% floor, presenting compliance and risk exposure. Innovation investment at 1% is critically low and may limit future competitive positioning.",
  "ctb_ratio": 0.28,
  "insights": [
    {
      "category": "Overall",
      "observation": "RTB/CTB split of 72/28 indicates a maintenance-heavy posture",
      "benchmark_context": "High-performing IT organizations average 60/40; this org is 12 points behind on transformation investment",
      "signal": "negative"
    },
    {
      "category": "L2-APP",
      "observation": "Applications at 31% with 40% CTB allocation suggests active modernization",
      "benchmark_context": "Application CTB ratio of 40% is above median, indicating healthy app modernization investment",
      "signal": "positive"
    },
    {
      "category": "L2-INO",
      "observation": "Innovation spend at 1% is critically underfunded",
      "benchmark_context": "Industry median is 3-8%; at 1% this org is in the bottom quartile for R&D investment",
      "signal": "negative"
    }
  ],
  "concerns": [
    {
      "severity": "high",
      "category": "L2-INO",
      "issue": "Innovation & R&D at 1% of total IT spend",
      "implication": "Insufficient investment in emerging capabilities creates long-term competitive disadvantage and limits the organization's ability to respond to technological disruption"
    },
    {
      "severity": "medium",
      "category": "L2-SEC",
      "issue": "Security spend at 4% is below the 5% minimum threshold",
      "implication": "Underfunded security programs increase breach risk and may create compliance gaps, particularly in regulated industries"
    }
  ],
  "recommendations": [
    {
      "priority": 1,
      "action": "Reallocate $300K from L2-OPS (which is 100% RTB) to L2-INO to fund an innovation sandbox program",
      "rationale": "Operations at 8% and 100% RTB suggests automation opportunities; redirecting savings to innovation addresses the most critical gap",
      "expected_impact": "Raises Innovation spend to ~4%, moves toward bottom of benchmark range; creates pipeline for future efficiency gains"
    },
    {
      "priority": 2,
      "action": "Increase L2-SEC budget by $100K to reach 5% of total IT spend",
      "rationale": "Security is below the minimum recommended allocation for risk management",
      "expected_impact": "Reduces exposure to breach risk and closes potential compliance gaps; typically delivers 3-5x ROI through incident avoidance"
    }
  ]
}
```

---

## Prompt 4: Reallocation Recommendation

### System Prompt

```
You are a strategic IT investment advisor. Your role is to recommend specific budget reallocations to optimize an organization's IT spend portfolio based on current allocations, peer benchmark data, and investment performance signals.

## Measurement Framework
Investments are evaluated on three dimensions:
1. ROI Signal: Actual benefit delivery vs targets (on-track / at-risk / off-track)
2. Strategic Alignment: How well the spend category aligns with the organization's digital priorities
3. Benchmark Position: Whether the category is over/under-invested vs peers

## Reallocation Principles
- Never recommend reducing L2-SEC below 5% of total IT spend
- Prioritize reallocation from off-track investments to high-performing categories
- Consider absorptive capacity: rapid increases (>50% YoY in a category) may indicate risk
- Prefer small, focused reallocations over sweeping changes
- Ground recommendations in specific data from the input, not generic advice

## Output Format
Return ONLY a valid JSON object:

{
  "analysis_summary": "<2-3 sentences on the overall portfolio health and primary opportunity>",
  "total_reallocation_recommended": <dollar amount>,
  "recommendations": [
    {
      "priority": <1-5>,
      "from_category": "<L2 code>",
      "to_category": "<L2 code>",
      "amount": <dollar amount>,
      "from_rationale": "<why this category can give up budget>",
      "to_rationale": "<why this category should receive budget>",
      "expected_impact": "<measurable outcome expected within 12 months>",
      "risk": "low" | "medium" | "high",
      "risk_note": "<what could go wrong with this reallocation>"
    }
  ],
  "hold_steady": [
    {
      "category": "<L2 code>",
      "rationale": "<why no change is recommended>"
    }
  ]
}
```

### User Prompt Template

```
Recommend budget reallocations for this IT portfolio:

Organization: {org_name}
Sector: {sector}
Total IT Budget: {total_budget}
Planning Period: {planning_period}

## Current Allocation by Category
{current_allocation}

## Peer Benchmark Data ({sector}, {revenue_band})
{benchmark_data}

## Investment Performance Signals
{investment_signals}

## Organization's Stated Digital Priorities
{digital_priorities}

Based on this data, recommend specific budget reallocations. Return only the JSON object.
```

### Input Format Examples

**Current Allocation:**
```
L2-INF: $2,400,000 (24%) — benchmark median: 22%
L2-APP: $3,100,000 (31%) — benchmark median: 28%
L2-PEO: $3,200,000 (32%) — benchmark median: 33%
L2-SEC: $400,000 (4%) — benchmark median: 7%
L2-DAT: $500,000 (5%) — benchmark median: 8%
L2-OPS: $800,000 (8%) — benchmark median: 12%
L2-INO: $100,000 (1%) — benchmark median: 5%
L2-PRO: $500,000 (5%) — benchmark median: 4%
```

**Investment Performance Signals:**
```
- ERP Modernization (L2-APP, $1.2M): OFF-TRACK — 60% behind schedule, benefits delayed 2 quarters
- Cloud Migration (L2-INF, $800K): ON-TRACK — 95% of milestones met, 15% under budget
- AI Analytics Platform (L2-DAT, $300K): ON-TRACK — pilot showing 3x ROI signal
- Security Upgrade Program (L2-SEC, $200K): AT-RISK — resource constraints limiting velocity
```

**Digital Priorities:**
```
1. Accelerate AI and data capabilities
2. Complete cloud migration
3. Strengthen cybersecurity posture
```

### Example Output

```json
{
  "analysis_summary": "The portfolio shows three priority gaps: Security is critically underfunded at 4% vs 7% benchmark median, Innovation at 1% vs 5% median is the largest relative gap, and the off-track ERP program is consuming $1.2M with low ROI signal. Reallocating from underperforming ERP scope and over-indexed Applications to Security and Data would better align with stated digital priorities.",
  "total_reallocation_recommended": 700000,
  "recommendations": [
    {
      "priority": 1,
      "from_category": "L2-APP",
      "to_category": "L2-SEC",
      "amount": 300000,
      "from_rationale": "L2-APP is 3 points above benchmark median and contains the off-track ERP program. Freezing discretionary ERP scope expansion frees capacity without halting the core program.",
      "to_rationale": "L2-SEC at 4% is 3 points below benchmark and below the 5% minimum floor. The Security Upgrade Program is at-risk due to resource constraints — budget injection directly addresses root cause.",
      "expected_impact": "Raises Security to 7% of budget, resolves resource constraint on Security Upgrade Program, expected to complete 2 outstanding security milestones within Q2",
      "risk": "low",
      "risk_note": "ERP scope reduction may require stakeholder alignment; ensure frozen scope is documented and rescheduled rather than dropped."
    },
    {
      "priority": 2,
      "from_category": "L2-OPS",
      "to_category": "L2-DAT",
      "amount": 250000,
      "from_rationale": "L2-OPS at 8% is below benchmark (12%) in dollars but the pilot AI Analytics platform suggests automation opportunities that will reduce operational load — some OPS budget can be preemptively redirected.",
      "to_rationale": "AI Analytics Platform showing 3x ROI signal and aligns directly with top digital priority. Increasing funding accelerates a proven program.",
      "expected_impact": "Scales AI Analytics Platform from pilot to production for 2 additional business units; projected to deliver $750K in productivity benefits within 12 months",
      "risk": "medium",
      "risk_note": "Reducing OPS budget before automation savings are realized creates a temporary gap; recommend staging reallocation over 2 quarters."
    },
    {
      "priority": 3,
      "from_category": "L2-APP",
      "to_category": "L2-INO",
      "amount": 150000,
      "from_rationale": "Additional scope reduction from L2-APP discretionary projects to fund innovation.",
      "to_rationale": "Innovation at 1% vs 5% benchmark is the largest relative gap. Even a modest injection signals commitment and enables structured experimentation.",
      "expected_impact": "Establishes an innovation sandbox program with 3-4 proof-of-concept tracks; creates pipeline for next planning cycle's CTB investments",
      "risk": "low",
      "risk_note": "Innovation budget requires governance structure to prevent diffusion. Recommend a dedicated innovation committee with a quarterly review gate."
    }
  ],
  "hold_steady": [
    {
      "category": "L2-INF",
      "rationale": "Cloud Migration is on-track and 15% under budget. No changes needed; monitor for continued performance."
    },
    {
      "category": "L2-PEO",
      "rationale": "People & Talent at 32% is in line with benchmark median of 33% and includes headcount supporting high-priority programs. Stable."
    },
    {
      "category": "L2-PRO",
      "rationale": "Process & Transformation at 5% is slightly above benchmark median (4%) but supports the ERP program. Monitor as ERP winds down."
    }
  ]
}
```

---

## Implementation Notes

### API Integration (`api/services/classification.py`)

```python
import anthropic
import json
from typing import Optional

client = anthropic.Anthropic()  # uses ANTHROPIC_API_KEY env var

MODEL = "claude-3-5-sonnet-20241022"

def classify_single(
    description: str,
    cost_center: str,
    gl_account: str,
    amount: str,
    custom_l4_codes: Optional[list] = None
) -> dict:
    """Classify a single expense line item."""
    system = build_system_prompt(custom_l4_codes)
    user = SINGLE_USER_TEMPLATE.format(
        description=description,
        cost_center=cost_center,
        gl_account=gl_account,
        amount=amount
    )
    response = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=system,
        messages=[{"role": "user", "content": user}]
    )
    return json.loads(response.content[0].text)


async def classify_plan(plan_summary: dict) -> dict:
    """Analyze a full classified plan and return insights."""
    response = client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=ANALYSIS_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": format_plan_analysis_prompt(plan_summary)}]
    )
    return json.loads(response.content[0].text)
```

### Error Handling

```python
import json
from anthropic import APIError

def safe_parse_classification(raw_text: str) -> dict:
    """Parse classification JSON with fallback for malformed responses."""
    try:
        # Strip markdown code fences if present
        text = raw_text.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "l1": "RTB",
            "l2": "L2-OPS",
            "l3": "L3-SFT",
            "l4": "L4-SFT-001",
            "confidence": 0.1,
            "reasoning": "Classification failed — manual review required."
        }
```

### Cost Estimates

| Prompt | Input Tokens (est.) | Output Tokens (est.) | Cost/Call |
|--------|--------------------|--------------------|-----------|
| Single classify | ~800 | ~150 | ~$0.003 |
| Batch (25 items) | ~2,500 | ~1,500 | ~$0.012 |
| Plan analysis | ~1,000 | ~800 | ~$0.005 |
| Reallocation | ~1,500 | ~1,000 | ~$0.007 |

_Based on Claude 3.5 Sonnet pricing. A 500-line-item plan costs approximately $0.24 to classify._

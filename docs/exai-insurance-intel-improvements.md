# exai-insurance-intel - Improvement Roadmap

## Current State Assessment

The repo is a solid **single-endpoint eval harness** — budget-capped, SQLite-cached, with smoke testing and a clean 9-cell notebook structure. It exercises `POST /search` with `category="people"` and `use_highlights=True`. That's roughly **10–15% of the Exa API surface area**. There's a lot of room to grow this into something that demonstrates mastery of the platform *and* becomes a genuine operational tool for the insurance/CAT-loss vertical.

---

## Part 1: Code & Architecture Improvements

### 1.1 — Modularize the Notebook into a Python Package

Right now everything lives in a single notebook. Extract the reusable pieces into a small package:

```
exai_search_demo/
├── __init__.py
├── client.py          # Exa wrapper (search, answer, find_similar, research)
├── cache.py           # SQLite cache logic (currently Cell 4)
├── budget.py          # Budget enforcement + cost tracking
├── config.py          # CONFIG dict + env loading
├── models.py          # Pydantic models for results, cost breakdowns
├── formatters.py      # Output formatting, redaction, markdown rendering
└── industry/
    ├── __init__.py
    ├── queries.py     # Domain-specific query suites (insurance, CAT law, etc.)
    └── schemas.py     # Structured output schemas for deep search
```

The notebook then becomes a thin orchestration layer that imports from the package. This also makes the smoke runner and any future CLI tools cleaner.

### 1.2 — Add Pydantic Models for Type Safety

The raw dict responses from Exa are hard to work with. Define models:

```python
class ExaResult(BaseModel):
    title: str
    url: str
    published_date: Optional[str]
    author: Optional[str]
    highlights: list[str] = []
    highlight_scores: list[float] = []
    summary: Optional[str] = None
    text: Optional[str] = None

class CostBreakdown(BaseModel):
    total: float
    neural_search: float = 0
    deep_search: float = 0
    content_text: float = 0
    content_highlight: float = 0
    content_summary: float = 0
```

### 1.3 — Improve the Test Suite

Currently there's a smoke runner. Expand to:

- **Unit tests** for cache logic (hit/miss/expiry), budget enforcement (hard stop behavior), cost estimation
- **Integration tests** (gated behind `--mode live`) that verify real API responses match expected schemas
- **Snapshot tests** for query suites — pin the expected result structure so regressions are obvious
- **pytest + pytest-cov** instead of raw nbclient, with a `conftest.py` that handles env/fixture setup

### 1.4 — Add a CLI Runner

```bash
# Run a single query
python -m exai_search_demo search "public adjuster Florida hurricane" --type deep --category people

# Run the full eval suite
python -m exai_search_demo eval --suite insurance --output results/

# Check budget
python -m exai_search_demo budget --run-id demo-2026-03
```

This is more useful for day-to-day exploration than opening Jupyter every time.

### 1.5 — Results Export & Visualization

- Export results to CSV/JSON for downstream analysis
- Add a simple Streamlit dashboard or HTML report generator that shows query-by-query results, cost breakdown, and relevance scoring over time
- Integrate with the Cytoscape/D3 visualization patterns you're already using in other projects — map relationship networks between professionals discovered via search

---

## Part 2: Exa API Features You're Not Using Yet

### 2.1 — Deep Search (`type="deep"` and `type="deep-reasoning"`)

This is Exa's most powerful search mode. It runs multiple queries in parallel and re-ranks results agentically. For the insurance vertical, this is huge — a query like "independent adjuster specializing in wind and hail damage claims Florida" benefits enormously from query expansion.

**What to add to the notebook:**

```python
# Deep search with automatic query expansion
result = exa.search(
    query="public adjuster catastrophe loss Florida",
    type="deep",
    num_results=10,
    contents={"highlights": True, "summary": True}
)

# Deep search with manual additionalQueries
result = exa.search(
    query="public adjuster catastrophe loss Florida",
    type="deep-reasoning",
    additional_queries=[
        "licensed public adjuster hurricane claims",
        "PA firm property insurance advocacy FL",
        "catastrophe response team independent adjuster"
    ],
    contents={"highlights": True, "summary": True}
)
```

**Cost:** $12/1k requests for deep, $15/1k for deep-reasoning (vs $7/1k for auto). Worth a dedicated eval cell comparing quality vs cost for your domain.

### 2.2 — Structured Output with `output_schema`

Deep search supports JSON schema output — meaning Exa returns structured data, not just links. This is perfect for building a database of professionals:

```python
result = exa.search(
    query="independent adjuster Florida catastrophe claims",
    type="deep",
    output_schema={
        "type": "object",
        "properties": {
            "professionals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "role": {"type": "string"},
                        "firm": {"type": "string"},
                        "state_licenses": {"type": "array", "items": {"type": "string"}},
                        "specializations": {"type": "array", "items": {"type": "string"}},
                        "notable_cases_or_experience": {"type": "string"}
                    }
                }
            }
        }
    }
)
```

This feeds directly into Neo4j/Life Graph as structured entities.

### 2.3 — `/answer` Endpoint (Cited Answers)

Instead of getting links and parsing them yourself, Exa generates a direct answer with citations. Use this for:

- Quick factual queries: "What is the Florida statute of limitations for property insurance claims?"
- Regulatory lookups: "What are the licensing requirements for public adjusters in Texas?"
- Case law summaries: "What was the ruling in Citizens Property Insurance v. Perdido Sun?"

```python
response = exa.answer(
    query="What is the appraisal clause dispute process in Florida homeowner insurance?",
    text=True
)
# Returns: answer text + cited sources
```

### 2.4 — `/findSimilar` Endpoint

Given a URL, find pages similar to it. Extremely useful for:

- **Competitor discovery:** Feed in Merlin Law Group's site, find similar plaintiff-side insurance law firms
- **Expert discovery:** Feed in a known public adjuster's LinkedIn profile, find similar professionals
- **Content discovery:** Feed in a good CAT-loss article, find more like it

```python
results = exa.find_similar(
    url="https://www.merlinlawgroup.com/",
    num_results=20,
    contents={"highlights": True}
)
```

### 2.5 — `/research` Endpoint (Agentic Research)

This is Exa's most advanced endpoint — it runs multi-step agentic search and returns structured reports. Perfect for:

- Deep dives into specific loss events (e.g., "Hurricane Ian insurance claim litigation outcomes")
- Market research on competitors in the PA space
- Regulatory landscape analysis across states

```python
research = exa.research.create(
    instructions="Research the current state of CAT loss litigation in Florida, "
                 "including major pending cases, key law firms representing "
                 "policyholders, and recent legislative changes affecting "
                 "property insurance claims.",
    output_schema={
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "key_firms": {"type": "array", "items": {"type": "string"}},
            "pending_cases": {"type": "array", "items": {"type": "string"}},
            "legislative_changes": {"type": "array", "items": {"type": "string"}}
        }
    }
)
```

### 2.6 — Websets (Large-Scale Continuous Search)

Websets are for when you want to build and maintain a dataset of entities over time. Think of it as a persistent search that keeps running and updating. For your use case:

- Build a webset of all public adjusters in Florida
- Build a webset of CAT-loss law firms nationwide
- Set up monitors to alert when new firms or professionals appear
- Webhook integration for real-time updates into your systems

This is the bridge between "eval notebook" and "production intelligence tool."

### 2.7 — Search Categories You're Missing

The `category` parameter has specialized modes:

| Category | Use For |
|----------|---------|
| `people` | Already using — LinkedIn profiles, professional pages |
| `company` | Find firms: PA companies, law firms, IA companies, umpire services |
| `news` | CAT event monitoring, litigation news, regulatory changes |
| `research paper` | Academic research on insurance disputes, climate risk models |
| `github` | Find open-source tools for claims processing, Xactimate integrations |

### 2.8 — Advanced Filtering

You're not yet using:

- **`includeDomains`** / **`excludeDomains`** — Focus on LinkedIn, state licensing boards, or exclude irrelevant sites
- **`startPublishedDate`** / **`endPublishedDate`** — Critical for news monitoring (e.g., "what's happened since Hurricane X made landfall")
- **`livecrawl`** — Force fresh crawl of pages instead of using cached index data

---

## Part 3: Insurance Industry Deep Dives

Here are the domain-specific query suites to build out:

### 3.1 — Public Adjusters (PA)

```python
PA_QUERIES = [
    # Discovery
    "licensed public adjuster Florida catastrophe claims",
    "public adjuster firm wind hail damage Texas",
    "public adjuster association board members",

    # Regulatory
    "Florida public adjuster licensing requirements DFS",
    "public adjuster fee limits by state",
    "public adjuster disciplinary actions Florida",

    # Competitive intelligence
    "largest public adjuster firms United States",
    "public adjuster M&A acquisitions 2024 2025",
]
```

### 3.2 — CAT Loss Law / First-Party Property Insurance Litigation

```python
CAT_LAW_QUERIES = [
    # Firm discovery
    "policyholder attorney property insurance bad faith Florida",
    "first-party property insurance litigation firm hurricane",
    "insurance coverage dispute attorney catastrophe claims",

    # Case law
    "Florida property insurance appraisal clause case law",
    "bad faith insurance claim jury verdict Florida 2024",
    "assignment of benefits AOB litigation Florida recent rulings",

    # Regulatory / legislative
    "Florida property insurance reform SB 2A impact",
    "one-way attorney fee abolition property insurance Florida",
    "Citizens Property Insurance depopulation program",
]
```

### 3.3 — Appraisers & Umpires

```python
APPRAISER_QUERIES = [
    "certified property damage appraiser Florida",
    "insurance appraisal umpire selection dispute resolution",
    "Xactimate certified appraiser catastrophe",
    "property damage appraisal panel umpire qualified neutral",
    "commercial property loss appraiser large loss",
    "appraisal vs mediation property insurance Florida",
]
```

### 3.4 — Independent Adjusters (IA)

```python
IA_QUERIES = [
    "independent adjuster CAT team deployment hurricane",
    "licensed independent adjuster Florida large loss",
    "independent adjuster firm staff augmentation carrier",
    "IA firm catastrophe response contract adjusters",
    "independent adjuster daily fee rates property claims",
    "Crawford and Company Sedgwick independent adjuster comparison",
]
```

### 3.5 — Adjacent Industries

```python
ADJACENT_QUERIES = [
    # Restoration / mitigation
    "water damage restoration contractor insurance preferred vendor",
    "emergency board-up service hurricane Florida certified",

    # Engineering / experts
    "forensic structural engineer hurricane damage expert witness",
    "roof consultant hail damage inspection certified",

    # Reinsurance / market
    "Florida property reinsurance market hardening 2025",
    "catastrophe bond pricing hurricane season outlook",

    # Technology
    "claims management software property insurance",
    "drone roof inspection insurance claims technology",
    "AI property damage assessment insurtech",
]
```

---

## Part 4: Presentation & Documentation Improvements

### 4.1 — README Upgrade

- Add a **Feature Matrix** showing which Exa endpoints are covered
- Add **Architecture Diagram** (Mermaid) showing data flow: Query → Cache Check → Exa API → Parse → Store → Display
- Add **Cost Comparison Table** across search types (auto vs deep vs deep-reasoning) for your domain
- Add badges: CI status, Python version, license

### 4.2 — Add a Demo Gallery

Create a `demos/` directory with focused, single-purpose notebooks:

```
demos/
├── 01_basic_search.ipynb           # People search (current notebook, cleaned up)
├── 02_deep_search_comparison.ipynb # Auto vs Deep vs Deep-Reasoning quality eval
├── 03_structured_output.ipynb      # Deep search with output_schema
├── 04_answer_endpoint.ipynb        # Cited answers for regulatory questions
├── 05_find_similar.ipynb           # Competitor/expert discovery from seed URLs
├── 06_research_endpoint.ipynb      # Agentic research for market intelligence
├── 07_news_monitoring.ipynb        # Date-filtered news search for CAT events
├── 08_domain_filtering.ipynb       # includeDomains/excludeDomains strategies
└── 09_neo4j_integration.ipynb      # Pipe structured results into graph DB
```

### 4.3 — CI/CD

- Add GitHub Actions workflow for smoke tests on every push (you have `.github/workflows/` already — make sure it runs `pytest` and the smoke runner)
- Add a scheduled workflow that runs the eval suite weekly with live API calls and commits the results as a report

### 4.4 — Security Hardening

- Validate that `.env` is in `.gitignore` (it is)
- Add `pre-commit` hooks: secrets scanning (`detect-secrets`), linting (`ruff`), type checking (`mypy`)
- Add SPDX headers to source files
- Document the ZDR (Zero Data Retention) option for sensitive queries — Exa supports this natively and it's relevant for insurance data

---

## Part 5: Integration Opportunities

### 5.1 — Feed into Life Graph / Neo4j

The structured output from deep search and websets can populate your Life Graph directly:

- **People nodes:** PAs, attorneys, IAs, appraisers, umpires
- **Firm nodes:** Law firms, PA companies, IA firms, restoration companies
- **Event nodes:** Hurricanes, legislative changes, case rulings
- **Relationships:** WORKS_AT, LICENSED_IN, SPECIALIZES_IN, INVOLVED_IN

### 5.2 — Feed into CAT Loss Case War Room

The `/answer` endpoint and `/research` endpoint are natural upgrades to the War Room notebook:

- Use `/answer` for quick case law lookups during demand letter drafting
- Use `/research` for comprehensive carrier playbook analysis
- Use `/findSimilar` starting from a known favorable ruling to find analogous cases

### 5.3 — Feed into Lead Gen Workflow

Your existing Exa-based lead gen targets Ubiquiti installers. The same patterns work for:

- Finding restoration contractors who might need PA referrals
- Finding law firms that might need expert witnesses
- Finding IA firms hiring for CAT season deployment

### 5.4 — MCP Server Integration

Exa has an official MCP server. Connect it to Claude Code / Claude Desktop for live search during development:

```json
{
  "mcpServers": {
    "exa": {
      "command": "npx",
      "args": ["-y", "exa-mcp-server", "--tools=web_search_exa,find_similar_exa,answer_with_citations_exa,deep_research_exa,linkedin_search,company_research"],
      "env": { "EXA_API_KEY": "your-key" }
    }
  }
}
```

---

## Suggested Priority Order

| Priority | Task | Effort | Impact |
|----------|------|--------|--------|
| 1 | Add `/answer` endpoint demo | Low | High — immediate utility for regulatory lookups |
| 2 | Add Deep Search comparison cell | Low | High — shows quality uplift for your domain |
| 3 | Add structured output (`output_schema`) | Medium | High — feeds directly into Neo4j pipeline |
| 4 | Build out industry query suites (Part 3) | Medium | High — demonstrates deep domain knowledge |
| 5 | Add `/findSimilar` demo | Low | Medium — great for competitor/expert discovery |
| 6 | Modularize into Python package | Medium | Medium — pays off over time |
| 7 | Add `/research` endpoint demo | Medium | High — most impressive capability |
| 8 | Integrate with Neo4j pipeline | High | Very High — connects to Life Graph vision |
| 9 | Explore Websets for persistent monitoring | High | Very High — production-grade intelligence |
| 10 | Add Streamlit dashboard | Medium | Medium — nice demo, not critical |

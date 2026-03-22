# exai-insurance-intel Rebuild Review

## TL;DR
If we were rebuilding this today, we would keep the **minimal, notebook-first evaluation loop** and safety framing, but we would split orchestration logic into a tiny Python package and treat the notebook as a presentation layer. That gives us repeatability, easier A/B experiments, and cleaner migration from demo to pilot.

## What We Would Keep (and Why)

1. **Single primary flow for first-run success**
   - The repository's emphasis on one core notebook and a fixed 9-cell flow is excellent for reducing onboarding friction.
   - The smoke/live/auto runner pattern is practical for cost-safe validation.

2. **Cost and caching as first-class concerns**
   - Explicit budget enforcement and sqlite-backed cache are exactly right for API-backed prototyping.
   - The run-scoped view of spend is a strong practical design choice for demos and internal reviews.

3. **Clear safety posture**
   - Guardrails focused on public/professional info, no harvesting, and human review are explicit and operationally useful.

## What We Would Change if Rebuilding From Scratch

### 1) Reframe the architecture: notebook = UI, package = engine

Move reusable logic into a small package (for example `src/exa_demo/`) and keep the notebook thin:

- `config.py`: typed config and defaults
- `client.py`: Exa request construction + response normalization
- `cache.py`: sqlite cache + schema migration helpers
- `budget.py`: run-scoped budget accounting
- `eval.py`: deterministic evaluation suite + scorecards
- `report.py`: tabular summaries and cost projections

**Why this matters**
- Enables unit tests and contract tests without executing the whole notebook.
- Allows a CLI and notebook to share identical logic.
- Makes future web UI integration straightforward.

### 2) Standardize the data model early

Define a canonical result schema (e.g., dataclass/pydantic model) for:
- query input
- result candidate
- credibility/quality annotations
- cost metadata
- cache provenance (`cache_hit`, hash, run id)

**Non-obvious payoff**: once shape is stable, you can compare model versions, query templates, and ranking strategies with less glue code.

### 3) Upgrade the evaluation harness from "demo batch" to "experiment loop"

Introduce an `experiments/` folder with immutable artifacts per run:
- `config.json`
- `queries.jsonl`
- `results.jsonl`
- `summary.json`

Add a command like:
```bash
python -m exa_demo.run --profile cat_insurance_v1 --mode smoke
```

**Why**
- Makes decision history auditable.
- Supports regression checks: "did this change improve precision or only increase cost?"

### 4) Separate trust and utility scoring

Current demos often blend "useful result" with "credible result." Rebuild with explicit dimensions:
- relevance score
- credibility score
- actionability score
- policy/safety pass flag

**Non-obvious payoff**: You can optimize different use-cases (fast triage vs high-confidence analyst workflows) without reworking the pipeline.

### 5) Add a tiny benchmark set with expected outcomes

Create a curated benchmark of 20-50 representative queries with expected signal patterns and failure cases.

Use it in CI smoke mode to catch behavior drift in:
- query templates
- normalization logic
- cost estimators

## Refactor Roadmap (Pragmatic)

### Phase 1: No-risk extraction (1 day)
- Lift config, cache, budget, and request wrapper into modules.
- Keep notebook outputs unchanged.
- Add tests for cache key stability and budget accounting.

### Phase 2: Evaluation discipline (1-2 days)
- Add benchmark queries and JSONL outputs.
- Add "before vs after" summary report generation.
- Add failure taxonomy in output (`no_results`, `low_confidence`, `off_domain`, etc.).

### Phase 3: Demo polish (1 day)
- Add one-command run script (`make demo` or python CLI).
- Add generated markdown report for stakeholders.
- Add optional frontend panel or static HTML export for visual storytelling.

## Repurpose Opportunities (to make this a killer demo)

1. **Executive view**: lead with KPI cards (coverage, precision proxy, cost/query, cache hit rate).
2. **Operator view**: include per-query diagnostics and why a result passed/failed.
3. **Risk view**: show explicit policy/safety checks and redaction outcomes.
4. **Scale view**: include projections for 100, 1k, and 10k queries with confidence intervals.

## "Would We Build It the Same Way Again?"

**Yes** on:
- minimal surface area
- notebook-first onboarding
- explicit caching + budget + guardrails

**No** on:
- keeping core logic trapped in notebook cells
- lacking typed intermediate schema
- treating evaluation outputs as ephemeral instead of versioned artifacts

The best v2 keeps the current simplicity while introducing a small amount of engineering structure so the demo can graduate into an internal pilot without rewrite churn.

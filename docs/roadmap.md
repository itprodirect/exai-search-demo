# Exa Search Demo Roadmap

## Summary

This roadmap merges the current-state observations from [rebuild_review.md](./rebuild_review.md) and the opportunity set in [exai-search-demo-improvements.md](./exai-search-demo-improvements.md).

It is intentionally phased from the actual repo baseline as of March 10, 2026, not from a hypothetical notebook-only starting point.

Status buckets:

- `Done`: already present in the repository
- `Next`: ready for implementation after this documentation/backlog pass
- `Later`: valuable follow-on work that depends on earlier foundation
- `Hold/Explore`: worth preserving, but not yet decision-complete enough to commit as active backlog

## Phase 0 - Completed Baseline

These capabilities are already present and should not be re-scoped as future work.

| Item | Goal | Why it matters | Current status | Dependencies | Success criteria | GitHub issue |
| --- | --- | --- | --- | --- | --- | --- |
| Package extraction | Keep notebook orchestration thin by moving reusable logic into `src/exa_demo` | Enables testing and future CLI reuse | `Done` | None | Notebook imports package modules for config, cache, client, evaluation, reporting, and safety | N/A |
| Benchmark fixture | Store reusable CAT-loss benchmark queries outside the notebook | Makes evaluation inputs testable and reusable | `Done` | None | `benchmarks/insurance_cat_queries.json` is loaded by code and tests | N/A |
| Test baseline | Validate cache, cost model, evaluation, and safety helpers | Protects the current harness while the roadmap expands | `Done` | Package extraction | `pytest -q` passes | N/A |
| Smoke CI | Run a no-network notebook smoke test on push and PR | Preserves first-run safety and regression detection | `Done` | Notebook and smoke runner | `.github/workflows/ci.yml` executes smoke mode successfully | N/A |
| Cache, budget, safety framing | Keep cost, caching, and public-info guardrails first-class | Preserves the demo's practical and safe operating model | `Done` | None | Budget cap, sqlite cache, and redaction/safety helpers remain part of the default flow | N/A |

## Phase 1 - Foundation

These items establish the engineering substrate needed before deeper API coverage and richer demos.

| Roadmap item | Goal | Why it matters | Current status | Dependencies | Success criteria | GitHub issue |
| --- | --- | --- | --- | --- | --- | --- |
| Typed models | Add normalized models in `src/exa_demo/models.py` for Exa results, cost metadata, and experiment artifacts | Stabilizes interfaces between notebook, CLI, evaluation, and reports | `Done` | Phase 0 baseline | Shared typed models are used by package code and tests for normalization and reporting | [#2](https://github.com/itprodirect/exai-search-demo/issues/2) |
| Installable package + CLI | Add package metadata and planned CLI commands `python -m exa_demo search`, `eval`, and `budget` | Makes the harness runnable without opening Jupyter and supports repeatable operations | `Done` | Typed models | Local install and documented CLI entrypoints work against existing core logic | [#3](https://github.com/itprodirect/exai-search-demo/issues/3) |
| Experiment artifact logging | Persist immutable run artifacts under `experiments/<run-id>/` with `config.json`, `queries.jsonl`, `results.jsonl`, and `summary.json` | Creates an auditable decision history for evaluation changes | `Done` | Typed models, CLI/package installability | Each run emits a complete artifact bundle that can be compared later | [#4](https://github.com/itprodirect/exai-search-demo/issues/4) |
| Evaluation taxonomy + before/after reporting | Add richer failure taxonomy and comparison reporting | Separates relevance, credibility, and actionability so future experiments are measurable | `Done` | Experiment artifacts | Reports can compare runs and classify failures such as `no_results`, `off_domain`, and `low_confidence` | [#5](https://github.com/itprodirect/exai-search-demo/issues/5) |

## Phase 2 - Exa API Coverage

These items expand the repo from a people-search harness into a broader Exa capability demo for insurance and CAT-loss research.

| Roadmap item | Goal | Why it matters | Current status | Dependencies | Success criteria | GitHub issue |
| --- | --- | --- | --- | --- | --- | --- |
| `/answer` endpoint demo | Add cited-answer workflows for fast regulatory and case-law lookups | Delivers immediate utility for research-style questions | `Done` | Typed models, reporting | Repo includes a documented demo or workflow for `/answer` with cited outputs and evaluation hooks | [#7](https://github.com/itprodirect/exai-search-demo/issues/7) |
| Deep vs deep-reasoning comparison | Compare `auto`, `deep`, and `deep-reasoning` quality/cost tradeoffs for domain queries | Quantifies whether higher-cost search modes are worth using in this vertical | `Done` | Experiment artifacts, reporting | Repeatable comparison output shows quality and spend deltas across search types | [#8](https://github.com/itprodirect/exai-search-demo/issues/8) |
| Structured output with `output_schema` | Extract structured entities directly from deep search responses | Enables downstream graph, analytics, and dataset workflows | `Next` | Typed models, deep-search support | Structured outputs are validated, stored, and demoed from a supported query set | [#9](https://github.com/itprodirect/exai-search-demo/issues/9) |
| `/findSimilar` demo | Add seed-URL discovery for competitor, expert, and content expansion | Broadens discovery workflows beyond keyword search | `Later` | CLI or notebook demo conventions | Repo includes a reproducible `/findSimilar` workflow and evaluation framing | [#10](https://github.com/itprodirect/exai-search-demo/issues/10) |
| `/research` demo | Add agentic research output for market and regulatory reports | Shows the most advanced report-generation capability in the Exa stack | `Later` | Typed models, artifact logging | Repo includes a documented research workflow and structured output/report handling | [#11](https://github.com/itprodirect/exai-search-demo/issues/11) |

## Phase 3 - Domain Coverage and Productization

These items extend the technical baseline into a more useful vertical demo for insurance/CAT-loss intelligence.

| Roadmap item | Goal | Why it matters | Current status | Dependencies | Success criteria | GitHub issue |
| --- | --- | --- | --- | --- | --- | --- |
| Insurance/CAT query suites | Expand benchmark and demo suites for public adjusters, CAT law, appraisers, independent adjusters, and adjacent industries | Demonstrates domain depth instead of a narrow people-search slice | `Next` | Experiment artifacts, evaluation taxonomy | Query suites are versioned, documented, and runnable through the shared harness | [#13](https://github.com/itprodirect/exai-search-demo/issues/13) |
| Export/report outputs + demo gallery | Add CSV/JSON/report exports and a focused demo-gallery structure | Improves stakeholder review and repeatable presentation | `Later` | Experiment artifacts, API coverage demos | Repo can emit reusable outputs and has documented demo entrypoints by use case | [#14](https://github.com/itprodirect/exai-search-demo/issues/14) |
| CI/security/integration follow-ons | Extend CI coverage, pre-commit/security checks, and document concrete integration boundaries | Keeps future expansion disciplined and safer to operate | `Later` | Foundation and reporting work | CI/test/security posture expands without weakening the current safe-default workflow | [#16](https://github.com/itprodirect/exai-search-demo/issues/16) |

## Phase 4 - Documentation, Governance, and Repo Operations

This phase governs how roadmap work is tracked and how delivery history is preserved.

| Roadmap item | Goal | Why it matters | Current status | Dependencies | Success criteria | GitHub issue |
| --- | --- | --- | --- | --- | --- | --- |
| Governance and delivery tracking | Maintain roadmap, issue tracker, ADRs, and session notes as durable project history | Preserves why decisions were made and what changed each session | `Next` | None | Docs and GitHub stay in sync for roadmap items and active work | [#17](https://github.com/itprodirect/exai-search-demo/issues/17) |
| README alignment and top-level navigation | Keep the README synchronized with the actual repo baseline, roadmap, and governance docs | Makes the repo entry point accurate for future sessions and contributors | `Next` | Governance conventions | README links, feature framing, and architecture context stay aligned with the roadmap | [#18](https://github.com/itprodirect/exai-search-demo/issues/18) |

## Planned Interfaces and Contracts

These interfaces are intentionally documented now so future implementation work has a stable target.

### CLI contract

Planned commands:

```powershell
python -m exa_demo search "public adjuster Florida hurricane"
python -m exa_demo answer "What is the Florida appraisal clause dispute process?"
python -m exa_demo eval --suite insurance
python -m exa_demo compare-search-types --suite forensic_and_damage_engineering --baseline-type deep --candidate-type deep-reasoning
python -m exa_demo budget --run-id demo-2026-03
```

### Model contract

Planned module:

```text
src/exa_demo/models.py
```

Planned responsibilities:

- normalized Exa result records
- cost breakdown and ledger records
- experiment artifact schemas
- any structured-output entity models needed by deep search flows

### Experiment artifact contract

Planned run layout:

```text
experiments/<run-id>/config.json
experiments/<run-id>/queries.jsonl
experiments/<run-id>/results.jsonl
experiments/<run-id>/summary.json
```

## Hold / Explore

These are preserved as future exploration themes, but they are not committed backlog items yet because they need sharper acceptance criteria first.

- Neo4j/Life Graph integration
- War Room integration patterns
- Websets / persistent monitoring
- MCP server integration
- Streamlit or richer visualization layers beyond report exports

## Source Inputs

- [docs/exai-search-demo-improvements.md](./exai-search-demo-improvements.md)
- [docs/rebuild_review.md](./rebuild_review.md)
- Current repository code, tests, CI, and README baseline observed on March 10, 2026




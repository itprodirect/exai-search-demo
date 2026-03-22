# Session: Phase 1 Foundation Start

- Date: 2026-03-10
- Participants: Codex, repository owner
- Related roadmap items: [docs/roadmap.md](../roadmap.md), [#2](https://github.com/itprodirect/exai-insurance-intel/issues/2), [#4](https://github.com/itprodirect/exai-insurance-intel/issues/4)
- Related ADRs: [ADR-0001-roadmap-governance.md](../adr/ADR-0001-roadmap-governance.md)

## Context

Start Phase 1 implementation with the two foundation items that unlock the rest of the roadmap: normalized typed models and durable experiment artifact logging.

## Repo Facts Observed

- The notebook already used shared package modules for cache, client, evaluation, reporting, and safety logic.
- `evaluate_batch_queries()` was the cleanest integration point for per-query structured records because the notebook already routes all benchmark execution through it.
- The notebook had no existing run-artifact persistence, so `experiments/<RUN_ID>/` needed a direct notebook hook to be useful immediately.

## Decisions Made

- Use standard-library `dataclass` models instead of adding a new runtime dependency for this first typed-model pass.
- Keep `evaluate_batch_queries()` backward compatible by preserving its `DataFrame` return value and adding an optional per-query recorder hook.
- Write experiment artifacts from the current notebook flow so the existing smoke runner validates the artifact pipeline end-to-end.
- Reset `queries.jsonl`, `results.jsonl`, and `summary.json` for a reused `RUN_ID` so reruns do not silently append duplicate records.

## Issues Opened or Updated

- [#2](https://github.com/itprodirect/exai-insurance-intel/issues/2): implemented `src/exa_demo/models.py` and normalized query-evaluation records.
- [#4](https://github.com/itprodirect/exai-insurance-intel/issues/4): implemented `src/exa_demo/artifacts.py` and notebook-backed `experiments/<RUN_ID>/` output.
- [#1](https://github.com/itprodirect/exai-insurance-intel/issues/1): foundation epic now has active implementation underneath it.

## Docs Touched

- [docs/roadmap.md](../roadmap.md)
- [docs/issue-tracker.md](../issue-tracker.md)
- [docs/sessions/2026-03-10-phase1-foundation-start.md](./2026-03-10-phase1-foundation-start.md)
- [README.md](../../README.md)

## Code Touched

- [src/exa_demo/models.py](../../src/exa_demo/models.py)
- [src/exa_demo/artifacts.py](../../src/exa_demo/artifacts.py)
- [src/exa_demo/evaluation.py](../../src/exa_demo/evaluation.py)
- [src/exa_demo/__init__.py](../../src/exa_demo/__init__.py)
- [exa_people_search_eval.ipynb](../../exa_people_search_eval.ipynb)
- [tests/test_evaluation.py](../../tests/test_evaluation.py)
- [tests/test_models.py](../../tests/test_models.py)
- [tests/test_artifacts.py](../../tests/test_artifacts.py)

## Tests and Checks Run

- `pytest -q`
- `python scripts/run_notebook_smoke.py --mode smoke --timeout 180`
- Verified artifact output under `experiments/20260310T033256Z/`

## Outcome

- Added typed result, cost, query-evaluation, and experiment-summary models.
- Added artifact writing for config, query, result, and summary files under `experiments/<RUN_ID>/`.
- Integrated artifact recording into the notebook batch flow without breaking the existing `DataFrame`-based evaluation path.

## Next-Session Handoff

- Decide whether to close or further refine [#2](https://github.com/itprodirect/exai-insurance-intel/issues/2) and [#4](https://github.com/itprodirect/exai-insurance-intel/issues/4) after review.
- Continue Phase 1 with [#3](https://github.com/itprodirect/exai-insurance-intel/issues/3) CLI/installability and [#5](https://github.com/itprodirect/exai-insurance-intel/issues/5) richer evaluation reporting.
- If the artifact schema changes, keep [README.md](../../README.md) and [docs/roadmap.md](../roadmap.md) aligned.

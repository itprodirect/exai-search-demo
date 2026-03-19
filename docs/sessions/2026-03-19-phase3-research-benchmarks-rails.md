# Session: Phase 3 Research, Benchmarks, and Rails

- Date: 2026-03-19
- Participants: User, Codex, subagents
- Related roadmap items: `#11`, `#13`, `#16`, `#17`
- Related ADRs: none

## Context

Continue the slice-based delivery pattern from March 18 with parallel work across product surface, domain coverage, and repo rails, while keeping commits and pushes aligned to stable checkpoints.

## Repo Facts Observed

- The repo started this session on `main` with yesterday's Phase 2 API slices already shipped through `/answer`, `compare-search-types`, `structured-search`, and `/findSimilar`.
- Two untracked experiment runs were present under `experiments/` and treated as disposable runtime artifacts rather than source-controlled deliverables.
- The next clean product slice in the roadmap was `/research`, while domain-suite expansion and CI hardening were both already marked as active follow-on work.

## Decisions Made

- Keep `/research` tightly scoped as a standalone workflow demo rather than trying to force it into ranked-search evaluation or notebook integration in the same slice.
- Expand the benchmark contract before adding more domain coverage so suites can carry metadata and mixed string/object query entries without breaking the existing CLI.
- Add a lightweight static quality gate now with `ruff` and pre-commit parity, but defer broader lint/type/security expansion until after the new rails have burned in.

## Docs Touched

- `README.md`
- `docs/roadmap.md`
- `docs/issue-tracker.md`
- `docs/sessions/2026-03-19-phase3-research-benchmarks-rails.md`

## Tests and Checks Run

- `pytest -q tests\test_evaluation.py` -> passed for the richer benchmark contract and new suite coverage.
- `python -m ruff check .` -> passed after adding the new static quality gate.
- `pytest -q tests\test_client.py tests\test_models.py tests\test_artifacts.py tests\test_cli.py` -> passed for the `/research` workflow slice.

## Outcome

- Completed the repo-ops hardening slice in commit `d321169`:
  - added `ruff` and `pre-commit` to the dev toolchain
  - wired `ruff` into CI before pytest
  - added `.pre-commit-config.yaml` for local hook parity
- Completed the domain benchmark contract slice in commit `a99c23a`:
  - added support for object-shaped benchmark suites with suite metadata and mixed query-entry formats
  - expanded the benchmark fixture with `restoration_and_mitigation`, `carrier_tpa_and_vendor_ecosystem`, and `regulatory_legislative_and_market_news`
  - preserved backward compatibility for legacy list-based suites and fixtures
- Completed the next product slice for `#11`:
  - added a standalone `research` CLI workflow with smoke/live runtime handling, cache integration, `research.json` artifact output, and focused client/model/CLI coverage
- Reconciled README, roadmap, and issue-tracker docs so the repo entry point matches the shipped product surface and current backlog state.

## Next-Session Handoff

- The remaining high-alpha productization follow-on is to decide whether `research` should stay as a raw report workflow or grow a rendered markdown/export path under `#14`.
- The new lint rail is intentionally narrow; widening it to tests, notebooks, and the remaining excluded modules should be handled as separate cleanup slices.

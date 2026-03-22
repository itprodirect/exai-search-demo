# Session: Phase 1 Evaluation Taxonomy and Before/After Reporting

- Date: 2026-03-11
- Participants: Codex, repository owner
- Related roadmap items: [docs/roadmap.md](../roadmap.md), [#5](https://github.com/itprodirect/exai-insurance-intel/issues/5), [#1](https://github.com/itprodirect/exai-insurance-intel/issues/1)
- Related ADRs: [ADR-0001-roadmap-governance.md](../adr/ADR-0001-roadmap-governance.md)

## Context

Deliver the remaining Phase 1 task for richer evaluation taxonomy and before/after reporting so experiment artifacts can support measurable run-to-run comparisons.

## Repo Facts Observed

- `#2`, `#3`, and `#4` were already implemented and pushed on `main` at commit `cbb7088`.
- The repo had one in-progress local notebook edit and one untracked experiment artifact directory at session start.
- Existing artifact bundles already persisted `config.json`, `queries.jsonl`, `results.jsonl`, and `summary.json`, but no explicit failure taxonomy or run-comparison output existed.

## Decisions Made

- Add taxonomy dimensions directly to query-level evaluation records: relevance, credibility, actionability, confidence, and normalized failure reasons.
- Keep failure taxonomy simple and explicit for now: `no_results`, `off_domain`, `low_confidence`.
- Implement before/after reporting as an eval command option (`--compare-to-run-id`) rather than a separate command, so a single eval invocation can emit current metrics plus deltas.
- Store taxonomy and comparison snapshots in `summary.json` under `extra` while also promoting key confidence/failure rates to typed top-level summary fields.

## Issues Opened or Updated

- [#5](https://github.com/itprodirect/exai-insurance-intel/issues/5): implemented end-to-end with taxonomy scoring, failure classification, and baseline-vs-candidate comparison reporting.
- [#1](https://github.com/itprodirect/exai-insurance-intel/issues/1): foundation epic remains in progress, with the final Phase 1 task now implemented.

## Docs Touched

- [docs/roadmap.md](../roadmap.md)
- [docs/issue-tracker.md](../issue-tracker.md)
- [docs/sessions/2026-03-11-phase1-eval-taxonomy-reporting.md](./2026-03-11-phase1-eval-taxonomy-reporting.md)
- [README.md](../../README.md)

## Code Touched

- [src/exa_demo/evaluation.py](../../src/exa_demo/evaluation.py)
- [src/exa_demo/models.py](../../src/exa_demo/models.py)
- [src/exa_demo/reporting.py](../../src/exa_demo/reporting.py)
- [src/exa_demo/artifacts.py](../../src/exa_demo/artifacts.py)
- [src/exa_demo/cli.py](../../src/exa_demo/cli.py)
- [src/exa_demo/__init__.py](../../src/exa_demo/__init__.py)
- [tests/test_evaluation.py](../../tests/test_evaluation.py)
- [tests/test_models.py](../../tests/test_models.py)
- [tests/test_artifacts.py](../../tests/test_artifacts.py)
- [tests/test_cli.py](../../tests/test_cli.py)
- [tests/test_reporting.py](../../tests/test_reporting.py)

## Tests and Checks Run

- `pytest -q` (passed: `19 passed`)

## Outcome

- Added query-level taxonomy scoring and failure tagging to evaluation outputs and typed models.
- Added reporting helpers for taxonomy aggregation and before/after comparison against a baseline artifact run.
- Extended CLI eval flow with `--compare-to-run-id` and persisted taxonomy/comparison snapshots into run summaries.
- Expanded tests to cover taxonomy behavior, artifact persistence of new metrics, and comparison reporting.

## Next-Session Handoff

- Close [#5](https://github.com/itprodirect/exai-insurance-intel/issues/5) in GitHub after review of this commit.
- Decide whether [#1](https://github.com/itprodirect/exai-insurance-intel/issues/1) should now be closed or moved to follow-on hardening tasks.
- Consider adding a markdown/HTML exporter for the comparison payload to support stakeholder-readable run reports.

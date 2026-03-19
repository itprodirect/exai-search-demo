# Session: Phase 3 Export Outputs and Smoke Rails

- Date: 2026-03-19
- Participants: User, Codex, subagents
- Related roadmap items: `#14`, `#16`, `#17`
- Related ADRs: none

## Context

Continue the bounded-slice delivery pattern by taking the next additive productization step: export-oriented artifacts and report outputs for the shipped workflows, while tightening the smoke runner rails without changing the core harness contracts.

## Repo Facts Observed

- The repo started this session with `search`, `answer`, `research`, `structured-search`, `find-similar`, and `compare-search-types` already shipped on `main`.
- The docs-only demo gallery slice landed in parallel during the session and was reconciled into the current branch state before close-out.
- The main verification baseline was clean at session start: `pytest -q` and `python -m ruff check .` both passed.

## Decisions Made

- Keep export/report outputs additive rather than changing the existing `summary.json`, `results.jsonl`, or workflow-specific JSON contracts.
- Add a lightweight artifact manifest so downstream tools can discover what each run emitted without inferring from workflow name alone.
- Treat the notebook smoke runner noise as a rail-hardening issue, but only take the smallest safe improvement in this session rather than forcing a risky deeper fix.

## Docs Touched

- `README.md`
- `docs/demo-gallery.md`
- `docs/roadmap.md`
- `docs/issue-tracker.md`
- `docs/sessions/2026-03-19-phase3-export-outputs-and-smoke-rails.md`

## Tests and Checks Run

- `pytest -q tests\test_artifacts.py tests\test_reporting.py tests\test_cli.py` -> passed for the additive export/report slice.
- `pytest -q tests\test_artifacts.py tests\test_reporting.py tests\test_cli.py tests\test_scripts.py` -> passed after the smoke-runner rail follow-up.
- `pytest -q` -> passed at session end with `74 passed`.
- `python -m ruff check .` -> passed at session end.
- `python scripts/run_notebook_smoke.py --mode smoke` -> passed and completed successfully without the earlier extra teardown noise.

## Outcome

- Completed the export/report output slice:
  - experiment runs now write `manifest.json` describing emitted artifacts
  - eval runs now emit additive `results.csv` exports
  - comparison runs now emit additive `comparison.json` and `grouped_query_outcomes.csv` exports
  - research runs now emit a human-readable `research.md` companion artifact alongside `research.json`
- Completed the focused demo-gallery docs slice in parallel:
  - added a command-first gallery doc covering discovery, research, extraction, and comparison workflows
  - linked the gallery from the README so it becomes the top-level entrypoint for use-case navigation
- Completed a small rail-hardening follow-up:
  - set `JUPYTER_PLATFORM_DIRS=1` in the smoke runner to make the runtime environment more explicit and reduce warning noise
- Reconciled roadmap and issue-tracker state so `#14` reflects the shipped export/report outputs and demo-gallery work.

## Next-Session Handoff

- The next clean rail-hardening move is to decide whether lint scope should expand further or whether live/manual integration boundaries should be documented more explicitly under `#16`.
- If export depth needs to grow again, the next additive move would be richer summary tables or stakeholder-oriented report bundles, not changes to the core JSON/JSONL contracts.

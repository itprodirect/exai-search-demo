# Session: Phase 3 Manual Live Validation

- Date: 2026-03-19
- Participants: User, Codex
- Related roadmap items: `#16`, `#17`
- Related ADRs: none

## Context

Add a bounded manual live-validation path so the repo can exercise real Exa API behavior without changing the smoke-first default operating model.

## Repo Facts Observed

- The repo started this session with smoke CI, lint, pytest, export artifacts, and explicit smoke-vs-live artifact metadata already in place.
- The remaining operational gap was no repeatable manual path for validating the real API surface across the shipped CLI workflows.
- The right scope was a small representative workflow set, not scheduled automation or automatic live runs.

## Decisions Made

- Keep live validation manual-only via GitHub Actions `workflow_dispatch`.
- Put the validation logic in a versioned Python script so it can be tested locally in smoke mode and reused by the workflow.
- Make comparison validation opt-in because it is materially more expensive than the default endpoint checks.

## Docs Touched

- `README.md`
- `docs/demo-gallery.md`
- `docs/integration-boundaries.md`
- `docs/issue-tracker.md`
- `docs/sessions/2026-03-19-phase3-manual-live-validation.md`

## Tests and Checks Run

- `pytest -q tests\test_scripts.py` -> passed for the new live-validation script.
- `python .\scripts\run_live_validation.py --mode smoke` -> passed locally and wrote a bounded validation summary plus workflow artifacts.
- `pytest -q` -> passed at session end.
- `python -m ruff check .` -> passed at session end.
- `python scripts/run_notebook_smoke.py --mode smoke` -> passed at session end.

## Outcome

- Added `scripts/run_live_validation.py` as the bounded runner for representative workflow validation through the real CLI surface.
- Added `.github/workflows/live-validation.yml` as a manual GitHub Actions workflow for smoke or live validation, with optional comparison coverage and artifact upload.
- Added a checked-in schema fixture for structured-search validation at `assets/live_validation_schema.json`.
- Updated docs so the manual live-validation path is discoverable from README, the demo gallery, and the integration-boundaries guide.

## Next-Session Handoff

- The next `#16` move, if needed, is tighter spend/secret policy around the manual workflow or selective live assertions on returned payload shape.
- Keep this workflow manual and bounded unless there is a strong reason to introduce scheduled live validation later.

# Session: Phase 3 Integration Boundaries and Lint Expansion

- Date: 2026-03-19
- Participants: User, Codex
- Related roadmap items: `#16`, `#17`
- Related ADRs: none

## Context

Take the next rail-hardening slice after export outputs by making the smoke-vs-live execution contract explicit in artifacts and docs, then widen lint coverage only where the repo already passes cleanly.

## Repo Facts Observed

- The repo started this session with the main workflow surface and additive export artifacts already shipped on `main`.
- `ruff` already passed against `tests/` and `src/exa_demo/evaluation.py` even though the configured lint scope had not been widened yet.
- The next clean move for `#16` was to codify execution boundaries rather than add more product surface.

## Decisions Made

- Keep the smoke-vs-live contract additive by recording runtime metadata in existing artifacts instead of inventing a new control plane.
- Widen lint scope only to files that already pass so the rail gets stronger without creating cleanup churn.
- Document smoke/live boundaries explicitly and keep CI smoke-only by default.

## Docs Touched

- `README.md`
- `docs/demo-gallery.md`
- `docs/integration-boundaries.md`
- `docs/issue-tracker.md`
- `docs/sessions/2026-03-19-phase3-integration-boundaries-and-lint-expansion.md`

## Tests and Checks Run

- `python -m ruff check tests`
- `python -m ruff check src\exa_demo\evaluation.py`
- `pytest -q tests\test_artifacts.py tests\test_cli.py`
- `pytest -q` -> passed at session end
- `python -m ruff check .` -> passed at session end

## Outcome

- Recorded runtime execution metadata in run artifacts so reviewers can tell whether a bundle came from smoke or live execution.
- Widened the configured lint surface to include `tests/` and `src/exa_demo/evaluation.py`, and expanded the pre-commit hook scope to include tests.
- Added explicit documentation for smoke-vs-live boundaries, artifact expectations, CI scope, and manual live validation rules.

## Next-Session Handoff

- The next `#16` move is either a manual live-validation workflow or tighter spend/secrets rules around live checks.
- Avoid broad refactors; the current high-value path is still disciplined hardening, not redesign.

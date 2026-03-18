# Session: Phase 2 Parallel Slice Delivery

- Date: 2026-03-18
- Participants: User, Codex, subagents
- Related roadmap items: `#7`, `#8`, `#9`, `#13`, `#16`, `#17`
- Related ADRs: none

## Context

Kick off a slice-based implementation session that keeps code, tests, docs, commits, and pushes synchronized after each completed slice.

## Repo Facts Observed

- The repo started this session clean on `main`.
- CI in [ci.yml](C:\Users\user\Desktop\exai-search-demo\.github\workflows\ci.yml) only ran the notebook smoke workflow.
- `pytest -q` passed locally at session start with 20 tests.
- The current harness already had CLI coverage for `search`, `eval`, and `budget`, but no direct test coverage for the helper scripts under `scripts/`.

## Decisions Made

- Deliver work in bounded slices and keep docs/tests/commits/pushes aligned per slice instead of batching all changes at the end.
- Take CI and test hardening first so later API-surface work lands on safer rails.
- Treat generated experiment artifacts from smoke validation as disposable runtime output, not source-controlled session deliverables.

## Issues Opened or Updated

- Closed completed GitHub issues after reconciling tracker state with the shipped repo surface: `#1`, `#2`, `#3`, `#4`, `#5`, and `#8`.
- `#7 Add /answer endpoint demo and cited-answer evaluation`: moved from `Implemented and pushed` to `Closed` after the repo tracker was reconciled with the shipped `/answer` workflow.
- `#16 Extend CI/security hardening and document integration follow-ons`: moved to `In progress` for pytest-in-CI and script/negative-path coverage work.
- `#8 Add deep vs deep-reasoning comparison workflow`: moved from `In progress` to `Implemented and pushed` after landing the end-to-end compare command on top of grouped reporting.
- `#9 Add structured-output extraction with output_schema`: moved from `Open` to `Closed` after landing the standalone structured-search workflow and schema-driven extraction path.
- `#13 Expand domain query suites for PA, CAT law, appraisers, IA, and adjacent industries`: moved to `In progress` after landing named benchmark suites and suite-aware reporting context.

## Docs Touched

- `docs/issue-tracker.md`
- `docs/roadmap.md`
- `docs/sessions/2026-03-18-phase2-parallel-slices.md`
- `README.md`

## Tests and Checks Run

- `gh issue list --state open --limit 30` -> confirmed all milestone issues were still open on GitHub before close-out.
- `pytest -q` -> passed at session start with `20 passed`.
- `pytest -q tests\test_cli.py tests\test_scripts.py` -> passed after adding negative-path and script coverage.
- `pytest -q` -> passed after slice-1 changes with `27 passed`.
- `python scripts/run_notebook_smoke.py --mode smoke` -> passed.
- `pytest -q tests\test_client.py tests\test_models.py` -> passed for deep-search payload controls.
- `pytest -q tests\test_cost_model.py tests\test_cli.py` -> passed for deep-search CLI and cost controls.
- `pytest -q` -> passed after slice-2 integration with `33 passed`.
- `pytest -q tests\test_evaluation.py` -> passed for named benchmark suites and legacy fixture compatibility.
- `pytest -q` -> passed after grouped reporting plus suite-selection integration with `37 passed`.
- `pytest -q tests\test_cli.py` -> passed for the end-to-end `compare-search-types` workflow.
- `pytest -q` -> passed after the workflow slice with `39 passed`.
- `pytest -q tests\test_client.py tests\test_models.py tests\test_cli.py tests\test_artifacts.py` -> passed for the integrated `/answer` workflow.
- `pytest -q` -> passed after `/answer` integration with `46 passed`.
- `pytest -q tests\test_client.py tests\test_models.py` -> passed for the structured-search core path with `16 passed`.
- `pytest -q` -> passed after structured-search integration with `55 passed`.

## Outcome

- Reconciled GitHub issue state with the actual shipped repo state and closed the completed foundation/comparison issues: `#1`, `#2`, `#3`, `#4`, `#5`, and `#8`.
- Completed slice 1 CI/test hardening in two commits:
  - `92e840f` added CLI negative-path coverage and new script tests.
  - `3ee8f35` landed CI pytest execution, pytest warning cleanup, and the first session-doc updates.
- CI now runs both `pytest` and notebook smoke so later feature slices land on safer rails.
- Completed slice 2 deep-search rail building in two commits:
  - `28428e9` added additive payload controls for `additionalQueries`, published-date filters, and `livecrawl`.
  - `3f39c3d` added CLI flags and type-aware cost override support for `deep` and `deep-reasoning` experiments.
- The repo can now run deeper `/search` experiments without changing the existing `results[]` artifact and evaluation contract.
- Completed slice 3 experiment segmentation and grouped reporting in two commits plus one integration fix:
  - `b592dfe` added suite-aware grouped comparison reporting and threaded run context through artifacts.
  - A follow-up local commit from this session lands named benchmark suite loading and CLI suite selection integration.
- The repo can now compare runs by query suite while preserving the original flat before/after report.
- Completed the next product slice for `#8`:
  - A follow-up local commit from this session lands `compare-search-types`, which executes deep-vs-deep-reasoning evaluations end to end and emits the grouped comparison bundle in one command.
- The repo now has a real workflow command for search-type experiments rather than only low-level controls.
- Completed the next product slice for `#7`:
  - `9acbeab` landed the standalone `answer` command and `answer.json` artifact wiring.
  - A follow-up local commit from this session lands the `/answer` client path, answer-specific models, smoke responses, and tests.
- The repo now supports cited-answer runs as a first-class workflow without forcing them through ranked-search evaluation semantics.
- Completed the next product slice for `#9`:
  - `9be7409` landed the structured-search core client path, typed structured-output models, smoke responses, and focused tests.
  - `20cc69a` landed the standalone `structured-search` CLI workflow, `structured_output.json` artifact wiring, and workflow tests.
- The repo now supports schema-driven extraction as a first-class workflow without forcing structured payloads through the ranked-search `results.jsonl` evaluation contract.

## Next-Session Handoff

- Decide whether `/findSimilar` or `/research` is the next highest-alpha API slice now that `/answer`, deep-vs-deep-reasoning, and structured-search are all shipped.
- Keep reconciling GitHub issue state and docs as remaining domain and repo-ops slices land.

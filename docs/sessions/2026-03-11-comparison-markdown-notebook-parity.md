# Session: Comparison Markdown and Notebook Parity

- Date: 2026-03-11
- Participants: Codex, repository owner
- Related roadmap items: [docs/roadmap.md](../roadmap.md), [#5](https://github.com/itprodirect/exai-search-demo/issues/5)
- Related ADRs: [ADR-0001-roadmap-governance.md](../adr/ADR-0001-roadmap-governance.md)

## Context

Follow-up polish after #5 implementation to add a human-readable comparison artifact and make notebook outputs match the CLI taxonomy/comparison behavior.

## Repo Facts Observed

- Comparison payloads already existed in structured JSON, but no markdown artifact was produced for reviewers.
- Notebook flow had taxonomy/comparison library support available but was not surfacing the full scorecard/deltas by default.
- The local notebook contained experimental cells with `EXPERIMENTAL_MODE = True`, which broke smoke execution until switched off by default.

## Decisions Made

- Add `comparison.md` generation directly under each candidate run artifact directory when comparison data exists.
- Keep comparison markdown generation in `reporting.py` and call it from CLI/notebook, instead of introducing a separate script path.
- Extend notebook Cell 2/7/9 to support optional baseline comparison config and display taxonomy + before/after output.
- Set experimental notebook mode defaults to `False` to keep smoke safety consistent.

## Issues Opened or Updated

- [#5](https://github.com/itprodirect/exai-search-demo/issues/5): polished with reviewer-facing markdown output and notebook parity.

## Docs Touched

- [README.md](../../README.md)
- [docs/issue-tracker.md](../issue-tracker.md)
- [docs/sessions/2026-03-11-comparison-markdown-notebook-parity.md](./2026-03-11-comparison-markdown-notebook-parity.md)

## Code Touched

- [src/exa_demo/reporting.py](../../src/exa_demo/reporting.py)
- [src/exa_demo/cli.py](../../src/exa_demo/cli.py)
- [src/exa_demo/__init__.py](../../src/exa_demo/__init__.py)
- [exa_people_search_eval.ipynb](../../exa_people_search_eval.ipynb)
- [tests/test_reporting.py](../../tests/test_reporting.py)
- [tests/test_cli.py](../../tests/test_cli.py)

## Tests and Checks Run

- `pytest -q` (passed: `20 passed`)
- `python -m exa_demo eval --mode smoke --run-id cli-cook-compare --artifact-dir experiments --compare-to-run-id 20260310T033256Z --limit 2 --json` (passed; produced `comparison.md`)
- `python scripts/run_notebook_smoke.py --mode smoke --timeout 180` (passed)

## Outcome

- Added `render_comparison_markdown()` and `write_comparison_markdown()`.
- CLI eval now emits `comparison_markdown_path` and writes `experiments/<RUN_ID>/comparison.md` when `--compare-to-run-id` is used.
- Notebook now exposes optional baseline-compare config, prints taxonomy scorecard/failure counts, and writes comparison markdown when enabled.

## Next-Session Handoff

- If desired, add a compact per-query diff table to `comparison.md` for shared query rows.
- Optionally add a small helper command to regenerate markdown from an existing `summary.json` `extra.comparison` payload.

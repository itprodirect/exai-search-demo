# Session: Phase 1 CLI and Installability

- Date: 2026-03-10
- Participants: Codex, repository owner
- Related roadmap items: [docs/roadmap.md](../roadmap.md), [#3](https://github.com/itprodirect/exai-insurance-intel/issues/3)
- Related ADRs: [ADR-0001-roadmap-governance.md](../adr/ADR-0001-roadmap-governance.md)

## Context

Continue Phase 1 by turning the extracted package into an installable project with a real CLI entrypoint, while preserving the notebook-first workflow.

## Repo Facts Observed

- The repo already had enough shared package logic to support CLI reuse without extracting another service layer first.
- `load_runtime_state()` and the current cache/client/reporting functions already matched the CLI needs if wrapped carefully.
- Editable install verification needed `--no-build-isolation` in this environment because the sandbox blocked build-dependency downloads.

## Decisions Made

- Use `pyproject.toml` with `setuptools` and a `src/` layout rather than adding a second packaging system.
- Add a thin `argparse` CLI with `search`, `eval`, and `budget` commands instead of pulling in a new CLI framework.
- Keep CLI modes aligned with existing repo behavior: `smoke`, `live`, and `auto`.
- Reuse the artifact writer in CLI commands so notebook and CLI runs produce the same run-history shape.

## Issues Opened or Updated

- [#3](https://github.com/itprodirect/exai-insurance-intel/issues/3): implemented package metadata, CLI entrypoints, and install verification.
- [#1](https://github.com/itprodirect/exai-insurance-intel/issues/1): foundation epic now includes typed models, artifact logging, and CLI/installability work.

## Docs Touched

- [docs/roadmap.md](../roadmap.md)
- [docs/issue-tracker.md](../issue-tracker.md)
- [docs/sessions/2026-03-10-phase1-cli-installability.md](./2026-03-10-phase1-cli-installability.md)
- [README.md](../../README.md)

## Code Touched

- [pyproject.toml](../../pyproject.toml)
- [src/exa_demo/cli.py](../../src/exa_demo/cli.py)
- [src/exa_demo/__main__.py](../../src/exa_demo/__main__.py)
- [tests/test_cli.py](../../tests/test_cli.py)

## Tests and Checks Run

- `pytest -q`
- `python -m pip install -e . --no-deps --no-build-isolation`
- `python -m exa_demo --help`
- `python -m exa_demo search "forensic engineer insurance expert witness" --mode smoke --run-id cli-verify-search --sqlite-path .cli-verify.sqlite --artifact-dir .cli-artifacts --json`
- `python -m exa_demo eval --mode smoke --run-id cli-verify-eval --sqlite-path .cli-verify.sqlite --artifact-dir .cli-artifacts --limit 2 --json`
- `python -m exa_demo budget --run-id cli-verify-eval --sqlite-path .cli-verify.sqlite --json`

## Outcome

- Added installable project metadata and an editable-install path.
- Added `search`, `eval`, and `budget` CLI commands under `python -m exa_demo`.
- Verified the installed CLI entrypoint in smoke mode and confirmed it writes the expected artifact bundles.

## Next-Session Handoff

- Decide whether to close or further refine [#3](https://github.com/itprodirect/exai-insurance-intel/issues/3) after review.
- Continue with [#5](https://github.com/itprodirect/exai-insurance-intel/issues/5) evaluation taxonomy/reporting or move into Phase 2 endpoint coverage.
- If package install instructions change, keep [README.md](../../README.md) and [pyproject.toml](../../pyproject.toml) aligned.

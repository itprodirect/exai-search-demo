# Session: Roadmap and Backlog Baseline

- Date: 2026-03-10
- Participants: Codex, repository owner
- Related roadmap items: [docs/roadmap.md](../roadmap.md)
- Related ADRs: [ADR-0001-roadmap-governance.md](../adr/ADR-0001-roadmap-governance.md)

## Context

Create a durable roadmap and GitHub backlog from the newly added improvement document, while preserving an auditable record of what happened this session and why.

## Repo Facts Observed

- `src/exa_demo` already exists and is used by `exa_people_search_eval.ipynb`.
- The repo already contains cache, cost, evaluation, reporting, and safety helpers.
- `benchmarks/insurance_cat_queries.json` exists and is covered by tests.
- `.github/workflows/ci.yml` already runs a no-network smoke execution for the notebook.
- `pytest -q` passed before the docs/backlog work began.
- GitHub had no existing issues and only the default label set before backlog creation.

## Decisions Made

- Use a phased roadmap rather than mirroring the raw source document structure.
- Treat repo docs as the canonical narrative history and GitHub issues as the execution queue.
- Use epics plus tasks for backlog structure.
- Preserve decision history with both ADRs and per-session notes.
- Keep Neo4j, Websets, MCP, War Room, and richer UI ideas in `Hold / Explore` until they have tighter acceptance criteria.

## Issues Opened or Updated

- Created epic issues [#1](https://github.com/itprodirect/exai-insurance-intel/issues/1), [#6](https://github.com/itprodirect/exai-insurance-intel/issues/6), [#12](https://github.com/itprodirect/exai-insurance-intel/issues/12), and [#15](https://github.com/itprodirect/exai-insurance-intel/issues/15).
- Created task issues [#2](https://github.com/itprodirect/exai-insurance-intel/issues/2) through [#5](https://github.com/itprodirect/exai-insurance-intel/issues/5), [#7](https://github.com/itprodirect/exai-insurance-intel/issues/7) through [#11](https://github.com/itprodirect/exai-insurance-intel/issues/11), [#13](https://github.com/itprodirect/exai-insurance-intel/issues/13), [#14](https://github.com/itprodirect/exai-insurance-intel/issues/14), and [#16](https://github.com/itprodirect/exai-insurance-intel/issues/16) through [#18](https://github.com/itprodirect/exai-insurance-intel/issues/18).
- Applied consistent issue bodies covering problem, why now, scope, non-goals, acceptance criteria, dependencies, and source references.
- Added labels and milestones to support phased tracking.

## Docs Touched

- [docs/roadmap.md](../roadmap.md)
- [docs/issue-tracker.md](../issue-tracker.md)
- [docs/sessions/README.md](./README.md)
- [docs/sessions/2026-03-10-roadmap-baseline.md](./2026-03-10-roadmap-baseline.md)
- [docs/adr/README.md](../adr/README.md)
- [docs/adr/ADR-0001-roadmap-governance.md](../adr/ADR-0001-roadmap-governance.md)
- [README.md](../../README.md)

## Tests and Checks Run

- `pytest -q`
- GitHub issue and label inspection via `gh`
- GitHub label, milestone, and issue creation via `gh`

## Outcome

- Added the roadmap, ADR, issue tracker, and session-log structure needed for durable delivery history.
- Created the initial GitHub backlog and linked it back to repo docs.
- No feature code was implemented in this session.

## Next-Session Handoff

- Start with the Phase 1 foundation issues, especially [#2](https://github.com/itprodirect/exai-insurance-intel/issues/2) and [#4](https://github.com/itprodirect/exai-insurance-intel/issues/4).
- Keep the roadmap and issue tracker synchronized if issue titles, labels, or milestones change.
- Re-run `pytest -q` after any docs-only changes that touch tracked files to confirm the repo baseline remains stable.

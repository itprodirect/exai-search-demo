# GitHub Issue Tracker

This document is the canonical mapping between the roadmap in [roadmap.md](./roadmap.md), GitHub issues, ADRs, and session logs.

Update it whenever issues are created, closed, re-scoped, or moved between milestones.

## Tracker Fields

- `Type`: epic or task
- `Milestone`: GitHub milestone the issue belongs to
- `Labels`: normalized labels applied in GitHub
- `Status`: current expected execution state
- `Dependency`: issue number or `None`
- `Source roadmap section`: matching section in [roadmap.md](./roadmap.md)
- `Last-updated session log`: latest repo session note that touched the issue

## Active Backlog

| Issue | Type | Milestone | Labels | Status | Dependency | Source roadmap section | GitHub URL | Last-updated session log |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `#1 Epic: Foundation and experiment discipline` | Epic | `Phase 1 - Foundation` | `type:epic`, `area:core`, `priority:p0`, `status:ready` | Closed | None | Phase 1 - Foundation | `https://github.com/itprodirect/exai-search-demo/issues/1` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |
| `#2 Add normalized typed models for Exa results and cost metadata` | Task | `Phase 1 - Foundation` | `type:task`, `area:core`, `priority:p0`, `status:ready` | Closed | `#1` | Phase 1 - Foundation | `https://github.com/itprodirect/exai-search-demo/issues/2` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |
| `#3 Make exa_demo installable and add CLI entrypoints` | Task | `Phase 1 - Foundation` | `type:task`, `area:core`, `priority:p1`, `status:ready` | Closed | `#1, #2` | Phase 1 - Foundation | `https://github.com/itprodirect/exai-search-demo/issues/3` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |
| `#4 Add experiment artifact logging for auditable runs` | Task | `Phase 1 - Foundation` | `type:task`, `area:eval`, `priority:p0`, `status:ready` | Closed | `#1, #2` | Phase 1 - Foundation | `https://github.com/itprodirect/exai-search-demo/issues/4` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |
| `#5 Expand evaluation taxonomy and before/after reporting` | Task | `Phase 1 - Foundation` | `type:task`, `area:eval`, `priority:p1`, `status:ready` | Closed | `#1, #4` | Phase 1 - Foundation | `https://github.com/itprodirect/exai-search-demo/issues/5` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |
| `#6 Epic: Exa API surface expansion` | Epic | `Phase 2 - Exa Coverage` | `type:epic`, `area:exa-api`, `priority:p0`, `status:ready` | Open | `#1` | Phase 2 - Exa API Coverage | `https://github.com/itprodirect/exai-search-demo/issues/6` | `docs/sessions/2026-03-10-roadmap-baseline.md` |
| `#7 Add /answer endpoint demo and cited-answer evaluation` | Task | `Phase 2 - Exa Coverage` | `type:task`, `area:exa-api`, `priority:p0`, `status:ready` | Closed | `#6, #1` | Phase 2 - Exa API Coverage | `https://github.com/itprodirect/exai-search-demo/issues/7` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |
| `#8 Add deep vs deep-reasoning comparison workflow` | Task | `Phase 2 - Exa Coverage` | `type:task`, `area:exa-api`, `priority:p0`, `status:ready` | Closed | `#6, #4` | Phase 2 - Exa API Coverage | `https://github.com/itprodirect/exai-search-demo/issues/8` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |
| `#9 Add structured-output extraction with output_schema` | Task | `Phase 2 - Exa Coverage` | `type:task`, `area:exa-api`, `priority:p1`, `status:ready` | Closed | `#6, #2` | Phase 2 - Exa API Coverage | `https://github.com/itprodirect/exai-search-demo/issues/9` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |
| `#10 Add /findSimilar demo for seed-URL discovery` | Task | `Phase 2 - Exa Coverage` | `type:task`, `area:exa-api`, `priority:p1`, `status:ready` | Closed | `#6, #1` | Phase 2 - Exa API Coverage | `https://github.com/itprodirect/exai-search-demo/issues/10` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |
| `#11 Add /research demo for market/regulatory reports` | Task | `Phase 2 - Exa Coverage` | `type:task`, `area:exa-api`, `priority:p1`, `status:ready` | Closed | `#6, #2, #4` | Phase 2 - Exa API Coverage | `https://github.com/itprodirect/exai-search-demo/issues/11` | `docs/sessions/2026-03-19-phase3-research-benchmarks-rails.md` |
| `#12 Epic: Insurance/CAT domain coverage` | Epic | `Phase 3 - Domain/Productization` | `type:epic`, `area:domain`, `priority:p1`, `status:ready` | Open | `#1, #6` | Phase 3 - Domain Coverage and Productization | `https://github.com/itprodirect/exai-search-demo/issues/12` | `docs/sessions/2026-03-10-roadmap-baseline.md` |
| `#13 Expand domain query suites for PA, CAT law, appraisers, IA, and adjacent industries` | Task | `Phase 3 - Domain/Productization` | `type:task`, `area:domain`, `priority:p0`, `status:ready` | Closed | `#12, #4, #5` | Phase 3 - Domain Coverage and Productization | `https://github.com/itprodirect/exai-search-demo/issues/13` | `docs/sessions/2026-03-19-phase3-research-benchmarks-rails.md` |
| `#14 Add export/report outputs and demo-gallery documentation` | Task | `Phase 3 - Domain/Productization` | `type:task`, `area:docs`, `priority:p1`, `status:ready` | Closed | `#12, #7, #8, #13` | Phase 3 - Domain Coverage and Productization | `https://github.com/itprodirect/exai-search-demo/issues/14` | `docs/sessions/2026-03-19-phase3-export-outputs-and-smoke-rails.md` |
| `#15 Epic: Documentation, governance, and repo operations` | Epic | `Phase 3 - Domain/Productization` | `type:epic`, `area:ops`, `priority:p0`, `status:ready` | Open | None | Phase 4 - Documentation, Governance, and Repo Operations | `https://github.com/itprodirect/exai-search-demo/issues/15` | `docs/sessions/2026-03-10-roadmap-baseline.md` |
| `#16 Extend CI/security hardening and document integration follow-ons` | Task | `Phase 3 - Domain/Productization` | `type:task`, `area:ops`, `priority:p1`, `status:ready` | In progress | `#15, #14` | Phase 3 - Domain Coverage and Productization | `https://github.com/itprodirect/exai-search-demo/issues/16` | `docs/sessions/2026-03-20-phase4-refactor-decomposition.md` |
| `#17 Maintain roadmap, issue tracker, ADRs, and session notes` | Task | `Phase 3 - Domain/Productization` | `type:task`, `area:docs`, `priority:p0`, `status:ready` | In progress | `#15` | Phase 4 - Documentation, Governance, and Repo Operations | `https://github.com/itprodirect/exai-search-demo/issues/17` | `docs/sessions/2026-03-20-phase4-refactor-decomposition.md` |
| `#18 Upgrade README with feature matrix, architecture diagram, and roadmap links` | Task | `Phase 3 - Domain/Productization` | `type:task`, `area:docs`, `priority:p1`, `status:ready` | Closed | `#15` | Phase 4 - Documentation, Governance, and Repo Operations | `https://github.com/itprodirect/exai-search-demo/issues/18` | `docs/sessions/2026-03-18-phase2-parallel-slices.md` |

## Usage Rules

- Every active roadmap item outside Phase 0 must map to exactly one GitHub issue.
- Close the roadmap item and issue together, or document why they diverged.
- Update the `Last-updated session log` field whenever the issue scope, status, or acceptance criteria changes.
- Record durable process changes in `docs/adr/`.





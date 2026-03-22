# ADR-0001: Roadmap Governance and Delivery Tracking

- Date: 2026-03-10
- Status: Accepted

## Context

The repository gained a detailed improvement proposal in [the improvement roadmap](../exai-insurance-intel-improvements.md), but it did not yet have a canonical roadmap, durable decision log, or GitHub backlog structure. The repo also already contains more implementation than the proposal assumes, so future planning needs to start from the actual baseline rather than a notebook-only mental model.

## Decision

- Use a phased roadmap as the canonical planning view.
- Keep roadmap, ADRs, issue tracker, and session notes in-repo under `docs/`.
- Use GitHub issues as the execution queue, organized as epics plus task issues.
- Track active work in milestones aligned to roadmap phases.
- Require every active roadmap item outside the completed baseline to map to exactly one GitHub issue.
- Preserve exploratory ideas in a `Hold / Explore` section until they are specific enough to become backlog items.

## Consequences

- The repo now has a durable place to record why roadmap decisions were made.
- Session history can be reconstructed without relying only on chat or GitHub timestamps.
- GitHub becomes easier to operate because labels, milestones, and issue types follow a fixed scheme.
- Documentation upkeep becomes part of the delivery process, not an afterthought.

## Related Roadmap Items or Issues

- [docs/roadmap.md](../roadmap.md)
- [docs/issue-tracker.md](../issue-tracker.md)

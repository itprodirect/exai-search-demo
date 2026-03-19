# Integration Boundaries

This repo is designed to stay safe-by-default while still supporting deliberate live validation.

## Execution Modes

- `smoke`: no network, no Exa billing, mocked responses only
- `live`: real Exa API calls, requires `EXA_API_KEY`, can incur billing
- `auto`: resolves to `live` only when `EXA_API_KEY` is configured; otherwise falls back to `smoke`

## Default Delivery Rule

- Use `smoke` for development, CI, docs walkthroughs, and regression checks.
- Use `live` only for explicit manual validation when you want to inspect real API behavior.
- Keep human review in the loop for any operational interpretation of results, even in `live`.

## Artifact Expectations

- Smoke runs preserve the same artifact shape as live runs whenever possible.
- Workflow-specific payloads remain additive. Existing JSON and JSONL contracts should not be rewritten just because a new export is added.
- Every run records runtime execution metadata in `config.json`, `summary.json`, and `manifest.json` so reviewers can distinguish smoke artifacts from live artifacts.

## CI Boundary

- CI should stay smoke-only by default.
- CI is allowed to run lint, pytest, and the notebook smoke runner.
- Live API validation should remain an explicit manual workflow until its scope, spend guardrails, and secrets handling are documented more tightly.

## Cost and Safety Boundary

- Cached reruns should not re-bill.
- Live validation should stay bounded to small, intentional runs.
- Public/professional info only.
- No address hunting, contact harvesting, or operational use without human review.

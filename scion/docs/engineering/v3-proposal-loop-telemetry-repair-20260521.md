# v3 Proposal Loop and Telemetry Repair - 2026-05-21

## Scope

Focused P0/P1 repair for the 3-round v0.4 boundary/lifecycle stopped run.
The changes keep generic Scion problem-agnostic: domain mechanism facts remain
adapter/provider-owned or come from structured rejection payloads.

## Changes

- CLI lifecycle now installs SIGTERM/SIGINT handlers around `scion run`.
  A signal requests campaign stop, writes status/summary stop reason, and exits
  with the conventional signal exit code. The campaign manager also exposes a
  stop request path so the loop will not start new APS/session/LLM work after a
  stop is requested.
- Campaign loop now has a separate pre-screen agent-quality ceiling.
  Cumulative `agent_quality_blocked` proposal attempts stop the run with
  `proposal_quality_loop` by default after `max(3, rounds + 2)` attempts, or the
  `SCION_PROPOSAL_QUALITY_LOOP_LIMIT` environment override. Repairable telemetry
  and same-family retries keep separate budgets.
- Algorithm-smoke telemetry treats activation as required but effect/objective
  positive evidence as advisory unless a provider or hypothesis explicitly asks
  smoke to require positive effect. Formal telemetry guard behavior remains
  strict by default.
- Smoke feedback now distinguishes a helper that exists but was not reached in
  smoke from missing instrumentation, and tells the agent to adjust trigger
  conditions or provide a smoke-observable activation path.
- Hypothesis prompts can render a compact negative-fact block before the task.
  The block is built from provider-owned active facts or structured rejection
  payloads and includes fact ids, mechanism ids, and allowed-variant guidance.
- The Chinese runbook background launcher now records a process group and stops
  the process group, preventing wrapper-only termination from leaving a child
  campaign process alive.

## Verification

Targeted unit tests cover campaign loop ceiling, CLI signal handler, telemetry
advisory effect semantics, activation blocking, smoke feedback reachability
guidance, and negative fact prompt rendering.

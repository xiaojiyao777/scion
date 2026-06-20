# Scion v0.4 Current State

Last updated: 2026-06-20

This file is the operational resume point, not a run log. Replace stale
conclusions instead of appending history. Detailed repair notes belong in
`scion/docs/experiments/v0.4/`; sparse milestones belong in
`scion/docs/status/v0.4-history.md`.

## Operating Frame

- Active branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closeout goal: Scion must be stable enough for warehouse to recover
  continuous useful research and for CVRP/VRP to produce evidence-backed
  solver-design hypotheses before v0.5 broad experiment matrices.
- Current posture: avoid broad budgets, generic truncation/compression, and
  decorative gates. Keep CVRP/warehouse semantics problem-owned and keep
  `DecisionFeatures` problem-neutral.

## Current Decision

- Framework/readiness/launcher repairs are accepted enough for focused
  warehouse and CVRP follow-up.
- v0.4 is not closed until live runs show effective research behavior.
- No LLM campaign is currently running.
- Current blocker: external WSL `gpt-5.5` provider auth, not Scion static
  readiness. `/v1/models` can list `gpt-5.5`, but strict completion preflight
  fails with HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`. The auth pool has `active=0`, `total=1`; no active
  account is available. Ignore volatile substate changes such as expired versus
  refreshing unless active auth becomes available.

Do not launch a prepared root until:

```bash
scion/tools/check_launch_readiness.py <prepared-root> --require-launch-ready --format json
```

reports `launch_ready=true`.

## Active Prepared Roots

Generated on WSL at prepared runtime commit `fdc7ec85`; local mirrors exist under
`/home/clawd/research/scion-experiments/` with the same directory names.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-protocoldetail-fdc7ec85-preflight-6r-gpt55-20260620T062233Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-protocoldetail-fdc7ec85-preflight-4r-gpt55-20260620T062250Z-claw`

Readiness snapshot:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- Required failure: completion preflight auth only
- Runtime guard status: prepared commit `fdc7ec85`; launch-critical runtime
  guard paths are unchanged after docs-only snapshot commits.

Prepared run shape:

- Warehouse: 6 rounds, champion-v2 follow-up.
- CVRP: 4 rounds, bounded/deadline-aware large two-opt follow-up from external
  seed guidance.
- Proposal headroom: `max_attempts=64`, `max_quality_loops=64`.
- APS headroom: `agentic_session_timeout_sec=3600`,
  `agentic_tool_max_steps=240`, `agentic_tool_max_calls=200`,
  `agentic_code_tool_max_calls=200`, `agentic_observation_max_chars=2000000`.

## Framework Guarantees To Preserve

- LLM output, repair diagnostics, branch lessons, prompt ratios, and
  problem-owned research diagnostics remain tainted proposal material. They must
  not enter Decision, `DecisionFeatures`, promotion, scheduler state, or solver
  semantics.
- Launch readiness is the operator-facing authority for prepared roots. It
  checks prepared contract/brief identity, prompt-context bridge, problem
  handoff, runtime guards, model route, absolute launch paths, completion
  preflight, strict postrun rebuild/readiness, and prepared/postrun rebuild
  identity.
- Prepared prompt context must project required `research_focus` fields into
  the actual launch prompt path, including CVRP CMT2/CMT4 protection
  requirements.
- Current hypothesis prompts carry compact proposal-only research-shape
  diagnostics before broader feedback, and prompt manifest accounting classifies
  this block as `research_signal`.
- Code-phase prompts must retain direct source visibility for champion/current
  branch/target files and declared integration files.
- Postrun acceptance cannot silently pass when strict rebuild/readiness fails:
  launcher wrappers promote strict postrun acceptance failure to an effective
  wrapper failure and annotate top-level `run_status.json`.
- Warehouse/CVRP postrun conclusions require current-run evidence payloads,
  runtime-evidence consistency, formal hypothesis prompt traces, and
  problem-owned review rules; summary prose alone is not acceptance evidence.
  Problem-summary `current_run_evidence` must match the analysis brief
  lifecycle and Phase 4 current-run state. Required or present review-input
  summaries must also be current-run, so stale optional
  measurement/runtime/continuity summaries cannot make a delegated review look
  analysis-ready. Protocol-evaluated conclusions must also match current
  protocol-accounting detail for formal-screened candidates, metric rows,
  artifact rows, and stage rows. Quality-blocked no-protocol conclusions must
  also match current failure-taxonomy quality-block counts,
  reports-with-quality-blocks, and reason-count distribution. CVRP bounded
  two-opt ready summaries must
  match recomputed direct-evidence counters, family lists, rejection counts, and
  top-row signal count from current measurement/continuity inputs. Measurement
  evidence must match current interpretation counts and
  `max_effect_to_mde_ratio`; CVRP bounded two-opt ready summaries must also
  match current mechanism-family mapped/unmapped row counts.

## Warehouse

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
- Next live question: can Scion produce useful follow-up research from `v2`, or
  correctly diagnose a real post-v2 plateau?
- A plateau conclusion is accepted only when protocol evidence shows no
  positive effect at or above MDE, runtime evidence is review-ready, and
  continuity evidence is substantive without fully missed same-mechanism
  follow-up opportunities.

## CVRP/VRP

- CVRP can now steer target intent, carry branch lessons into prompts, generate
  material solver code, complete formal screening, preserve mechanism telemetry,
  and reject weak or negative hypotheses with evidence.
- CVRP is still not v0.4-accepted because no current solver-design branch has
  produced continuous improvement or promotion.
- The active follow-up treats the external large-instance intra-route two-opt
  result only as proposal guidance. Review readiness requires a bounded,
  deadline-aware implementation with co-located positive effect, activation,
  objective-effect, intra-large-two-opt phase telemetry, and CMT2/CMT4
  protection evidence; `two_opt_star`, cross-route, VNS, unbounded, and
  fallback phase telemetry do not satisfy this direct-evidence rule.

## Next Actions

1. Refresh WSL/local proxy login, then rerun strict launch readiness on the
   current prepared root. `/v1/models` is not enough; completion preflight must
   pass.
2. Run warehouse `v2` follow-up first as the simpler continuous-improvement
   proof.
3. Run the CVRP bounded large-two-opt follow-up after warehouse is underway or
   accepted for launch.
4. After each run, classify current-run evidence through the problem-owned
   postrun review rules before treating promotion/no-promotion as a research
   conclusion.

## Evidence Pointers

- Core task and acceptance source: `scion/TASK.md`.
- Boundary and audit basis:
  `scion/design/scion-architecture-v3.md`,
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`, and
  `scion/design/v0.5-evidence-uplift-roadmap.md`.
- Current planning summary:
  `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`.
- Current launch/readiness evidence:
  `scion/docs/experiments/v0.4/v04-prepared-research-focus-projection-readiness-20260620.md`.
- Current postrun wrapper-status evidence:
  `scion/docs/experiments/v0.4/v04-postrun-wrapper-status-escalation-20260620.md`.
- Current WSL access:
  `ssh -i ~/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1`.
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`.
- WSL experiments root: `/home/xjy-ubuntu/research/scion-experiments`.
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`.
- For ad hoc WSL tests, set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion` because the
  conda env also has a stale editable install under
  `/home/xjy-ubuntu/projects/scion`.

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

Generated on WSL at launch-authoritative prepared runtime commit `aa916783`
after local runtime-equivalent commit `a36e4604`; local mirrors exist under
`/home/clawd/research/scion-experiments/` with the same directory names for
inspection.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-size70hypctx-aa916783-nocaps-aps0-sourceheadroom-codecap0-preflight-6r-gpt55-20260620T115809Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-large-twoopt-phase4-size70hypctx-aa916783-nocaps-aps0-sourceheadroom-codecap0-preflight-4r-gpt55-20260620T115809Z-claw`

Readiness snapshot:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- Required failure: completion preflight auth only
- Runtime guard status: prepared runtime commit `aa916783`; strict readiness
  must keep reporting runtime guard OK. Doc/status-only commits after prepare
  are acceptable only when readiness reports unchanged runtime guard paths.
- Campaign launch contract status: `ok`; `run.sh`, `launch.env`, and
  `prepared_run_manifest.v1.json` agree on the problem/protocol/split/seeds,
  campaign directory, rounds, time limit, measurement-governance mode, and
  proposal-context ablation used by the actual `scion.cli.main run` command.

Prepared run shape:

- Warehouse: 6 rounds, champion-v2 follow-up.
- CVRP: 4 rounds, bounded/deadline-aware large two-opt follow-up from external
  seed guidance.
- Proposal research caps are disabled for the current prepared roots:
  `proposal_attempt_limit=0`, `proposal_quality_loop_limit=0`. The core
  campaign loop still has a high-water `campaign_safety_step_limit` and the
  normal circuit breaker.
- Launch readiness treats missing or command-disconnected proposal-cap fields
  as launch blockers. Exact `0` values for disabled proposal/APS caps are
  recorded as disabled details, not warnings or gates; positive values below
  the historical recommendation remain audit warnings only.
- APS research caps are disabled for the current prepared roots while the
  wall-time guard remains enabled: `agentic_session_timeout_sec=3600`,
  `agentic_tool_max_steps=0`, `agentic_tool_max_calls=0`,
  `agentic_code_tool_max_calls=0`, `agentic_observation_max_chars=0`.
  Runtime semantics now match readiness semantics: `agentic_code_tool_max_calls=0`
  uses a disabled effective limit and must not suppress code-phase
  planner-selected source reads.
- Runtime replay semantics: budget-exhausting summaries suppress stale
  fresh-runtime replay markers, materialization, and pressure reports. Runtime
  tie fresh replay remains available only for comparative runtime semantics.
- Low-SNR runtime semantics: budget-exhausting runtime ratios do not block
  trajectory-divergent low-SNR expansion or same-branch follow-up; comparative
  runtime slowdown still remains actionable.
- CVRP prompt diagnostics: hypothesis context exposes problem-owned
  `screening_headroom`, `measurable_opportunity_classes`, and
  `mechanism_effect_ranking` as proposal-only research signals while raw BKS,
  validation, frozen, calibration-row, and pair-row details remain hidden from
  prompts and excluded from `DecisionFeatures`. Prepared prompt readiness now
  carries a `cvrp_problem_measurement_diagnostics_prompt_bridge` summary and
  launch readiness recomputes it from the current checkout, so missing or stale
  ranking projection blocks static launch readiness before a campaign starts.
- Warehouse prompt diagnostics: hypothesis context exposes problem-owned
  validation-transfer follow-up diagnostics, including transfer risk,
  activation/effect counters, `validation_transfer_continuation`, and
  plateau-vs-continuous-follow-up reason codes as proposal-only research
  signals while raw prompts/payloads remain excluded. Prepared prompt readiness
  now carries a `warehouse_problem_measurement_diagnostics_prompt_bridge`
  summary and launch readiness recomputes it from the current checkout, so
  missing or stale warehouse diagnostic projection blocks static readiness
  before a campaign starts.

## Framework Guarantees To Preserve

- LLM output, repair diagnostics, branch lessons, prompt ratios, and
  problem-owned research diagnostics remain tainted proposal material. They must
  not enter Decision, `DecisionFeatures`, promotion, scheduler state, or solver
  semantics.
- Launch readiness is the operator-facing authority for prepared roots. It
  checks prepared contract/brief identity, prompt-context bridge, problem
  handoff, runtime guards, model route, campaign launch command consistency,
  absolute launch paths, completion preflight, strict postrun rebuild/readiness,
  and prepared/postrun rebuild identity.
- Prepared prompt context must project required `research_focus` fields into
  the actual launch prompt path, including CVRP CMT2/CMT4 protection
  requirements. The current prepared roots carry
  `prepared_research_focus_prompt_bridge.detail.prompt_summary` with
  schema `scion.prepared_research_focus_prompt_summary.v1`: warehouse renders
  19 required `research_focus` paths, CVRP renders 36, both with
  `missing_rendered_paths=[]`, no forbidden prompt tokens, raw prompts excluded,
  and `DecisionFeatures` excluded.
- CVRP prepared prompt context must also prove that problem-owned measurement
  diagnostics reach the hypothesis prompt through a safe summary, including the
  mechanism-effect ranking, without persisting raw prompts or raw diagnostic
  payloads.
- Warehouse prepared prompt context must also prove that problem-owned
  validation-transfer diagnostics reach the hypothesis prompt through a safe
  summary, including the continuous-follow-up and plateau-guard signals, without
  persisting raw prompts or raw diagnostic payloads.
- Current hypothesis prompts carry compact proposal-only research-shape
  diagnostics before broader feedback, and prompt manifest accounting classifies
  this block as `research_signal`.
- Code-phase prompts must retain direct source visibility for champion/current
  branch/target files and declared integration files. Source-read tool schemas,
  registry result caps, ledger normalization, and active solver preview
  headroom must remain aligned so `context.read_algorithm_file`,
  `context.read_algorithm_symbol`, and `context.read_surface` can carry the
  96k source-window used by current solver-design/code prompts without
  `RESULT_TOO_LARGE` or shallow-preview misses.
- Postrun acceptance cannot silently pass when strict rebuild/readiness fails:
  launcher wrappers promote strict postrun acceptance failure to an effective
  wrapper failure and annotate top-level `run_status.json`.
- The top-level analysis brief must preserve report-only boundary markers:
  `report_only=true`, `quality_judgment=false`,
  `decision_features_excluded=true`, and no campaign/scheduler/promotion
  mutation claims.
- Warehouse/CVRP postrun conclusions require current-run evidence payloads,
  runtime-evidence consistency, formal hypothesis prompt traces, and
  problem-owned review rules; summary prose alone is not acceptance evidence.
  Problem-summary `current_run_evidence` must match the analysis brief
  lifecycle and Phase 4 current-run state. Required or present review-input
  summaries must also be current-run, so stale optional
  measurement/runtime/continuity summaries cannot make a delegated review look
  analysis-ready. Protocol-evaluated conclusions must also match current
  protocol-accounting detail for formal-screened candidates, metric rows,
  artifact rows, and stage rows. Review-input summaries for
  protocol/measurement/runtime/continuity must also match current
  research-efficiency artifacts for aggregate and entry detail, so a stale
  optional or required review-input summary cannot be paired with a current
  problem conclusion. Quality-blocked no-protocol conclusions must also match
  current failure-taxonomy quality-block counts,
  reports-with-quality-blocks, and reason-count distribution. Failure-taxonomy
  summaries must also match the current research-efficiency reports for
  aggregate failure counts, proposal-quality counts, run-status counts, entries,
  and top examples. Prompt context/source visibility summaries must match the
  current proposal trajectory manifests for trace counts, source visibility,
  block-family totals, signal density, hypothesis-generation block-family
  totals/signal density, and per-report entries. Formal hypothesis-generation
  readiness cannot be proved by code-only, target-intent, or aggregate-only
  prompt context; when current continuity signals exist, the hypothesis trace
  itself must carry research or cross-branch lesson signal. CVRP bounded two-opt
  ready summaries must match recomputed direct-evidence counters, family lists,
  rejection counts, and top-row signal count from current
  measurement/continuity inputs. Measurement evidence must match current
  interpretation counts and `max_effect_to_mde_ratio`; CVRP bounded two-opt
  ready summaries must also match current mechanism-family mapped/unmapped row
  counts.

## Warehouse

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
- Next live question: can Scion produce useful follow-up research from `v2`, or
  correctly diagnose a real post-v2 plateau?
- A plateau conclusion is accepted only when protocol evidence shows no
  positive effect at or above MDE, runtime evidence is review-ready, and
  continuity evidence is substantive without fully missed same-mechanism
  follow-up opportunities. Problem-summary continuity evidence must also match
  the current recomputed `same_mechanism_missed` count, so a stale or hand-written
  plateau summary cannot hide missed same-mechanism follow-up.

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
  protection evidence; `two_opt_star`, cross-route, VNS, unbounded,
  `size70_two_opt_*`, and fallback phase telemetry do not satisfy this
  direct-evidence rule.

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
  `scion/docs/experiments/v0.4/v04-cvrp-size70-direct-evidence-guard-20260620.md`.
- Current disabled proposal/APS research-cap semantics:
  `scion/docs/experiments/v0.4/v04-disabled-proposal-research-caps-20260620.md`.
- Current source-read result/headroom alignment:
  `scion/docs/experiments/v0.4/v04-source-read-result-headroom-20260620.md`.
- Current CVRP prompt-diagnostic repair:
  `scion/docs/experiments/v0.4/v04-cvrp-mechanism-effect-diagnostics-prompt-repair-20260620.md`.
- Current warehouse prompt-diagnostic repair:
  `scion/docs/experiments/v0.4/v04-warehouse-diagnostics-prompt-bridge-20260620.md`.
- Current prepared `research_focus` prompt bridge:
  `scion/docs/experiments/v0.4/v04-research-focus-prompt-bridge-20260620.md`.
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

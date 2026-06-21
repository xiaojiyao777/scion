# Scion v0.4 Current State

Last updated: 2026-06-21

This file is the operational resume point, not a run log. Replace stale facts
instead of appending history. Put detailed repair evidence in focused
experiment reports, keep sparse milestones in `v0.4-history.md`, and use git
history when exact old chronology is needed.

## Operating Frame

- Branch: `codex/v04-evidence-repair-plan`.
- Boundary authority: `scion/design/scion-architecture-v3.md`.
- v0.4 closes only after Scion demonstrates effective research behavior:
  warehouse should recover useful continuous optimization from champion `v2`,
  and CVRP/VRP should produce evidence-backed solver-design follow-up.
- v0.5 is for broader experiment matrices. Do not defer v0.4 framework
  stability, prompt/context quality, runtime semantics, or effective-agent
  research to v0.5.
- Current posture: avoid broad budgets, generic truncation/compression, and
  decorative gates. Keep CVRP/warehouse semantics problem-owned and keep
  `DecisionFeatures` problem-neutral.

## Current Decision

- Framework/readiness/launcher repairs are accepted enough for focused
  warehouse and CVRP follow-up.
- v0.4 is not closed until live runs show effective research behavior.
- No LLM campaign is currently running.
- Latest accepted runtime-path repair: local commit `9b29245e` / WSL commit
  `2b2cd351` exposes both `fresh_runtime_replay_drain_limit` and
  `stage_transition_drain_limit` as structured `scion run`/launcher/readiness
  fields. Focused v0.4 prepared roots set fresh-runtime replay drain to exact
  `0` and stage-transition drain to explicit `4`, so hidden drain behavior is
  no longer inherited from core/env defaults.
- Latest accepted launch-readiness audit repair: local commit `6771a6a4` / WSL
  commit `6b4c70d6` exposes compact prepared prompt-context evidence summaries
  directly in launch readiness. The summary distinguishes prepared renderer
  evidence from live provider-prompt evidence and surfaces the CVRP
  CMT2/CMT4/resume-continuity, CVRP top-level required-evidence, warehouse
  champion-v2, warehouse required-evidence, and active code constraint rendered
  checks without changing Decision, scheduler, promotion, or Protocol inputs.
- Latest accepted prepared calibration-provenance prompt-bridge repair: local
  commit `ceaf339c` / WSL commit `26a03547` keeps
  `measurement_readiness` reduced and ref-free while surfacing compact
  calibration provenance in the sibling `calibration` block: source artifact
  `sha256` plus whitelisted `calibration_run` summary fields. Prepared
  prompt-context readiness now proves that provenance is rendered into the
  proposal-only research-focus bridge. Raw pair rows and full calibration replay
  details remain out of status and `DecisionFeatures`.
- The prior CVRP protected-case guard remains in force: CMT2/CMT4 postrun
  evidence must carry numeric objective/distance delta evidence; route-count,
  feasibility-only, case-name, or free-text continuity payloads cannot make a
  bounded two-opt summary review-ready.
- Current blocker is external WSL `gpt-5.5` provider auth, not Scion static
  readiness. `/v1/models` lists `gpt-5.5`, but strict completion preflight
  returns HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, with no active auth account available.

## Active Prepared Roots

These WSL roots supersede earlier prepared roots. They were generated at WSL
runtime commit `26a03547` after the prepared calibration-provenance prompt-bridge
repair; the corresponding local repair commit is `ceaf339c`. They retain the
CVRP required-evidence repair from WSL commit `6b4c70d6` and the explicit
drain-limit behavior from WSL commit `2b2cd351`.
Local mirrors under `/home/clawd/research/scion-experiments/` are for
inspection only. Run readiness and launch from WSL because the prepared
contracts contain WSL absolute paths.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-26a03547-calprompt-6r-gpt55-6r-gpt55-20260621T054141Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-26a03547-calprompt-4r-gpt55-4r-gpt55-20260621T054140Z-claw`

Current readiness snapshot for both roots:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- only required failure: completion preflight auth, HTTP `401`,
  `classification=not_authenticated`, `code=invalid_api_key`, auth pool has
  `active=0`, `total=1`; ignore volatile expired/refreshing substates unless
  active auth becomes available
- runtime guard: `runtime_guard_status=ok`,
  `prepared_runtime_commit=26a03547`; current WSL HEAD may include status or
  tooling commits outside runtime-guard paths after prepare, and strict
  readiness accepts that only when the guarded runtime paths are unchanged since
  prepare
- measurement handoff:
  `measurement_readiness.calibration_evidence_level=summary_only` and no
  `measurement_readiness.calibration_ref` or
  `measurement_readiness.pair_evidence` in either prepared root. The sibling
  `calibration` block carries compact source provenance: warehouse source
  artifact sha `5e34c863356bc74a9d2254dbde1d0a0945c88d56ca7201a4e033344b9718146f`
  and `calibration_run.action=modify`; CVRP source artifact sha
  `bdba8272d4eb130200ad537b51ceaef7e50323f614ea3ae29a8247ed9a771684`,
  `calibration_run.replicate_count=3`, and
  `calibration_run.runtime_policy.selected_policy=protocol_time_limits`
- campaign marker: `campaign_execution_marker_status=ok`
- secret file permissions: `launch_env_secret_permissions=ok`,
  `launch_env_mode=0o600`
- headroom guard: `checks.run_script_proposal_headroom_enforced.status=ok`;
  exact `0` proposal/APS/fresh-runtime replay drain caps are treated as
  explicitly disabled; low nonzero proposal/APS caps fail readiness instead of
  passing as warnings, fresh-runtime replay drain must be explicit rather than
  hidden behind the core legacy default, and stage-transition drain must be an
  explicit positive value (`4` in the current focused roots)
- prompt-context readiness summary:
  `checks.prompt_context_readiness_complete.detail.provider_prompt_scope=prepared_renderer_summary_not_live_provider_prompt`,
  `raw_provider_prompt_rendered=false`, `missing_rendered_paths=[]`; CVRP
  exposes `cvrp_case_protection_present=true`,
  `cvrp_resume_continuity_present=true`, and
  `cvrp_bounded_twoopt_present=true`, plus
  `cvrp_required_evidence_all_present=true` with 5 required-evidence items
  rendered, and the calibration provenance prompt fields
  `cvrp_measurement_calibration_source_artifact_present=true`,
  `cvrp_measurement_calibration_run_present=true`, and
  `cvrp_measurement_calibration_runtime_policy_present=true`; warehouse exposes
  `warehouse_v2_followup_present=true` and
  `warehouse_required_evidence_all_present=true`, plus
  `warehouse_measurement_calibration_source_artifact_present=true` and
  `warehouse_measurement_calibration_run_present=true`
- completion preflight exposes flat `completion_login_url` and
  `completion_next_step`; always fetch a fresh login URL from strict readiness
  rather than copying an old OAuth URL from notes

Do not launch either root until this WSL command reports `launch_ready=true`:

```bash
PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  "$PY" /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/check_launch_readiness.py \
  <prepared-root> --require-launch-ready --format json
```

Useful auth-recovery check:

```bash
PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  "$PY" /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/check_launch_readiness.py \
  <prepared-root> --require-launch-ready --format json | jq -r '.completion_login_url, .completion_next_step'
```

After strict readiness passes, launch the wrapper itself:

```bash
bash /home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-26a03547-calprompt-6r-gpt55-6r-gpt55-20260621T054141Z-claw/run.sh
```

Run CVRP after warehouse is underway or accepted for launch:

```bash
bash /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-26a03547-calprompt-4r-gpt55-4r-gpt55-20260621T054140Z-claw/run.sh
```

After a run, inspect `exit.txt`, `run_status.json`, and
`postrun_acceptance/readiness/`, then mirror the WSL root back to the server:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  python scripts/sync_wsl_run_root.py <wsl-run-root> \
  --execute --format json
```

Prepared-only mirrors skip current-run postrun acceptance and should return the
rsync/local-status result with `postrun_check_skip_reason=prepared_only_not_launched`;
postrun acceptance remains required after an actual launch.

## Preserved Guarantees

Keep this list compact. Detailed field-level evidence lives in `scion/TASK.md`,
the v0.4 planning summary, focused tests, and experiment reports.

- v3 boundary stays hard: LLM output, prompt ratios, branch lessons, repair
  diagnostics, and problem-owned research diagnostics remain proposal/control
  material and excluded from Decision, `DecisionFeatures`, promotion, scheduler
  state, and solver semantics unless explicitly part of Protocol.
- Launch readiness is the operator-facing authority for prepared roots. It
  checks prepared-contract identity, prompt-context bridge, runtime paths,
  model route, completion preflight, private `launch.env` permissions,
  wrapper/campaign marker consistency, and strict postrun rebuild/readiness
  behavior before launch. Low nonzero proposal/APS caps fail readiness; use
  exact `0` when the intended v0.4 behavior is no research-headroom cap. The
  same explicit-disabled convention applies to focused fresh-runtime replay
  drain. Stage-transition drain must also be explicit and positive for the
  current focused launch shape. Prompt-context readiness now exposes compact
  renderer-summary evidence in launch readiness; live provider-prompt evidence
  remains a postlaunch trace requirement.
- Problem-owned diagnostics may guide proposal context, protocol
  configuration, runtime governance, lifecycle policy, and readiness only
  through deterministic, schema-validated fields.
- Measurement readiness records calibration evidence depth as a compact status
  field. Current packaged CVRP and warehouse calibration refs are
  `summary_only`; richer external A/A artifacts must prove replay metadata
  before being labeled `full_replay`.
- Code-phase prompts must retain direct champion/current-branch/target source
  visibility and active problem-owned code constraints. Compression may remove
  boilerplate, not research-object source or active contracts.
- Hypothesis prompts should receive compact mechanism-level branch lessons,
  research-shape diagnostics, and bounded runtime/protocol feedback with
  omission/digest audit markers, not raw long prose or telemetry dumps.
- Active no-effect branch cards, sibling projections, and scheduler policy must
  agree with same-mechanism follow-up policy: ordinary no-effect/tie evidence
  remains schedulable for same-mechanism follow-up and does not emit
  runtime-saturated diversity, clean-fork guidance, or scheduler-origin
  parked-lineage blocks without a Decision-origin park marker. Cross-branch
  repeated-signature pressure preserves current active no-effect diagnostic
  follow-up, portfolio plateau lessons still block unchanged sibling copies,
  and true quality/runtime regression remains fail-closed.
- Runtime semantics must not turn budget-exhausting solver saturation, cached
  ties, comparative runtime-ratio slowdown, or inactive mechanism activation
  into meaningless replay pressure, lifecycle churn, or proposal feedback
  noise. Nominal no-effect/tie runtime summaries remain report-only; generic
  bounded/top-k runtime guidance requires actual comparative slowdown,
  runtime failure, or runtime budget saturation.
- Postrun acceptance must fail closed on missing current-run evidence, stale
  copied resume artifacts, wrapper/postrun status failures, absent source
  visibility, missing interpretation-specific review inputs, or CVRP bounded
  two-opt claims without current-run CMT2/CMT4 protection evidence.
- Screening gate, Decision, proposal feedback, and search memory must agree on
  marginal evidence: high-win-rate, non-negative, sub-practical-delta screening
  evidence is diagnostic follow-up material, not promotable proof. Global
  search-memory AVOID is driven by hard failures, not ordinary repeated
  no-effect/tie diagnostics.

## Problem Frontiers

Warehouse:

- Positive checkpoint: champion `v2` promoted in the validation-transfer rerun.
- Next question: can Scion produce useful follow-up research from `v2`, or
  correctly diagnose a real post-v2 plateau?
- Accept a plateau conclusion only with protocol evidence below MDE,
  review-ready runtime evidence, and substantive continuity evidence without
  fully missed same-mechanism follow-up opportunities.

CVRP/VRP:

- CVRP now has better target intent, branch-lesson transfer, material solver
  code generation, formal screening, mechanism telemetry, and evidence-backed
  rejection of weak/negative hypotheses.
- CVRP is still not v0.4-accepted because no current solver-design branch has
  produced continuous improvement or promotion.
- The active follow-up treats the external large-instance intra-route two-opt
  result only as proposal guidance. Review readiness requires a bounded,
  deadline-aware implementation with current-run positive effect, activation,
  objective-effect, intra-large-two-opt telemetry, and CMT2/CMT4 protection
  evidence. `two_opt_star`, cross-route, VNS, unbounded fallback, and
  continuity-only mentions do not satisfy this direct-evidence rule.
- The active CVRP prepared handoff now also carries proposal-only
  `resume_continuity_requirements`, so the zero-branch-card sparse resume must
  use copied target-intent or hypothesis trace evidence rather than being
  treated as an empty campaign.

## Next Actions

1. Refresh the WSL/local proxy login, then rerun strict launch readiness.
   `/v1/models` is not enough; completion preflight must pass.
2. Run warehouse champion-`v2` follow-up first as the simpler
   continuous-improvement proof.
3. Run the CVRP bounded large-two-opt follow-up after warehouse is underway or
   accepted for launch.
4. After each run, classify current-run evidence through the problem-owned
   postrun review rules before treating promotion/no-promotion as a research
   conclusion.

## Pointers

- Task and acceptance source: `scion/TASK.md`.
- Current planning summary:
  `scion/docs/planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`.
- Boundary and audit basis:
  `scion/design/scion-architecture-v3.md`,
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`, and
  `scion/design/v0.5-evidence-uplift-roadmap.md`.
- Detailed repair/postrun evidence: `scion/docs/experiments/v0.4/`.
- Sparse milestone index: `scion/docs/status/v0.4-history.md`.
- WSL SSH:
  `ssh -i ~/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1`.
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`.
- WSL experiments root: `/home/xjy-ubuntu/research/scion-experiments`.
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`.

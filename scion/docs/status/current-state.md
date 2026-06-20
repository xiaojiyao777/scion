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
PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  "$PY" /home/xjy-ubuntu/research/or-autoresearch-agent/scion/tools/check_launch_readiness.py \
  <prepared-root> --require-launch-ready --format json
```

reports `launch_ready=true`.

After strict readiness passes, launch from WSL by running the prepared wrapper
itself, not by reconstructing the long `scion run` command:

```bash
bash /home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-add376-markerreadiness-6r-gpt55-20260620T222137Z-claw/run.sh
```

Run the CVRP wrapper only after the warehouse run is underway or accepted for
launch:

```bash
bash /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-add376-markerreadiness-4r-gpt55-20260620T222137Z-claw/run.sh
```

The wrappers already enforce completion preflight, runtime guards, campaign
execution, strict postrun rebuild/readiness, and top-level wrapper-status
escalation. After each run, inspect `exit.txt`, `run_status.json`, and
`postrun_acceptance/readiness/`, then rsync the WSL run root back to the
same-named local mirror before server-side analysis.

Run this from the server checkout:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  python scripts/sync_wsl_run_root.py <wsl-run-root> \
  --execute --format json
```

The helper mirrors the WSL root with rsync and then reruns
`check_postrun_acceptance.py --require-current-run-ready` against the local
mirror. With `--execute`, it first verifies that the WSL source has Scion run
root markers, refuses destructive rsync targets outside the local experiment
mirror root, and includes a `local_run_status_summary` with wrapper,
pre-campaign, postrun readiness/report exit status, and launcher marker counts
for status-writer, postrun acceptance/readiness/report, and effective-wrapper
failures. Without `--execute`, it prints the planned commands only.
After rsync, the helper also requires the mirrored root `run_status.json` to be
present and readable before it returns success. `--skip-postrun-check` skips
current-run readiness only; it does not skip root-status validation.

## Active Prepared Roots

Generated on WSL at launch-authoritative prepared runtime commit `add3760a`;
the corresponding local framework repair commit is `4fbf511b`. Local mirrors
exist under `/home/clawd/research/scion-experiments/` with the same directory
names for inspection only. Run launch readiness on WSL, because prepared
contracts and wrapper scripts intentionally contain WSL absolute paths and will
fail identity checks if evaluated from the server-side mirror.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-add376-markerreadiness-6r-gpt55-20260620T222137Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-add376-markerreadiness-4r-gpt55-20260620T222137Z-claw`

Readiness snapshot:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- Required failure: completion preflight auth only
- Runtime guard status: `runtime_guard_status=ok`,
  `prepared_runtime_commit=add3760a`, and either
  `runtime_guard_reason=runtime_guard_commit_matches` or
  `runtime_guard_reason=runtime_guard_paths_unchanged_since_prepare` after
  doc-only commits. Treat all earlier prepared roots as superseded because
  runtime-guarded launcher, prompt-context, and postrun artifact-identity paths
  changed.
- `launch_env_secret_permissions=ok`; each current root reports
  `launch_env_mode=0o600`.
- Completion auth status is exposed by launch readiness in
  `completion_preflight_summary` plus flat `completion_http_status`,
  `completion_classification`, `completion_code`, and `completion_auth_pool`
  fields.
- Runtime/env refresh status is exposed by launch readiness in flat
  `runtime_guard_status`, `runtime_guard_reason`, `prepared_runtime_commit`,
  `actual_runtime_commit`, `launch_env_secret_permissions`, and
  `launch_env_mode` fields.
- Prepared static handoff reports expose
  `readiness_scope=static_only_completion_preflight_not_run` and
  `launch_blockers=["completion_preflight_not_run"]`; their legacy
  `ready=true` means static audit readiness only. Strict launch checks must use
  `readiness_scope=launch_with_completion_preflight`.
- CVRP prepared research-focus prompt bridge now carries adapter-derived
  `screening_headroom`, `mechanism_effect_ranking`, and
  `opportunity_diagnostics`; the current CVRP root reports
  `mechanism_rank_count=4` and `opportunity_diagnostic_count=5`. These remain
  proposal-visible/report-only and excluded from `DecisionFeatures`.
- Warehouse prepared research-focus prompt bridge now carries adapter-derived
  `transfer_risk`, `required_diagnostics`, and post-promotion
  `opportunity_diagnostics`; the current warehouse root reports
  `opportunity_diagnostic_count=1` and keeps plateau guards visible in prompt
  readiness. These remain proposal-visible/report-only and excluded from
  `DecisionFeatures`.
- Campaign launch contract status: `ok`; `run.sh`, `launch.env`, and
  `prepared_run_manifest.v1.json` agree on the problem/protocol/split/seeds,
  campaign directory, rounds, time limit, measurement-governance mode, and
  proposal-context ablation used by the actual `scion.cli.main run` command.
- CVRP prepared contract now verifies that protected cases named by
  `research_focus.case_protection_requirements` are present in formal
  screening; the current root reports CMT2 and CMT4 in `screening`.

Prepared run shape:

- Warehouse: 6 rounds, champion-v2 follow-up.
- CVRP: 4 rounds, bounded/deadline-aware large two-opt follow-up from external
  seed guidance.
- Proposal research caps are disabled for the current prepared roots:
  `proposal_attempt_limit=0`, `proposal_quality_loop_limit=0`. APS step/tool
  caps and observation truncation are disabled with exact `0` values while the
  wall-time guard remains enabled. Launch readiness treats missing or
  command-disconnected cap fields as blockers and treats exact disabled values
  as disabled details, not warnings or gates.

## Framework Guarantees To Preserve

Keep this section as a compact invariant checklist. Detailed repair evidence
and exact guard fields live in `scion/TASK.md` and the focused v0.4 experiment
reports.

- v3 boundary stays hard: LLM output, repair diagnostics, branch lessons,
  prompt ratios, and problem-owned research diagnostics remain tainted proposal
  material and excluded from Decision, `DecisionFeatures`, promotion, scheduler
  state, and solver semantics.
- Measurement/runtime/lifecycle/context repairs stay problem-owned or
  deterministic control-plane inputs. CVRP/warehouse diagnostics may guide
  readiness, proposal context, and postrun review only through schema-validated
  fields.
- Launch readiness is the operator-facing authority for prepared roots. It must
  guard prepared contract identity, prompt-context bridge, runtime paths, model
  route, completion preflight, private `launch.env` permissions, wrapper command
  consistency, campaign-execution marker placement, and strict postrun
  rebuild/readiness before launch.
- CVRP launch readiness must reject prepared roots whose prompt-visible
  CMT2/CMT4 protection requirements are absent from formal screening. This
  remains a problem-owned prepared-handoff contract and does not enter
  `DecisionFeatures`.
- Runtime semantics must keep budget-exhausting solver saturation and cached
  runtime ties from creating meaningless fresh-replay pressure, lifecycle churn,
  or proposal feedback noise.
- Code-phase prompts must retain direct champion/current-branch/target source
  visibility and declared integration-file visibility; compression may remove
  boilerplate, not the research object code.
- Postrun acceptance must fail closed unless warehouse/CVRP conclusions,
  review-input summaries, failure taxonomy, prompt/source visibility,
  Phase 4 evidence coverage, runtime-budget evidence, continuity evidence, and
  bounded two-opt direct evidence recompute from current-run artifacts with
  matching local/WSL-safe artifact identity. CVRP summaries now carry
  branch-depth, same-mechanism, branch-lesson, weak-positive, and
  mechanism-family continuity signals in their evidence payload and readiness
  rejects stale copies of those signals. It also requires clean launcher status:
  missing or nonzero root wrapper exit status, nonzero campaign wrapper exit
  status, top-level postrun acceptance failure markers, or nonzero postrun
  readiness/report exit status fail readiness before delegated review. Launcher
  status-writer failure markers in `run.log` and effective wrapper-exit markers
  in `exit.txt` also fail readiness, so stale clean `run_status.json` cannot
  hide failed postrun annotation. Postrun acceptance/readiness/report failure
  markers in `exit.txt` fail readiness as well, covering interrupted status
  updates before `run_status.json` is refreshed.
- Postrun inventory treats missing/unreadable root `run_status.json`, and root
  launcher status without any readable campaign execution
  `run_status.json`/`status.json`/`campaign_summary.json`, as invalid
  infra-only evidence rather than current-run research evidence. Copied or
  partial campaign artifacts remain resume snapshots until valid launcher and
  campaign execution status exist. Launch wrappers write a current
  campaign-execution marker after pre-campaign checks, and launch readiness
  rejects wrappers that omit that marker or place it after the campaign command.
  When the marker exists, stale copied resume-campaign documents older than the
  marker are rejected as `campaign_execution_artifacts_stale_resume_snapshot`.
  Postrun rebuild uses this same lifecycle source to skip current-run summary,
  failure, research-efficiency, and manifest report families when current-run
  evidence is false.
- Research-context actionability requires an allowlisted formal
  hypothesis-generation prompt trace; code, target intent, and unknown
  `hypothesis_*` call kinds cannot prove continuity signals reached the next
  proposal prompt.
- Screening gate, Decision, proposal feedback, and search memory must agree on
  marginal evidence: high-win-rate, non-negative, sub-practical-delta screening
  evidence is diagnostic follow-up material, not a promotable signal.

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
  protection evidence. `two_opt_star`, cross-route, VNS, unbounded,
  `size70_two_opt_*`, fallback phase telemetry, and continuity-only mentions do
  not satisfy this direct-evidence rule.

## Next Actions

1. Refresh WSL/local proxy login, then rerun strict launch readiness on the
   current prepared roots. `/v1/models` is not enough; completion preflight
   must pass.
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
- Repair/readiness evidence: use the current task, this status file, and the
  v0.4 planning summary first. Detailed repair reports live under
  `scion/docs/experiments/v0.4/`; read them only when auditing a specific
  guarantee or failure.
- Current WSL access:
  `ssh -i ~/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1`.
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`.
- WSL experiments root: `/home/xjy-ubuntu/research/scion-experiments`.
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`.
- For ad hoc WSL tests, set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion` because the
  conda env also has a stale editable install under
  `/home/xjy-ubuntu/projects/scion`.

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
bash /home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-f22ad5f4-pathidentity-6r-gpt55-20260620T153154Z-claw/run.sh
```

Run the CVRP wrapper only after the warehouse run is underway or accepted for
launch:

```bash
bash /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-f22ad5f4-pathidentity-4r-gpt55-20260620T153155Z-claw/run.sh
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
root markers and refuses destructive rsync targets outside the local experiment
mirror root. Without `--execute`, it prints the planned commands only.

## Active Prepared Roots

Generated on WSL at launch-authoritative prepared runtime commit `f22ad5f4`;
the corresponding local framework repair commit is `b2d19a59`. Local mirrors
exist under `/home/clawd/research/scion-experiments/` with the same directory
names for inspection only. Run launch readiness on WSL, because prepared
contracts and wrapper scripts intentionally contain WSL absolute paths and will
fail identity checks if evaluated from the server-side mirror.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-f22ad5f4-pathidentity-6r-gpt55-20260620T153154Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-f22ad5f4-pathidentity-4r-gpt55-20260620T153155Z-claw`

Readiness snapshot:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- Required failure: completion preflight auth only
- Runtime guard status: prepared runtime commit `f22ad5f4`; strict readiness
  must keep reporting runtime guard OK. The previous `febeaf11-runtimeinactive`
  roots are superseded because the postrun acceptance path-identity repair
  changed a runtime-guarded tool path.
- Campaign launch contract status: `ok`; `run.sh`, `launch.env`, and
  `prepared_run_manifest.v1.json` agree on the problem/protocol/split/seeds,
  campaign directory, rounds, time limit, measurement-governance mode, and
  proposal-context ablation used by the actual `scion.cli.main run` command.

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

- LLM output, repair diagnostics, branch lessons, prompt ratios, and
  problem-owned research diagnostics remain tainted proposal material. They must
  not enter Decision, `DecisionFeatures`, promotion, scheduler state, or solver
  semantics.
- Measurement declarations, A/A calibration, practical-delta resolution,
  runtime-model semantics, low-SNR lifecycle behavior, prompt diagnostics, and
  prepared `research_focus` projection stay problem-owned or deterministic
  control-plane inputs.
- Launch readiness is the operator-facing authority for prepared roots. It
  checks prepared contract/brief identity, prompt-context bridge, problem
  handoff, runtime guards, model route, campaign launch command consistency,
  absolute launch paths, completion preflight, strict postrun rebuild/readiness,
  and prepared/postrun rebuild identity.
- Runtime semantics distinguish comparative runtime evidence from
  budget-exhausting solver behavior. Budget-exhausting saturation and cached
  runtime ties must not create meaningless fresh-replay pressure, lifecycle
  fragmentation, or proposal feedback noise.
- Code-phase prompts must retain direct source visibility for champion/current
  branch/target files and declared integration files. Source-read schemas,
  registry caps, prompt projection, symbol reads, and retry-block placement must
  keep the current 96k source-window path available for solver-design/code
  prompts.
- Postrun acceptance cannot silently pass when strict rebuild/readiness fails:
  launcher wrappers promote strict postrun acceptance failure to an effective
  wrapper failure and annotate top-level `run_status.json`.
- The top-level analysis brief must preserve report-only boundary markers:
  `report_only=true`, `quality_judgment=false`,
  `decision_features_excluded=true`, and no campaign/scheduler/promotion
  mutation claims.
- Warehouse/CVRP postrun conclusions require current-run evidence payloads,
  formal hypothesis prompt traces, runtime-evidence consistency, and
  problem-owned review rules. Free-text summary claims alone are never
  acceptance evidence.
- Current-run warehouse/CVRP problem summaries, review-input summaries,
  failure-taxonomy summaries, prompt/source visibility summaries, measurement
  evidence, runtime-budget evidence, continuity evidence, and CVRP bounded
  two-opt direct-evidence summaries must match recomputed current-run artifacts
  before delegated review can mark the analysis ready. Review-input entry paths
  must also match current artifact identity through a local/WSL-safe path-tail
  signature.
- Runtime telemetry summaries preserve explicit inactive observations
  (`candidate_false`, activation status `inactive`) separately from numeric zero
  counters, so delegated review and proposal feedback do not confuse a
  non-triggered mechanism with a no-effect mechanism.
- Screening gate, Decision, proposal feedback, and search memory agree on
  marginal evidence: high-win-rate, non-negative, sub-practical-delta screening
  evidence is a diagnostic validation candidate, not a promotable signal.

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
- Current repair/readiness evidence:
  - `scion/docs/experiments/v0.4/v04-disabled-proposal-research-caps-20260620.md`
  - `scion/docs/experiments/v0.4/v04-source-read-result-headroom-20260620.md`
  - `scion/docs/experiments/v0.4/v04-disabled-code-surface-full-read-repair-20260620.md`
  - `scion/docs/experiments/v0.4/v04-code-prompt-solver-source-96k-projection-repair-20260620.md`
  - `scion/docs/experiments/v0.4/v04-screening-marginal-gate-decision-alignment-20260620.md`
  - `scion/docs/experiments/v0.4/v04-postrun-review-input-path-identity-repair-20260620.md`
  - `scion/docs/experiments/v0.4/v04-pathidentity-prepared-root-refresh-20260620.md`
  - `scion/docs/experiments/v0.4/v04-postrun-runtime-budget-side-summary-20260620.md`
  - `scion/docs/experiments/v0.4/v04-runtime-telemetry-inactive-observation-repair-20260620.md`
  - `scion/docs/experiments/v0.4/v04-cvrp-mechanism-effect-diagnostics-prompt-repair-20260620.md`
  - `scion/docs/experiments/v0.4/v04-warehouse-diagnostics-prompt-bridge-20260620.md`
  - `scion/docs/experiments/v0.4/v04-research-focus-prompt-bridge-20260620.md`
  - `scion/docs/experiments/v0.4/v04-postrun-wrapper-status-escalation-20260620.md`
- Current WSL access:
  `ssh -i ~/.ssh/id_ed25519_codex_wsl -p 2222 -o BatchMode=yes -o StrictHostKeyChecking=no xjy-ubuntu@127.0.0.1`.
- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`.
- WSL experiments root: `/home/xjy-ubuntu/research/scion-experiments`.
- WSL Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`.
- For ad hoc WSL tests, set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion` because the
  conda env also has a stale editable install under
  `/home/xjy-ubuntu/projects/scion`.

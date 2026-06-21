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
- Current blocker is external WSL `gpt-5.5` provider auth, not Scion static
  readiness. `/v1/models` lists `gpt-5.5`, but strict completion preflight
  returns HTTP `401`, `classification=not_authenticated`,
  `code=invalid_api_key`, with no active auth account available.

## Active Prepared Roots

These WSL roots supersede earlier prepared roots. They were generated at WSL
runtime commit `488576d9`; the corresponding server repair commit is
`6d985f84`. Local mirrors under `/home/clawd/research/scion-experiments/` are
for inspection only. Run readiness and launch from WSL because the prepared
contracts contain WSL absolute paths.

- Warehouse:
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-488576-runtime-ratio-6r-gpt55-20260621T003311Z-claw`
- CVRP:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-488576-runtime-ratio-resume-4r-gpt55-20260621T003312Z-claw`

Current readiness snapshot for both roots:

- `static_ready=true`
- `launch_ready=false`
- `failed_static_required_checks=[]`
- only required failure: completion preflight auth
- runtime guard: `runtime_guard_status=ok`,
  `prepared_runtime_commit=488576d9`; doc-only commits may report
  `runtime_guard_reason=runtime_guard_paths_unchanged_since_prepare`
- campaign marker: `campaign_execution_marker_status=ok`
- secret file permissions: `launch_env_secret_permissions=ok`,
  `launch_env_mode=0o600`
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
bash /home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-488576-runtime-ratio-6r-gpt55-20260621T003311Z-claw/run.sh
```

Run CVRP after warehouse is underway or accepted for launch:

```bash
bash /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-488576-runtime-ratio-resume-4r-gpt55-20260621T003312Z-claw/run.sh
```

After a run, inspect `exit.txt`, `run_status.json`, and
`postrun_acceptance/readiness/`, then mirror the WSL root back to the server:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  python scripts/sync_wsl_run_root.py <wsl-run-root> \
  --execute --format json
```

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
  behavior before launch.
- Problem-owned diagnostics may guide proposal context, protocol
  configuration, runtime governance, lifecycle policy, and readiness only
  through deterministic, schema-validated fields.
- Code-phase prompts must retain direct champion/current-branch/target source
  visibility and active problem-owned code constraints. Compression may remove
  boilerplate, not research-object source or active contracts.
- Hypothesis prompts should receive compact mechanism-level branch lessons,
  research-shape diagnostics, and bounded runtime/protocol feedback with
  omission/digest audit markers, not raw long prose or telemetry dumps.
- Runtime semantics must not turn budget-exhausting solver saturation, cached
  ties, comparative runtime-ratio slowdown, or inactive mechanism activation
  into meaningless replay pressure, lifecycle churn, or proposal feedback
  noise.
- Postrun acceptance must fail closed on missing current-run evidence, stale
  copied resume artifacts, wrapper/postrun status failures, absent source
  visibility, missing interpretation-specific review inputs, or CVRP bounded
  two-opt claims without current-run CMT2/CMT4 protection evidence.
- Screening gate, Decision, proposal feedback, and search memory must agree on
  marginal evidence: high-win-rate, non-negative, sub-practical-delta screening
  evidence is diagnostic follow-up material, not promotable proof.

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

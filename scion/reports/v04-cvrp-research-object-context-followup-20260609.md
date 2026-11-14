# Scion v0.4 CVRP Research-Object and Context Follow-Up

Date: 2026-06-09

This note records the current CVRP discussion so it survives context
compaction. It is a handoff note, not a final experiment report.

## Architecture Boundary

- `scion/design/scion-architecture-v3.md` remains the governing blueprint.
- LLM output is proposal-only and tainted.
- Contract, verification, protocol, and safe feature extraction remain the path
  to deterministic `DecisionFeatures`.
- BKS, gap, case hardness, and research-object readiness are CVRP
  problem-owned diagnostics. They must not enter `DecisionFeatures` or
  promotion criteria.
- Cross-branch lessons and CVRP diagnostic facts may guide proposal visibility,
  but only as advisory proposal context.

## Current 40R Snapshot

At the time of this note:

- Warehouse 40R finished:
  `/home/clawd/research/scion-experiments/v04-p2-auditability-verify-warehouse-40r-gpt55-20260609T114828Z-claw`
  - `40/40` complete.
  - wrapper exit `0`.
  - run valid.
  - model counts only `gpt-5.5`.
  - quality blocks `0`.
  - no promotion.

- CVRP 40R was still running:
  `/home/clawd/research/scion-experiments/v04-p2-auditability-verify-cvrp-40r-gpt55-20260609T114757Z-claw`
  - about `29/40` effective rounds.
  - still only screening stage.
  - validation and frozen had not been reached.
  - model counts only `gpt-5.5`.
  - quality blocks `1`.

This 40R run was launched before the CVRP formal case/seed redesign below, so
it still uses the old CVRP formal seed ledger.

## Seed and Case Findings

Hooke audited the completed CVRP 12R run:

`/home/clawd/research/scion-experiments/v04-post40r-repair-verify-cvrp-12r-gpt55-20260609T042719Z-claw-12r-gpt55-20260609T042719Z-claw`

Effective copied formal seeds were:

- screening: `[11, 29]`
- validation: `[47, 53]`
- frozen: `[61, 67]`
- canary: `[101]`

The completed CVRP 12R run exercised screening only. Validation and frozen were
not reached. The current running CVRP 40R also used the same old formal seeds
because it was launched before the redesign.

The earlier concern that recent CVRP experiments were still using only two
screening seeds is confirmed.

## Screening Saturation

The old CVRP screening split contained many cases already at or near BKS. This
made early screening a poor research object:

- old screening had many solved-to-BKS rows.
- old screening median seed-0 gap was near zero.
- CVRP candidates often failed screening before validation/frozen could test
  larger-gap cases.

This does not mean CVRP globally lacks algorithmic room. Validation and frozen
held larger-gap cases, especially X instances. The problem was mainly the
research-object/protocol mismatch at screening.

## Implemented CVRP Formal Redesign

Meitner implemented a problem-owned redesign. These files are currently changed
in the working tree:

- `scion/scion/problems/cvrp/formal/split_manifest.yaml`
- `scion/scion/problems/cvrp/formal/seed_ledger.yaml`
- `scion/scion/problems/cvrp/formal/protocol.yaml`
- `scion/scion/problems/cvrp/formal/budgets.json`
- `scion/scion/problems/cvrp/formal/manifests/screening.json`
- `scion/scion/problems/cvrp/formal/manifests/validation.json`
- `scion/scion/problems/cvrp/formal/manifests/frozen.json`
- `scion/scion/problems/cvrp/formal/manifests/final.json`
- `scion/scion/problems/cvrp/formal/README.md`
- `scion/scion/tests/test_cvrp_formal_readiness.py`

Redesign summary:

- screening seeds: `[11, 29, 43, 59]`
- validation seeds: `[47, 53, 71, 83]`
- frozen seeds: `[61, 67, 89]`
- final evidence seeds remain `[0, 1, 2]`

Main acceptance checks:

- screening has 16 reference-clean, benchmark-feasible, route-clean cases.
- screening has no solved-to-BKS rows.
- screening seed-0 gap range is approximately `2.624%` to `7.586%`.
- validation and frozen remain disjoint from screening.
- frozen remains an X-only holdout.
- BKS/gap stays in problem-owned diagnostics and final evidence only.

Focused test already passed:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/test_cvrp_formal_readiness.py -q
```

Result: `7 passed`.

## VNS Absorption Hypothesis

The strong claim was:

> Scion agent changes are structurally erased by VNS, so candidate and
> champion outputs become identical even on cases with BKS gap.

Hooke and Plato both found the strong version is false.

Evidence:

- CVRP 12R metrics contain pair-level non-tie wins/losses.
- CVRP 40R formal artifacts also contain many non-tie pairs.
- Agent-visible CVRP surface is `solver_design`, not only an operator hook.
- Editable files include `policies/baseline_algorithm.py` and
  `policies/baseline_modules/*.py`.
- Agent can target local search/VNS, scheduler, destroy/repair, acceptance,
  construction, state, and related solver-design modules.

Plato's artifact classification:

- 12R non-ties appeared in `destroy_repair.py`, `scheduler.py`,
  `local_search.py`, and `construction.py`.
- 40R non-ties appeared across `local_search.py`, `destroy_repair.py`,
  `scheduler.py`, `acceptance.py`, `construction.py`, and `route_merge.py`.

Controlled temporary run on `E-n101-k8`, seed `11`:

- baseline: total distance `880.0`
- explicit pre-VNS route reversal perturbation: total distance `860.0`
- VNS disabled: total distance `884.0`

Conclusion:

- VNS does not erase all Scion modifications as a framework property.
- A narrower surface-specific risk remains: weak upstream changes or poorly
  integrated modules can be absorbed by the existing ALNS/VNS basin and produce
  all-tie outcomes.
- Future experiment analysis should classify outcomes by target surface and
  mechanism family instead of treating CVRP as globally all-tie.

## Context Degeneration Risk

This remains a high-priority issue.

External audit and prior Scion experiment analyses point to the same risk:

- LLM prompts can grow into a large mix of algorithm source, governance rules,
  telemetry, compliance metadata, and historical logs.
- One audited prompt was described as roughly `116k` characters, with about
  `65%` source/governance material.
- Direct branch research feedback and failure lessons were tiny by comparison
  in that audit, around a few hundred characters.

Interpretation:

- The goal is not simply to reduce tokens or tool calls.
- The goal is to preserve sufficient research context while increasing the
  signal-to-noise ratio for algorithmic research.
- The agent must still see problem mechanics, active solver facts, relevant
  source, branch history, screening/runtime feedback, and cross-branch lessons.
- The failure mode is when governance and raw logs dominate attention, causing
  the model to optimize for framework compliance rather than clear algorithmic
  hypotheses.

This should be treated as a separate targeted optimization after the current
CVRP 40R finishes and after the CVRP formal case/seed redesign is committed.

## Proposed Context Follow-Up

Run a focused context/profile audit over:

- the current CVRP 40R prompt manifests;
- the completed CVRP 12R prompt manifests;
- one warehouse run as a contrast case.

Measure per phase:

- total prompt chars/tokens;
- source-code block share;
- governance/compliance block share;
- tool observation block share;
- branch-local feedback share;
- cross-branch lesson share;
- runtime/screening feedback share;
- whether branch lessons and prior failures are visible as concise action
  guidance;
- whether large raw observations duplicate compact active facts.

Likely remediation directions:

- make algorithm profile the default for hypothesis generation;
- include repair/governance blocks only when the branch is actually in repair
  or audit mode;
- replace repeated full source blocks with source summaries plus focused target
  file reads when possible;
- promote branch-local history and failure lessons into a compact, structured
  research-feedback block;
- keep full prompt manifests and raw observations as audit artifacts, not
  necessarily as default model-visible context;
- add prompt-block accounting so future runs can show research signal vs
  governance/source overhead.

Acceptance criteria for the context fix:

- context remains sufficient for real algorithm work;
- branch history and failure lessons become materially visible;
- no v3 boundary regression;
- tool/context reductions do not remove needed information;
- later 4R/8R CVRP validation shows no quality-block or missing-context
  regression.

## Recommended Next Steps

1. Wait for the current CVRP 40R to finish.
2. Analyze the CVRP 40R by branch and surface family, using Hooke/Plato's
   corrected interpretation:
   - not globally all-tie;
   - inspect surface-specific all-tie behavior;
   - inspect why screening still blocked validation/frozen.
3. Review and commit the CVRP formal case/seed redesign.
4. Run a short CVRP verification sequence on the new split:
   - start at 4R;
   - then 8R/12R if clean;
   - only then longer 20R/40R.
5. Start a dedicated context/profile optimization phase.

## Open Questions

- Does the new harder screening split produce enough non-tie evidence without
  causing runtime instability?
- Are win/loss signals more informative with 4 screening seeds?
- Which surface families still produce all-tie outcomes under the new split?
- Should CVRP proposal context include a problem-owned "research object
  readiness" summary showing case gap bands and saturation warnings as
  proposal-only advisory context?
- Can branch-local history and failure lessons be raised in prompt salience
  without making them hard constraints?

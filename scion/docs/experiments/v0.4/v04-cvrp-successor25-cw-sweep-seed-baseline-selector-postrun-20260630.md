# CVRP Successor25 CW/Sweep Seed Baseline Selector Postrun - 2026-06-30

## Run Identity

- Run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor25-cw-sweep-seed-baseline-selector-2r-gpt55-20260630T101601Z-claw`
- WSL runner repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629`
- Runner commit: `d501b900`
- Model route: `gpt-5.5` via `http://127.0.0.1:8080`
- Start/end: `2026-06-30T10:16:05Z` / `2026-06-30T11:25:56Z`
- Wrapper exit status: `0`
- Campaign stop reason: `max_rounds_exhausted`
- Postrun acceptance: ready for analysis

## Validity

The run is valid and complete:

- requested rounds: `2`;
- effective protocol rounds: `2`;
- screening protocol rows: `2`;
- validation/frozen rows: `0`;
- proposal quality blocks: `0`;
- verification failure consumed candidates: `0`;
- postrun readiness: `current_run_analysis_ready=true`,
  `delegation_ready=true`, `failed_required_checks=[]`;
- latest champion version: `1`.

## Mechanism

The candidate targeted the intended mechanism:

- branch: `c157153c-4790-4d78-9876-0f78f0245f39`;
- mechanism: `cw_sweep_seed_baseline_selector`;
- primary target: `policies/baseline_modules/construction.py`;
- scheduler scope: invocation from `_initial_solution`;
- formal candidate replay identity: complete.

The patch built the existing Clarke-Wright, sweep, and capacity-balanced seeds,
compared them with the current default seed using the solver objective key, and
returned the best feasible route-limit-preserving seed.

## Objective Evidence

The solver evidence is negative for v0.4 closeout:

- rows at or above MDE: `0`;
- positive rows: `0`;
- rows with CI high below MDE: `2`;
- max median delta: `0.0`;
- max effect/MDE ratio: `0.0`;
- MDE at 80% power: `9.9`;
- interpretation: `all_available_ci_high_below_mde`.

Protocol rows:

| Row | Pairs | Median delta | CI | Decision | Interpretation |
|---|---:|---:|---|---|---|
| 1 | 32 | `0.0` | `[0.0, 0.0]` | `expand_screening` | no aggregate effect |
| 2 | 48 | `0.0` | `[0.0, 0.0]` | `abandon` | no aggregate effect / quality regression |

Case-level signal:

- row 1 was all-tie at median level, with one positive pair on `B-n63-k10` and
  one positive pair on `P-n65-k10`;
- row 2 had losses on `A-n64-k9` (`-1.5`) and `B-n67-k10` (`-2.5`), one
  `P-n65-k10` positive-pair caveat, and otherwise median ties.

## Telemetry

Activation and runtime were observed:

- row 1: `cw_sweep_seed_baseline_selector` runtime observed in `32/32` pairs;
- row 2: runtime observed in `48/48` pairs.

Direct seed-baseline telemetry was weak:

- row 1: direct effect fields were zero in `32/32` pairs;
- row 2: `4/48` pairs had positive direct seed delta, all on `B-n67-k10`, with
  `selector_best_delta=956.0`;
- those four direct seed wins did not translate into reliable downstream
  solver effect: final `B-n67-k10` pair deltas were `-26.0`, `-5.0`, `0.0`,
  and `37.0`, with case median `-2.5`.

Campaign-level telemetry diagnostics still reported
`TELEMETRY_EFFECT_ZERO_DIAGNOSTIC` for the mechanism, so treat the direct
attribution as insufficient for a same-mechanism solver claim.

## Interpretation

Successor25 is valid framework evidence and negative solver evidence.

It demonstrates that the repaired guidance can drive the agent to a
construction-owned clean fork with same-run seed-baseline comparison. It does
not support a solver-improvement claim because formal objective evidence is
all below MDE, the expanded row was abandoned, and the only direct seed delta
cluster did not survive downstream search.

Classification:

- `seed-effect-mostly-noop-below-MDE`;
- with `direct-seed-delta-isolated-to-B-n67` and
  `downstream-effect-not-preserved` caveats.

## Next Action

Do not continue unchanged `cw_sweep_seed_baseline_selector`.

Before launching another CVRP campaign, update the problem-owned guidance and
successor catalog so successor25 is reviewed/default-avoid. The next solver
slot should be designed as a materially different causal path. The strongest
new evidence from this run is not "construction seed selection works"; it is
that initial seed improvement can be observed on a narrow case but is not
preserved by the current downstream search.

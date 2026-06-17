# CVRP Embedded-VNS Share Trigger Focus

Date: 2026-06-17
Branch: `codex/v04-evidence-repair-plan`
Commits: `0dc7f83`, `c55d8ae`, `3c04125`, `384644c`

## Purpose

The priority-guided agentic cadence-trigger field check selected the intended
CVRP scheduler target, but its generated trigger was rejected: it saved some
runtime while losing objective quality on `CMT4` and `X-n110-k13`. This report
turns that failed candidate into focused no-LLM mechanism diagnostics.

The question is whether adaptive embedded-VNS thinning can preserve the hard
case quality of canonical ALNS+VNS while recovering some of the runtime/ALNS
iteration headroom observed in raw cadence-2.

## Repairs Added

- `adaptive_embedded_vns_early8_cadence2`: protect embedded VNS for the first
  eight ALNS iterations, then use cadence-2 plus repaired-candidate improvement
  rescue.
- `adaptive_embedded_vns_share60_cadence2`: protect embedded VNS while its
  ALNS-loop runtime share is below `0.60`, then use cadence-2 plus rescue.
- `adaptive_embedded_vns_share70_cadence2`: same as share60 but with a `0.70`
  floor.
- Share-floor semantics were fixed in `384644c` so the first ALNS iteration is
  protected when the share floor is configured. The pre-fix share60/share70
  runs are diagnostic for the bug only; the accepted share-floor evidence uses
  the fixed share70 run.

All changes are CVRP-owned scheduler/matrix diagnostics. Canonical defaults
remain unchanged, and no generic `DecisionFeatures`, gate, Protocol, lifecycle,
or promotion behavior changed.

## Local Acceptance

Commands:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py \
  scion/scion/tests/unit/test_cvrp_scheduler_embedded_vns_trigger.py \
  scion/scion/tests/unit/test_cvrp_solver_design_provider.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py -q
```

Result before prompt update: `56 passed`.

Additional focused checks:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m py_compile \
  scion/scion/problems/cvrp/policies/baseline_modules/config.py \
  scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py \
  scion/scion/problems/cvrp/evidence/mechanism_matrix.py \
  scion/tools/cvrp_mechanism_matrix.py

git diff --check
```

Both passed.

## WSL Runs

All WSL runs used:

- WSL repo: `/home/xjy-ubuntu/research/or-autoresearch-agent`
- Server sync root: `/home/clawd/research/scion-experiments`
- Cases: `A-n64-k9`, `P-n65-k10`, `CMT4`, `X-n110-k13`
- Seeds: `41`, `42`, `43`, `44`
- Time budget: `3s`
- Mechanisms: canonical plus focused adaptive embedded-VNS variants

Primary artifact directories:

- `/home/clawd/research/scion-experiments/v04-cvrp-early8-cadence2-focus-0dc7f83-20260617T212012Z`
- `/home/clawd/research/scion-experiments/v04-cvrp-share60-cadence2-focus-c55d8ae-20260617T212635Z`
- `/home/clawd/research/scion-experiments/v04-cvrp-share70-cadence2-focus-3c04125-20260617T213142Z`
- `/home/clawd/research/scion-experiments/v04-cvrp-share70-cadence2-fixed-focus-384644c-20260617T213623Z`

The fixed share70 run is the accepted share-floor run. It completed `64/64`
rows with summary status `completed`.

Command shape for the fixed run:

```bash
PYTHONPATH=$PWD/scion /home/xjy-ubuntu/miniconda3/envs/scion/bin/python \
  scion/tools/cvrp_mechanism_matrix.py \
  --case-id A-n64-k9 --case-id P-n65-k10 \
  --case-id CMT4 --case-id X-n110-k13 \
  --case-limit 4 \
  --seed 41 --seed 42 --seed 43 --seed 44 \
  --mechanism canonical_alns_vns \
  --mechanism adaptive_embedded_vns_cadence2 \
  --mechanism adaptive_embedded_vns_early8_cadence2 \
  --mechanism adaptive_embedded_vns_share70_cadence2 \
  --time-budget-sec 3 \
  --output-dir /home/xjy-ubuntu/research/scion-experiments/v04-cvrp-share70-cadence2-fixed-focus-384644c-20260617T213623Z
```

## Fixed Share70 Results

Lower paired delta is better. Deltas are candidate total distance minus
canonical total distance for the same case/seed.

| Mechanism | Overall W/L/T | Mean Delta | Median Delta | Mean Embedded-VNS Share | Mean ALNS Iterations |
| --- | ---: | ---: | ---: | ---: | ---: |
| `adaptive_embedded_vns_cadence2` | `2/7/7` | `+2.81` | `0.0` | `0.655` | `13.56` |
| `adaptive_embedded_vns_early8_cadence2` | `2/3/11` | `+0.25` | `0.0` | `0.742` | `9.81` |
| `adaptive_embedded_vns_share70_cadence2` | `2/3/11` | `-0.12` | `0.0` | `0.698` | `12.94` |

Case-level share70 deltas:

| Case | Deltas | W/L/T | Mean | Median |
| --- | --- | ---: | ---: | ---: |
| `A-n64-k9` | `[4.0, 0.0, 0.0, 0.0]` | `0/1/3` | `+1.0` | `0.0` |
| `CMT4` | `[0.0, 0.0, 0.0, 0.0]` | `0/0/4` | `0.0` | `0.0` |
| `P-n65-k10` | `[-6.0, 2.0, -11.0, 9.0]` | `2/2/0` | `-1.5` | `-2.0` |
| `X-n110-k13` | `[0.0, 0.0, 0.0, 0.0]` | `0/0/4` | `0.0` | `0.0` |

## Interpretation

- Raw cadence-2 remains too aggressive for CMT4: it loses `0/3/1` on CMT4
  with mean delta about `+10`.
- Early-8 protects CMT4 and X-n110 but mostly reverts hard cases to canonical
  behavior; it is useful as a failure-mode diagnostic, not a compelling runtime
  candidate.
- Share60 and pre-fix share70 exposed an implementation trap: without first
  ALNS-iteration protection, the share floor starts too late and behaves like
  raw cadence-2.
- Fixed share70 is the best current scheduler-trigger opportunity. It preserves
  CMT4 and X-n110 neutrality, improves the P-n65 focused mean, and uses less
  embedded-VNS share than early-8. It is still a focused diagnostic, not a
  production default.

## Next Gate

Expose fixed share70 cadence-2 as the current CVRP solver-design target
guidance. The next agentic CVRP run should refine this scheduler-owned trigger,
not repeat raw cadence-2, recent-best stall gates, broad VNS removal, or
local-search detours without an evidence-backed deviation note.

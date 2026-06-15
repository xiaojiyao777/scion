# CVRP Size70 Fixed-Candidate Validation Design - 2026-06-15

## Purpose

The size70 two-opt polish is the leading CVRP mechanism seed after no-LLM
diagnostic replay. This document defines the next validation sequence before
any merge, promotion claim, or broad LLM campaign.

This design follows the v3 boundary: size70 two-opt remains human-approved
hypothesis material until replayed through appropriate deterministic evidence.
BKS/gap/runtime/timeout/two-opt activation/best-update diagnostics remain
problem-owned postrun material and must not enter generic core or
`DecisionFeatures`.

## Recommendation

Use both fixed-candidate replay and a short seeded Scion run, in this order:

1. Fixed-candidate validation-grade replay first.
2. Only if that passes, run a short seeded Scion CVRP agent/debug campaign to
   verify that proposal context, Contract, Verification, and Protocol can
   preserve and act on the mechanism.

Do not treat a short LLM run as proof of the mechanism. Direct replay still is
not promotion evidence, but it is the required next mechanism-validity gate.

## Pre-Registered Replay Tiers

### Tier 1: Large-X Completion Diagnostic

- Cases: `X-n401-k29`, `X-n573-k30`, `X-n641-k35`, `X-n1001-k43`
- Seeds: `61`, `67`, `89`
- Multipliers: `1`, `2`, `4`
- Candidate keys: `36`
- Include `m=2`; the previous candidate replay intentionally omitted it, which
  created key-set ambiguity against the champion runtime curve.
- Use `--resume` and explicit timeout completeness accounting.

### Tier 2: Formal Validation

- Cases: all `12` cases from
  `scion/scion/problems/cvrp/formal/manifests/validation.json`
- Seeds: `47`, `53`, `71`, `83`
- Multiplier: `1`
- Candidate/champion pairs: `48`
- Runtime budgets: protocol-resolved formal budgets:
  - dimension `<=100`: `30s`
  - dimension `101-149`: `45s`
  - dimension `150-250`: `60s`

### Tier 3: Frozen, Only If Validation Passes

- Cases: all `12` cases from
  `scion/scion/problems/cvrp/formal/manifests/frozen.json`
- Seeds: `61`, `67`, `89`
- Formal evidence multiplier: `1`
- Optional diagnostic multipliers: `2`, `4`; keep these outside promotion and
  Decision.

## Acceptance Criteria

Mechanism validity:

- candidate canary and verification pass;
- outputs are feasible and objective is recomputable;
- no fleet violation regression;
- no systematic completed-pair objective loss;
- validation aggregate is interpreted against the CVRP A/A MDE, about `9.6` to
  `9.9` raw `total_distance`, in problem-owned reporting;
- no candidate-only timeout, and all planned keys are accounted;
- double timeouts are runtime-policy diagnostics, not positive evidence;
- eligible `customer_count >= 70` rows show `two_opt_polish_initial` and/or
  `two_opt_polish_embedded` activity;
- ineligible rows show zero activation and tie;
- `best_update_count=0` is acceptable for this mechanism only if final
  objective movement plus two-opt phase accepts show the construction/polish
  path. It must not be described as deeper ALNS incumbent-update improvement.

Promotion evidence:

- requires formal validation then frozen pass through Scion Protocol gates;
- requires canary, confidence/gate success, complete key accounting, and no
  critical runtime or verification failure;
- direct replay alone is never promotion evidence.

## Tooling

Reuse `scion/tools/cvrp_runtime_curve.py` for Tier 1 where possible:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
python /home/clawd/research/or-autoresearch-agent/scion/tools/cvrp_runtime_curve.py \
  --repo-root /home/clawd/research/or-autoresearch-agent \
  --workspace <candidate_size70_workspace> \
  --data-root /home/clawd/research/or-autoresearch-agent/vrp \
  --selected-surface solver_design \
  --parallelism 1 \
  --timeout-padding-sec 900 \
  --resume \
  --case-budget cvrplib/X/X-n401-k29.vrp=90 \
  --case-budget cvrplib/X/X-n573-k30.vrp=120 \
  --case-budget cvrplib/X/X-n641-k35.vrp=120 \
  --case-budget cvrplib/X/X-n1001-k43.vrp=120 \
  --seed 61 --seed 67 --seed 89 \
  --multiplier 1 --multiplier 2 --multiplier 4 \
  --output-dir <run_root>/results/candidate_size70_largeX_full
```

Current minimal tool gap: the existing fixed-candidate replay path is oriented
around screening candidates from `formal_candidates/index.jsonl`. v0.4 needs a
stage-aware fixed-candidate replay path for `validation|frozen`, and it should
accept an external full-file candidate artifact for this size70 patch without
forcing an LLM campaign to generate it first.

## Do Not Do Yet

- Do not merge or promote size70.
- Do not encode BKS/gap/runtime/two-opt fields into `DecisionFeatures`.
- Do not tune the `customer_count >= 70` threshold after seeing validation rows
  unless a new pre-registered candidate is declared.
- Do not run solver-heavy CVRP replay while a time-sensitive warehouse debug is
  active.

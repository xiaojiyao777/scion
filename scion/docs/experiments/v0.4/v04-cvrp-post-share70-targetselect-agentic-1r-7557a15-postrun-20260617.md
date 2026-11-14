# CVRP Post-Share70 Target-Selection Agentic 1R Postrun

Date: 2026-06-17
Branch: `codex/v04-evidence-repair-plan`
Commit: `7557a15`

WSL run:
`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-post-share70-targetselect-agentic-1r-7557a15-20260617T230654Z`

Server sync:
`/home/clawd/research/scion-experiments/v04-cvrp-post-share70-targetselect-agentic-1r-7557a15-20260617T230654Z`

## Purpose

This was the first short CVRP agentic field check after share70 cap/tail
diagnostics. The goal was not to promote a solver change. The goal was to test
whether updated CVRP-owned guidance would stop treating share70 scheduler
variants as the default target and instead select a concrete non-scheduler
solver-design owner unless it had a materially different X-n110 tail repair.

No generic Decision, Protocol, lifecycle, promotion, or `DecisionFeatures`
behavior changed.

## Launch

The run executed in WSL through the reverse SSH channel and was synced back to
the server experiment root.

Command shape:

```bash
python -m scion.cli.main run \
  --problem .../cvrp/problem.yaml \
  --protocol .../cvrp/formal/protocol.yaml \
  --split .../cvrp/formal/split_manifest.yaml \
  --seeds .../cvrp/formal/seed_ledger.yaml \
  --campaign-dir "$ROOT/campaign" \
  --rounds 1 \
  --time-limit-sec 30 \
  --agentic-session-timeout-sec 900 \
  --measurement-governance on \
  --proposal-context-ablation compact-measurement-diagnostics \
  --disable-early-stop \
  --agentic-proposal
```

Model/proxy settings:

- `SCION_MODEL=gpt-5.5`
- `SCION_BASE_URL=http://127.0.0.1:8080`
- `SCION_API_KEY=pwd`
- `SCION_LLM_TIMEOUT_SEC=120`
- `SCION_LLM_CODE_TIMEOUT_SEC=240`
- `SCION_LLM_MAX_RETRIES=1`
- `SCION_SDK_MAX_RETRIES=0`
- `SCION_PROBLEM_DATA_ROOT=/home/xjy-ubuntu/research/or-autoresearch-agent/vrp`

## Run Outcome

- Wrapper exit: `0`.
- Run validity: `valid`.
- Effective rounds: `1/1`.
- Formal candidate artifacts: `1`.
- Screening pairs: `32/32` attempted and valid, `0` failed pairs.
- Champion remained `v1`.
- LLM calls: `hypothesis_target_intent=1`, `hypothesis=1`,
  `tool_selection=6`, `code=1`, all `gpt-5.5`.
- Decision: `expand_screening`.
- Decision reason: `SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`.

Formal candidate:

`campaign/artifacts/formal_candidates/d6335b47/screening-9159d1be-ee05-4774-889d-5312047b8a19-551f018e12048c7b/`

## Steering Evidence

The target-intent trace selected a non-scheduler solver-design owner:

- `target_file`: `policies/baseline_modules/destroy_repair.py`
- `mechanism_family`: `destroy_repair`
- `mechanism_id`: `route_merge_repair`

The target-intent notes explicitly avoided repeating embedded-VNS share/cap
rescue variants and assigned ownership to `destroy_repair.py` because
route-count losses can arise when greedy/regret repair falls back to
`_insert_new_route`.

The generated candidate added a post-repair route absorption pass after
greedy/regret insertion and added scheduler wiring only to pass `context` and
`max_routes` into repair operators. The candidate patch modified:

- `policies/baseline_modules/destroy_repair.py`
- `policies/baseline_modules/scheduler.py`

## Screening Evidence

Screening used the formal CVRP protocol with cases:

- `A-n64-k9`, `B-n63-k10`, `E-n101-k14`, `P-n65-k10`
- `CMT2`, `CMT4`, `M-n200-k17`, `X-n110-k13`

Seeds: `11`, `29`, `43`, `59`.

Pair-level results, using favorable champion-minus-candidate distance deltas:

- W/L/T: `10/3/19`
- Mean favorable delta: `+1.406`
- Median delta: `0.0`
- Runtime median ratio: `0.9994`
- Runtime median delta: `-22 ms`

Case-level deltas:

| Case | W/L/T | Mean | Median | Deltas |
| --- | ---: | ---: | ---: | --- |
| `A-n64-k9` | `3/0/1` | `+9.0` | `+8.5` | `[0, 4, 13, 19]` |
| `B-n63-k10` | `2/0/2` | `+3.75` | `+2.0` | `[0, 11, 4, 0]` |
| `E-n101-k14` | `2/0/2` | `+2.0` | `+0.5` | `[1, 0, 0, 7]` |
| `CMT2` | `2/2/0` | `-3.25` | `-1.0` | `[-32, 21, 8, -10]` |
| `P-n65-k10` | `1/1/2` | `-0.25` | `0.0` | `[6, -7, 0, 0]` |
| `CMT4` | `0/0/4` | `0.0` | `0.0` | `[0, 0, 0, 0]` |
| `M-n200-k17` | `0/0/4` | `0.0` | `0.0` | `[0, 0, 0, 0]` |
| `X-n110-k13` | `0/0/4` | `0.0` | `0.0` | `[0, 0, 0, 0]` |

Campaign summary classified case-level winners as `A-n64-k9`, `B-n63-k10`,
and `E-n101-k14`, with no case-level losses.

## Mechanism Telemetry

The candidate emitted direct mechanism telemetry for `route_merge_repair`:

- Phase runtime observed on all `32` candidate pairs.
- Total `route_merge_repair` phase runtime: `514 ms`.
- `route_merge_repair` phase improvement counts were nonzero on `19/32`
  candidate pairs, sum `69`.
- `route_merge_repair` phase best-delta was nonzero on `19/32` candidate
  pairs, sum `1297`.

This is materially better attribution than the earlier share70 agentic check:
the selected mechanism has activation and objective-effect evidence under its
own phase id.

## Interpretation

This run accepts the post-share70 steering repair in the field. Scion did not
repeat share70 floor, hardcap, softrescue, tail6, or another scheduler default.
It selected a concrete non-scheduler owner and generated a real mechanism with
direct effect telemetry.

The solver change is not a promotion. The formal decision is correctly
`expand_screening`, not promote: aggregate evidence is low-SNR with median
delta `0.0`, but the candidate has a positive pair-level shape, no failed
pairs, no case-level losses, and neutral X-n110/CMT4/M-n200 behavior.

The next CVRP work should continue the `route_merge_repair` branch as a
same-mechanism follow-up. The most useful next slice is to inspect the
route-merge activation/effect rows and refine when the consolidation pass runs,
not to return to scheduler share70 variants.

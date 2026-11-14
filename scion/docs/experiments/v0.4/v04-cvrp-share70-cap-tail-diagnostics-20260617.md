# CVRP Share70 Cap And Tail Diagnostics

Date: 2026-06-17
Branch: `codex/v04-evidence-repair-plan`
Commits: `df8ac68`, `d1c0929`

## Purpose

The share70 agentic field check selected the intended scheduler mechanism but
kept an X-n110 tail loss. This report tests whether that loss was caused by
the generated hard cap itself, by missing repair-improvement rescue, or by too
little post-cap VNS polish.

All changes are CVRP-owned solver-design diagnostics. Canonical defaults remain
unchanged. No generic Decision, Protocol, lifecycle, promotion, or
`DecisionFeatures` behavior changed.

## Repairs Added

- `EMBEDDED_VNS_MAX_RUNTIME_SHARE`: optional cap for embedded VNS runtime share.
- `EMBEDDED_VNS_CAP_REPAIR_IMPROVEMENT_RESCUE`: optional rescue above the cap
  when the repaired candidate already improves current/best.
- `EMBEDDED_VNS_CAP_RESCUE_CADENCE`: optional sparse rescue above the cap.
- `EMBEDDED_VNS_DIAGNOSTIC_PHASE`: optional mechanism-specific telemetry phase.
- New mechanism-matrix probes:
  - `adaptive_embedded_vns_share70_hardcap_cadence2`
  - `adaptive_embedded_vns_share70_softrescue_cadence2`
  - `adaptive_embedded_vns_share70_tail6_cadence2`

When a diagnostic phase is configured, the scheduler records
`context.record_iteration`, `context.record_phase`, and direct
`context.record_move` effect telemetry under
`adaptive_embedded_vns_share70_trigger`.

## Local Acceptance

Commands:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/evidence/test_cvrp_mechanism_matrix.py \
  scion/scion/tests/unit/test_cvrp_scheduler_embedded_vns_trigger.py -q
```

Result: `20 passed`.

Prompt/provider follow-up:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_cvrp_solver_design_provider.py \
  scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py -q
```

Result: `43 passed`.

Additional checks:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m py_compile \
  scion/scion/problems/cvrp/policies/baseline_modules/config.py \
  scion/scion/problems/cvrp/policies/baseline_modules/scheduler.py \
  scion/scion/problems/cvrp/evidence/mechanism_matrix.py \
  scion/tools/cvrp_mechanism_matrix.py

git diff --check
```

Both passed. Local 1s smoke checks also verified that the new mechanisms run
and emit direct trigger effect telemetry.

## WSL Runs

All runs used a clean WSL worktree synchronized by git and artifacts synced
back by rsync.

### 3s Cap Matrix

Run:

`/home/clawd/research/scion-experiments/v04-cvrp-share70-cap-diagnostic-df8ac68-20260617T2238Z`

Commit: `df8ac68`

Cases: `A-n64-k9`, `CMT4`, `M-n200-k17`, `X-n110-k13`

Seeds: `11`, `29`, `43`, `59`

Mechanisms: canonical, share70 floor, hardcap, softrescue

Result: `64/64` jobs completed, wrapper exit `0`.

This run validated the overlays and direct trigger telemetry, but it was too
shallow to decide the X-n110 tail: all X-n110 mechanisms returned the same
`15523` objective at 3s. Treat it as a smoke/telemetry diagnostic, not tail-loss
evidence.

### X-n110 30s Cap Matrix

Run:

`/home/clawd/research/scion-experiments/v04-cvrp-share70-cap-x30-diagnostic-df8ac68-20260617T2245Z`

Commit: `df8ac68`

Case: `X-n110-k13`

Seeds: `11`, `29`, `43`, `59`

Mechanisms: canonical, share70 floor, hardcap, softrescue

Result: `16/16` jobs completed, wrapper exit `0`.

Against canonical, all three share70 variants had the same objective deltas:

| Mechanism | W/L/T | Mean | Median | Deltas |
| --- | ---: | ---: | ---: | --- |
| `adaptive_embedded_vns_share70_cadence2` | `0/2/2` | `+32.0` | `+6.0` | `[12, 0, 116, 0]` |
| `adaptive_embedded_vns_share70_hardcap_cadence2` | `0/2/2` | `+32.0` | `+6.0` | `[12, 0, 116, 0]` |
| `adaptive_embedded_vns_share70_softrescue_cadence2` | `0/2/2` | `+32.0` | `+6.0` | `[12, 0, 116, 0]` |

Hardcap and softrescue reduced embedded-VNS share and emitted direct trigger
effect telemetry, but they did not repair the X-n110 seed-43 loss.

### X-n110 30s Tail6 Matrix

Run:

`/home/clawd/research/scion-experiments/v04-cvrp-share70-tail6-x30-diagnostic-d1c0929-20260617T2258Z`

Commit: `d1c0929`

Case: `X-n110-k13`

Seeds: `11`, `29`, `43`, `59`

Mechanisms: canonical, share70 floor, tail6

Result: `12/12` jobs completed, wrapper exit `0`.

Against canonical:

| Mechanism | W/L/T | Mean | Median | Deltas |
| --- | ---: | ---: | ---: | --- |
| `adaptive_embedded_vns_share70_cadence2` | `0/2/2` | `+32.0` | `+6.0` | `[12, 0, 116, 0]` |
| `adaptive_embedded_vns_share70_tail6_cadence2` | `0/2/2` | `+32.0` | `+6.0` | `[12, 0, 116, 0]` |

Tail6 reduced mean embedded-VNS share from about `0.876` to `0.776` and emitted
direct trigger effect telemetry, but it still failed to recover the X-n110
seed-43 canonical improvement.

## Interpretation

- Direct mechanism effect telemetry is accepted. The new diagnostic phase
  records activation, phase runtime, and `record_move`-based effect attribution
  under `adaptive_embedded_vns_share70_trigger`.
- The X-n110 tail loss is not fixed by hard cap, repair-improvement rescue, or
  sparse post-cap rescue every sixth ALNS iteration.
- The share70 scheduler family remains useful as research-loop evidence and
  mechanism diagnostics, but the tested floor/hardcap/softrescue/tail6 variants
  are rejected as production solver improvements.
- The next CVRP agent should not repeat these scheduler variants. It should
  either propose a materially different X-tail repair with explicit evidence or
  pivot to a different solver-design owner such as destroy/repair, local search,
  acceptance, construction, or a stable-entrypoint algorithm-body change.

## Status Update

CVRP-owned prompt guidance was updated so share70 is no longer the default
target-selection priority. Future scheduler proposals must contrast against the
rejected share70 variants and explain how they preserve the X-n110 seed-43
canonical improvement. Otherwise, target selection should prefer a concrete
non-scheduler solver-design owner.

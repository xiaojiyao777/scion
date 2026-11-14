# CVRP Successor19 Clean-Fork In-Flight Record - 2026-06-29

## Purpose

Record the current successor19 launch state and early evidence while the local
2-round run is still active. This is not a postrun conclusion and must not be
used for promotion/frozen interpretation.

Superseded for interpretation by:
`scion/docs/experiments/v0.4/v04-cvrp-successor19-cleanfork-local-postrun-20260629.md`.

## Task Basis

- Plan:
  `scion/docs/experiments/v0.4/v04-cvrp-successor19-cleanfork-plan-20260629.md`
- Task source: `scion/TASK.md`
- Boundary authority: `scion/design/scion-architecture-v3.md`

Successor19 is intended to test a materially different CVRP-owned causal path
after successor18b remained solver-negative.

## Runner State

WSL high-resource runner:

- Prepared root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-successor19-cleanfork-2r-gpt55-20260629T132904Z-claw`
- `run_status.json`: `status=prepared`, `prepared_only=true`,
  `git_commit=8bde8c82`, `scion_model=gpt-5.5`.
- Not launched from WSL. Completion preflight attempts observed from the main
  session failed first with an HTTP 502/TLS backend error and then with HTTP
  401 `auth_token_invalidated` / `All accounts exhausted (1 expired)`.
- The WSL root has prepared files only; it has no authoritative campaign
  evidence.

Server-local small run:

- Root:
  `/home/clawd/research/scion-experiments/v04-cvrp-successor19-cleanfork-local-2r-gpt55-20260629T133200Z-claw`
- Local completion preflight:
  `launch_ready=true`, `static_ready=true`, chat completion HTTP 200,
  `classification=healthy`, model `gpt-5.5`.
- Running command uses `--rounds 2`, `--time-limit-sec 30`,
  `--measurement-governance on`, `--completion-preflight`, and
  `--disable-early-stop`.
- As of `campaign/status.json` updated at `2026-06-29T14:15:35Z`, the wrapper
  is still running. The first screening completed and the branch entered an
  expanded screening pass.

## Proposal Flow Observed

First proposed mechanism:

- Hypothesis id: `f9727ce5-30b6-4b3f-b8ac-8e99a7ced0f2`
- Target: `policies/baseline_modules/destroy_repair.py`
- Mechanism ids: `radial_load_slice_removal`,
  `destroy_repair_selection`
- Status: rejected before protocol.
- Quality block:
  `agent_quality_blocked:cvrp_solver_design_static_quality`.
- Reason: the static smoke rejected non-causal destroy telemetry because
  `radial_load_slice_removal` recorded effect telemetry inside
  `destroy_repair.py`. Destroy helpers may record activation or budget while
  removing customers, but effect telemetry must be recorded after repair and
  acceptance on a feasible candidate or directly attributable accepted
  improvement.

Second proposed mechanism:

- Hypothesis id: `ec55f92f-3aef-4870-b7cb-22f27d6625f5`
- Target: `policies/baseline_modules/local_search.py`
- Mechanism id: `bounded_route_segment_exchange`
- Status: active while the run continues.
- Mechanism summary: add a bounded VNS local-search neighborhood that swaps
  short contiguous length-2/3 blocks between distinct routes when capacity is
  preserved and combined route distance strictly decreases.
- Static/code session status: completed with contract preview passed.

## First Screening Evidence

First screening metrics artifact:

- `campaign/metrics/aa5f9356-aea5-49e2-9592-14130395517e.json`
- `stage=screening`
- `total_pairs=32`
- `valid_pairs=32`
- `failed_pairs=0`
- `candidate_failed_pairs=0`
- `champion_failed_pairs=0`
- `screening_pair_wins=15`
- `screening_pair_losses=8`
- `screening_pair_ties=9`
- `screening_median_delta=2.0`
- `screening_evidence_status=complete`
- `runtime_evidence_status=sufficient`
- `runtime_confidence=high`
- `bounded_route_segment_exchange` phase telemetry is active and nonzero.

Representative valid pairs from the first screening snapshot:

| Case | Seed | Result | Candidate total_distance | Champion total_distance | Delta | Candidate fleet_violation | Champion fleet_violation |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |
| `cvrplib/A/A-n64-k9.vrp` | 11 | win | 1440.0 | 1453.0 | 13.0 | 0.0 | 0.0 |
| `cvrplib/A/A-n64-k9.vrp` | 29 | win | 1435.0 | 1458.0 | 23.0 | 0.0 | 0.0 |
| `cvrplib/A/A-n64-k9.vrp` | 43 | win | 1425.0 | 1442.0 | 17.0 | 0.0 | 0.0 |
| `cvrplib/A/A-n64-k9.vrp` | 59 | win | 1462.0 | 1464.0 | 2.0 | 0.0 | 0.0 |
| `cvrplib/B/B-n63-k10.vrp` | 11 | loss | 1559.0 | 1509.0 | -50.0 | 0.0 | 0.0 |
| `cvrplib/B/B-n63-k10.vrp` | 29 | win | 1558.0 | 1559.0 | 1.0 | 0.0 | 0.0 |
| `cvrplib/B/B-n63-k10.vrp` | 43 | win | 1542.0 | 1549.0 | 7.0 | 0.0 | 0.0 |
| `cvrplib/B/B-n63-k10.vrp` | 59 | loss | 1556.0 | 1543.0 | -13.0 | 0.0 | 0.0 |
| `cvrplib/E/E-n101-k14.vrp` | 11 | win | 1101.0 | 1124.0 | 23.0 | 0.0 | 0.0 |
| `cvrplib/E/E-n101-k14.vrp` | 29 | tie | 1130.0 | 1130.0 | 0.0 | 0.0 | 0.0 |
| `cvrplib/E/E-n101-k14.vrp` | 43 | tie | 1114.0 | 1114.0 | 0.0 | 0.0 | 0.0 |

Delta is positive in the screening artifact when the candidate improves the
declared objective under `declared_objectives_lexicographic` semantics.

Decision after first screening:

- `decision=expand_screening`
- `decision_reason=["SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT"]`
- Scheduler result: `continue_same_branch`.

## Expanded Screening In Flight

Expanded screening metrics artifact:

- `campaign/metrics/6713e5d8-57d8-4ca6-b317-a273024eba4c.json`
- `stage=screening`
- `expand=true`
- `expand_round=1`
- Current snapshot: `valid_pairs=8`, `total_pairs=48`,
  `failed_pairs=0`.

## Interpretation Boundary

This is useful but incomplete evidence:

- The second mechanism is a clean-fork local-search path, not a repeat of the
  rejected destroy telemetry candidate.
- The first screening signal is mixed but mechanism-active: 15 wins, 8 losses,
  9 ties, and median delta 2.0 over 32 valid pairs. All observed pairs preserve
  feasibility.
- The framework correctly expanded screening instead of promoting or rejecting
  immediately under low-SNR trajectory-divergent evidence.
- There is not yet postrun readiness, formal MDE comparison, CMT2/CMT4
  evidence, validation/frozen evidence, or promotion-grade conclusion.
- Do not promote, freeze, or close v0.4 based on this in-flight record.

## Next Check

When the local run exits, generate/read postrun artifacts and update this
record or write a final postrun report with:

- final `campaign/status.json` counters;
- `campaign_summary.json`;
- postrun brief/readiness artifacts;
- formal mechanism activation/effect evidence;
- pair/case totals for all screening rows, including CMT2 and CMT4;
- MDE/effect interpretation;
- final decision: solver-positive-at-MDE, weak-positive-below-MDE, no-effect,
  quality regression, inactive, or infra invalid.

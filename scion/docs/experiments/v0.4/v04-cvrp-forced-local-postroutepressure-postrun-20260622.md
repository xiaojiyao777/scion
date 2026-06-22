# CVRP Forced Local-Search Post Route-Pressure Postrun

Date: 2026-06-22

This report records the forced local-search CVRP root launched after two
current-run acceptance-family failures and the default-avoid guard probes. The
run is current-run-ready and framework-valid. It did not improve the solver, but
it did recover non-acceptance CVRP research: the agent generated, coded,
screened, refined, and then rejected local-search mechanisms with direct
mechanism telemetry.

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-forced-local-eb2627e5-postroutepressure-4r-gpt55-20260622T081704Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-forced-local-eb2627e5-postroutepressure-4r-gpt55-20260622T081704Z-claw`
- WSL commit: `eb2627e5`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw/campaign`
- Forced target:
  `--force-surface solver_design --force-action modify --force-target-file policies/baseline_modules/local_search.py`
- Final wrapper status: `wrapper_exit_status=0`,
  `campaign_wrapper_exit_status=0`, `postrun_readiness_exit_status=0`,
  `postrun_acceptance_status=ready`.
- Final campaign status: `valid`, `complete`, stopped naturally on
  `max_rounds_exhausted`.
- Campaign counters: 4 effective rounds, 4 protocol-evaluated screening rows,
  4 formal screened candidates, 0 quality blocks, 0 proposal quality blocks, 0
  validation rows, 0 fresh-runtime replay rows, 0 promotions, champion still
  `v1`.

Interpretation caveat: this root resumes the route-pressure campaign. The
agentic session index therefore contains older construction and acceptance
sessions from the resume source. They are not current forced-target failures;
the current forced-local path starts at the `local_search.py` sessions.

The top-level `exit.txt` includes the earlier operator SIGTERM from a discarded
restart attempt, but the restarted run finished cleanly. Current status should
be read from `run_status.json`, `campaign/status.json`, and postrun readiness.

## Acceptance Checks

`postrun_acceptance/readiness/cvrp_on_full.postrun_acceptance_readiness.v1.json`
accepted the run for analysis:

- `current_run_analysis_ready=true`
- `delegation_ready=true`
- `failed_required_checks=[]`
- all postrun report families are present
- current-run prompt/source visibility, branch state, champion progress,
  failure taxonomy, and Phase 4 evidence coverage checks are ready

The postrun analysis brief reports complete current-run Phase 4 coverage,
including prompt manifests, code traces, target-intent and hypothesis traces,
branch lessons, protocol accounting, runtime feedback, same-mechanism follow-up,
and CVRP-specific handoff evidence for default-avoid directions, MDE, bounded
large-instance two-opt constraints, resume continuity, and CMT2/CMT4 protection.

## Mechanisms Tested

The forced target succeeded: current candidates modified
`policies/baseline_modules/local_search.py`, not acceptance or scheduler
modules.

| Round | Mechanism | Decision | Pairs | Pair W/L/T | Case W/L/T | Median delta | CI | Net raw delta |
| ---: | --- | --- | ---: | --- | --- | ---: | --- | ---: |
| 1 | `bounded_interroute_2opt_bridge` | `expand_screening` | 32 | 10/8/14 | 3/2/3 | `0.0` | `[-3.5, 3.25]` | `-59` |
| 2 | `bounded_interroute_2opt_bridge` | `continue_explore` | 48 | 13/13/22 | 3/3/6 | `0.0` | `[-1.75, 0.5]` | `-82` |
| 3 | refined `bounded_interroute_2opt_bridge` | `continue_explore` | 32 | 9/17/6 | 0/5/3 | `-4.25` | `[-6.0, 1.5]` | `-87` |
| 4 | `cmt_slack_aware_segment_swap` | `abandon` | 32 | 4/13/15 | 0/3/5 | `-1.75` | `[-7.0, 0.0]` | `-132` |

The effect-vs-MDE postrun report is unambiguous:

- `mde_at_power_80=9.9`
- 4/4 rows below MDE
- 4/4 rows with CI high below MDE
- 0 positive rows at or above MDE
- 4/4 nonpositive median-delta rows

## Case Pattern

The initial bridge had localized wins but did not generalize:

- Round 1: wins on `A-n64`, `P-n65`, and `CMT2`; losses on `B-n63` and
  `X-n110`; `E-n101` mixed; `CMT4` and `M-n200` tied.
- Round 2 expansion kept `A-n64`, `P-n65`, and `CMT2` positive, but losses on
  `B-n63`, `B-n67`, and `X-n110` balanced the signal.
- Round 3 refinement regressed: no case-level wins, losses on `A-n64`,
  `B-n63`, `E-n101`, `CMT2`, and `X-n110`.
- Round 4 CMT slack segment swap also failed: no case-level wins, losses on
  `A-n64`, `B-n63`, and `P-n65`; `CMT2` mixed and `CMT4` tied.

Protected-case interpretation: the first bridge looked safe-positive on CMT2
and neutral on CMT4, but the refinement lost CMT2 and mixed CMT4. The separate
CMT slack segment swap did not produce a protected-case win. Do not accept the
current bridge/refinement or CMT slack swap as protected-case-safe mechanisms.

## Mechanism Telemetry

The negative solver result is not a telemetry failure. Both local-search
mechanisms activated and produced direct phase evidence:

- `bounded_interroute_2opt_bridge` round 1: 296 accepted phase moves, best-delta
  sum `1037`, 296 improvements, observed on all 32 candidate pairs.
- `bounded_interroute_2opt_bridge` round 2: 379 accepted phase moves, best-delta
  sum `1243`, 379 improvements, observed on all 48 candidate pairs.
- refined `bounded_interroute_2opt_bridge` round 3: 328 accepted phase moves,
  best-delta sum `1012`, 328 improvements, observed on all 32 candidate pairs.
- `cmt_slack_aware_segment_swap` round 4: 565 accepted phase moves,
  best-delta sum `467`, 565 improvements, observed on all 32 candidate pairs.

Postrun phase-causal summaries classify this as local phase activation/effect
that did not translate into reliable final-objective improvement. That is
useful research evidence: the candidate mechanisms are active but poor as
integrated solver changes.

## Interpretation

This run satisfies the immediate v0.4 direction-control check:

- the launcher forced-target pass-through reached the generated `run.sh`
  execution block;
- the agent stopped spending Protocol rows on unchanged acceptance-family
  proposals;
- the proposal/code path produced local-search solver code under the requested
  target file;
- schema, target/action, static contract, canary, and formal screening all
  completed without quality blocks;
- postrun acceptance is ready and current-run evidence is present.

The solver conclusion is negative:

- champion stayed at `v1`;
- no row reached validation or promotion;
- all rows were below MDE and had CI high below MDE;
- the refined bridge worsened the original bridge;
- the CMT slack segment-swap alternative was abandoned.

Operational conclusion: v0.4 CVRP effective research has recovered enough to
generate and reject non-acceptance local-search mechanisms, but it still lacks
continuous CVRP improvement. The next CVRP root should not repeat unchanged
`bounded_interroute_2opt_bridge`, its high-asymmetric-promise refinement, or
`cmt_slack_aware_segment_swap`. Use the case pattern above to choose either a
materially different bounded local-search operator or a different direct
solver-design causal path with activation-to-objective telemetry and explicit
CMT2/CMT4 protection.

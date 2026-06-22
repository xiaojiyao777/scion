# CVRP Route-Pressure Post-Rank-Gap Postrun

Date: 2026-06-22

This report records the CVRP follow-up launched after the current-run-ready
rank-gap acceptance evidence. The purpose was to see whether Scion would pivot
to bounded large-instance local search or another materially different
solver-design causal path. The run was framework-valid and postrun-ready, but
the live agent spent all four effective rows on the `route_pressure_acceptance`
family and produced no solver improvement.

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-nextmech-1aae436c-postrankgap-4r-gpt55-20260622T041502Z-claw`
- WSL commit: `1aae436c`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-2e1bc5ae-postrepair-4r-gpt55-20260622T021910Z-claw/campaign`
- Model: `gpt-5.5` through the local proxy.
- Final wrapper status: `wrapper_exit_status=0`,
  `campaign_wrapper_exit_status=0`, `postrun_readiness_exit_status=0`,
  `postrun_acceptance_status=ready`.
- Final run status: `valid`, `complete`, stopped naturally on
  `max_rounds_exhausted`.
- Campaign counters: 4 effective rounds, 4 consumed proposal attempts, 4
  protocol-evaluated screening rows, 4 formal screened candidates, 0 proposal
  quality blocks, 0 promotions, champion still `v1`.

## Mechanism Actually Tested

The prepared handoff named bounded large-instance two-opt as the highest current
follow-up and required CMT2/CMT4 protection for protected-case-sensitive
mechanisms. The live run instead selected a new acceptance-family branch:

- Branch: `bba3d45f-a7d7-4485-905b-cb3777976c1e`
- Hypothesis `030a3239-8581-49b1-9d45-37ec732d516b`: broad
  route-pressure penalty in simulated annealing acceptance.
- Hypothesis `d1009477-3977-4d36-9a06-b37c1237a315`: thresholded
  lexicographic route-pressure refinement.
- Target files in the formal diffs: `policies/baseline_modules/acceptance.py`
  and `policies/baseline_modules/scheduler.py`.

Both candidates instrumented `route_pressure_acceptance` and only changed the
non-improving simulated-annealing accept path. They did not implement bounded
large-instance local search, construction repair, VNS, or another direct
objective-improvement operator.

## Metrics

All four protocol rows were complete screening rows with 0 failed pairs.

| Hypothesis | Pairs | Pair wins/ties/losses | Net raw delta | Protected-case delta | Decision |
| --- | ---: | --- | ---: | --- | --- |
| `030a3239` | 32 | 1 / 31 / 0 | `+13` | CMT2 `0`, CMT4 `0` | expand screening |
| `030a3239` | 48 | 1 / 47 / 0 | `+8` | CMT3 `0`, CMT4 `0` | continue explore |
| `d1009477` | 32 | 3 / 29 / 0 | `+24` | CMT2 `0`, CMT4 `0` | expand screening |
| `d1009477` | 48 | 2 / 45 / 1 | `+5` | CMT3 `0`, CMT4 `0` | continue explore |

The nonzero case-level effects were sparse:

- First route-pressure candidate: `B-n63-k10 +13`, then `B-n67-k10 +8`.
- Refined route-pressure candidate: `A-n64-k9 +11`, `B-n63-k10 +13`, then
  `A-n64-k9 +11` and `P-n76-k4 -6`.

Postrun research-efficiency interpretation is stricter than the raw net deltas:

- `mde_at_power_80=9.9`
- 4 protocol rows below MDE.
- 4 rows with CI high below MDE.
- 0 positive rows at or above MDE.
- Mechanism family summary: `route_pressure_acceptance` only.
- Mechanism evidence: activation observed, objective-effect attribution
  missing, objective effect interpreted as zero.

## Acceptance Checks

`postrun_acceptance/readiness/cvrp_on_full.postrun_acceptance_readiness.v1.json`
accepted the run for analysis:

- `current_run_analysis_ready=true`
- `delegation_ready=true`
- `failed_required_checks=[]`
- `prompt_source_visibility_actionability=ok`: 31 traces, code protected
  source visible 5/5, hypothesis target source visible 5/5.
- `failure_taxonomy_actionability=ok`: 0 proposal quality blocks, no stale
  source/code-generation/tool-timeout failures.
- `champion_progress_actionability=ok`: no promotion signal observed, champion
  version remains `1`.
- `review_input_summaries_actionability=ok`: interpretation
  `protocol_evaluated_without_large_twoopt_signal`.

The remaining actionability gap is research-direction quality, not framework
validity. `research_context_actionability` still reports
`same_mechanism_opportunities_not_selected`, and the analysis brief reports
`missing_large_twoopt_mechanism_signal`.

## Interpretation

This is useful v0.4 evidence, but not a solver improvement.

- Positive: the repaired framework can launch a resumed CVRP campaign, produce
  current-run provider traces, preserve source visibility, evaluate four
  candidates without quality blocks, expand low-SNR screens, and generate
  postrun-ready actionability summaries.
- Negative: the agent did not follow the highest-opportunity bounded two-opt
  handoff; it selected another acceptance-family path after rank-gap acceptance
  had already failed to produce accepted objective evidence.
- Negative: all route-pressure effects are below MDE, protected CMT cases are
  neutral, and no promotion or champion improvement occurred.

Operational conclusion: after two current-run-ready acceptance-family failures
(`rank_gap_annealing_acceptance` and `route_pressure_acceptance`), the next CVRP
root should not spend branch slots on acceptance/adaptive-weighting unless the
hypothesis names a new non-acceptance causal path and direct objective-effect
telemetry. The launcher handoff has been updated accordingly so the next WSL
root steers toward bounded local search or another direct solver-design
mechanism.


# CVRP successor52 bounded multi-candidate ALNS race postrun - 2026-07-09

## Scope

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor52-post-successor51-cleanfork-server-claw-2r-gpt55-20260709T020546Z-claw`

Successor52 was launched from committed guidance repair `1869299c` after
successor51 closed `bounded_route_arc_lns_rebuild` as active-marginal,
below-MDE, and protected-case unsafe. The run used the server-local `claw`
environment, local `gpt-5.5`, `--rounds 2`, `--completion-preflight`, full
proposal context, `--force-surface solver_design`, and no forced target
mechanism or file.

## Run Status

- Wrapper status: finished, exit status `0`.
- Campaign status: complete; requested rounds `2`, effective rounds `2`.
- Postrun acceptance: ready.
- Stop reason: `max_rounds_exhausted`.
- Run validity: valid.
- Model calls: six successful `gpt-5.5` calls through `openai_compatible`.
- Request kinds: two `hypothesis_target_intent`, two `hypothesis`, one
  `tool_selection`, one `code`.
- Token accounting was present for all six traces: total `571075`, input
  `562601`, output `8474`, reasoning `1919`.
- Proposal attempts: three total, with one pre-code proposal-quality block.
- Candidate intents: two algorithm-quality candidates and one repair/infra
  candidate.
- Champion promotions: `0`.

The run is valid experiment evidence. It is not a model outage, completion
preflight failure, postrun-acceptance failure, or prompt-context failure.

## LLM Call Audit

1. The first target-intent call selected `bounded_multi_candidate_alns_race`
   in `policies/baseline_modules/scheduler.py`, classified as
   `destroy_repair_selection`. It proposed replacing a single ALNS
   destroy/repair sample with a tightly bounded race of feasible candidate
   states.
2. The first formal hypothesis kept the same mechanism but was blocked before
   code generation by `cvrp_solver_design_causal_path_contract`. The missing
   fields were `branch_lesson_usage.clean_fork_diversity_claim` and
   `algorithmic_intervention_sufficiency`. The block was pre-protocol and did
   not count toward max rounds.
3. The retry target-intent again selected `bounded_multi_candidate_alns_race`,
   now explicitly requiring isolated copied states/RNG streams, CMT2/CMT4
   protection, and separate local race versus final trajectory attribution.
4. The second formal hypothesis passed the contract with structured
   `material_difference`, CMT2/CMT4 protected-case entries, and a claimed
   algorithmic intervention: clone current state, generate `K` bounded
   destroy/repair candidates, select the best feasible route-count-safe
   candidate, then pass one winner into the existing acceptance path.
5. Tool selection returned `stop`; no external tool was requested.
6. The code call modified only `policies/baseline_modules/scheduler.py`. It
   imported `random`, wrapped the ALNS candidate-generation block in a
   race of up to two or three candidate states, recorded
   `bounded_multi_candidate_alns_race` iteration/phase/move telemetry, and
   then reused the existing acceptance and best-update path.

Prompt manifests and source visibility did not show harmful section truncation.
The agent saw the repaired research guidance, reviewed mechanism ids, default
avoid directions, scheduler source, and active CVRP constraints. This run does
not support a context-starvation explanation for the candidate quality issue.

## Candidate Audit

The candidate was a real solver mechanism, not a metadata gate or telemetry
wrapper:

- target file: `policies/baseline_modules/scheduler.py`;
- mechanism: race a small number of complete ALNS candidate states from the
  same current solution before the normal acceptance decision;
- activation: bounded by remaining-time reserve and small `race_limit`;
- protection: require feasibility and `max_routes` before a race winner can
  become the candidate;
- telemetry: records phase runtime, iteration count, move attempts, accepted
  race wins, and local race delta.

The implementation is still conservative and trajectory-coupled:

- race candidates can each run embedded VNS, which substantially increases
  runtime and changes the downstream search trajectory;
- non-baseline candidates draw seeds from the master RNG with `rng.randrange`,
  perturbing later ALNS choices even when they do not win;
- `baseline_record = race_records[0]` is not guaranteed to be the canonical
  race index `0` if earlier candidates fail or are filtered;
- race `accepted` telemetry means local winner-over-baseline, not final ALNS
  acceptance or final best-solution improvement;
- operator weights are credited to the selected winner's destroy/repair pair,
  which can amplify short-horizon winners.

## Measurement Result

Measurement readiness was `ready`, with MDE at power 80 equal to `9.9`; the
readiness artifact remains report-only and excluded from `DecisionFeatures`.

Protocol rows:

| Round | Pairs | Pair W/L/T | Median | CI | Decision |
|---|---:|---:|---:|---|---|
| 2 | 32 | 18/10/4 | 5.0 | [-6.5, 23.0] | expand_screening |
| 3 | 48 | 31/16/1 | 3.75 | [-1.25, 15.0] | continue_explore |

Postrun effect-vs-MDE summary:

- max median delta: `5.0`;
- max effect-to-MDE ratio: `0.505051`;
- rows at or above MDE: `0`;
- rows below MDE: `2`;
- interpretation: `protocol_effects_below_mde_or_inconclusive`;
- champion promotions: `0`.

The case-level result has useful positive pockets, but not promotion-grade
aggregate evidence.

## Case Pattern

Row 1 priority cases:

- `CMT2`: W/L/T `1/3/0`, deltas `[-30, 11, -9, -4]`, median `-6.5`.
- `CMT4`: W/L/T `1/3/0`, deltas `[11, -54, -15, -36]`, median `-25.5`.

Row 2 priority cases:

- `CMT2`: W/L/T `1/3/0`, deltas `[-30, 11, -9, -13]`, median `-11.0`.
- `CMT4`: W/L/T `1/3/0`, deltas `[11, -54, -15, -36]`, median `-25.5`.

Positive pockets:

- `A-n64-k9`: `4/0/0`, median `+23.0`.
- `A-n80-k10`: `4/0/0`, median `+21.5`.
- `B-n67-k10`: `4/0/0`, median `+5.0`.
- `X-n110-k13`: `3/0/1`, median `+35.0`.

Mixed or loss-prone rows include `B-n63-k10`, `E-n101-k14`,
`P-n101-k4`, and `P-n76-k4`. Fleet violation medians remained `0.0` in
the postrun case summaries, so the protected-case issue is not a feasibility
collapse. It is final total-distance degradation on priority structures.

## Telemetry Interpretation

Mechanism activation was strong:

- row 1 observed `bounded_multi_candidate_alns_race` runtime in `32/32`
  candidate pairs;
- row 2 observed runtime in `48/48` candidate pairs;
- row 1 race weighted runtime was `906148 ms`, with embedded VNS weighted
  runtime `788734 ms`;
- row 2 race weighted runtime was `1241637 ms`, with embedded VNS weighted
  runtime `1085540 ms`;
- postrun mechanism evidence marked the primary mechanism as activation
  observed and effect positive in both rows.

The failure mode is not inactive mechanism suppression. The problem is that a
short-horizon race winner changes the later ALNS/VNS trajectory and does not
protect final candidate-vs-champion total distance on CMT2/CMT4.

## Decision

Treat successor52 as valid, active-positive locally, below-MDE, and
protected-case unsafe.

Do not:

- promote or long-run unchanged `bounded_multi_candidate_alns_race`;
- continue with threshold-only race tuning;
- count local race winner-over-baseline telemetry as final solver effect;
- let CMT2/CMT4 protection be satisfied by generic feasibility or
  route-count guards only.

A follow-up is justified only as a designed protected repair of the mechanism,
not as an automatic extension. A credible follow-up must be CVRP-owned and
must address the mechanism's trajectory coupling:

- isolate or restore non-winning race RNG effects;
- avoid running embedded VNS independently for every race candidate, or apply
  embedded VNS once after winner selection under an explicit budget;
- record canonical baseline candidate identity, winner identity, final ALNS
  acceptance, and final best/current total-distance movement;
- make CMT2/CMT4 protection substantive in mechanism behavior, not only
  postrun reporting.

## Next TASK Implication

Record `bounded_multi_candidate_alns_race` as reviewed/default-avoid for
unchanged same-line continuation. The next CVRP action should either:

1. design a protected, budgeted candidate-trajectory selector follow-up that
   directly repairs the above failure modes; or
2. clean-fork to a materially different CVRP-owned causal path if the follow-up
   would amount only to threshold tuning.

No long-run should start from successor52 as-is.

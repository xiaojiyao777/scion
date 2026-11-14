# v0.4 CVRP 8-Seed A/A Power Check Postrun

*Date: 2026-06-12*
*Branch: `codex/v04-evidence-repair-plan`*
*Calibration commit recorded by wrapper: `809992a`*
*Status: accepted measurement diagnostic; CVRP still low-power*

## Summary

The CVRP 8-case x 8-seed x 3-replicate A/A power check completed with wrapper
exit status `0` and produced a valid `scion.aa_noise_floor.v1` artifact.

The result does not clear CVRP for a governance ON/OFF main experiment or a
long promotion campaign. The 8-seed MDE is `9.6` raw `total_distance`, only
slightly lower than the Phase 1 formal 4-seed MDE of `9.9`, and still `4.8x`
larger than the current CVRP `practical_delta_screen=2.0`. The calibration tool
also recommends `16` seeds. This confirms that current CVRP screening remains a
low-power measurement instrument for the declared practical effect scale.

A/A calibration remains a measurement/proposal-readiness diagnostic, not
promotion evidence. The artifact explicitly records
`policy=problem_owned_measurement_diagnostic` and
`decision_features_excluded=true`; raw pair evidence must remain outside
`DecisionFeatures`.

## Run

Run root:

`/home/clawd/research/scion-experiments/v04-phase4-cvrp-8seed-aa-saferoot-20260612T011824Z-claw`

Output:

`/home/clawd/research/scion-experiments/v04-phase4-cvrp-8seed-aa-saferoot-20260612T011824Z-claw/aa_noise_floor.json`

SHA256:

`aae0e564d08dfd07e39372386add50d1956fa9a61f4be2288aa2815a8d167e5b`

Wrapper:

- Started: `2026-06-12T01:18:24Z`
- Ended: `2026-06-12T04:13:56Z`
- Wrapper exit status: `0`
- Runtime policy: `protocol_time_limits`
- Safe data root: `/home/clawd/research/or-autoresearch-agent/vrp`

The prior attempt at
`/home/clawd/research/scion-experiments/v04-phase4-cvrp-8seed-aa-20260612T011722Z-claw`
failed before solver execution because the temporary protocol copy did not
activate a safe data root for `cvrplib/...` cases. The accepted saferoot rerun
used run-root protocol/seed/split copies and declared the repo `vrp` directory
in the split copy.

## Design Check

Expected design:

- Stage: screening
- Surface: `solver_design`
- Champion: CVRP Phase 4 champion v1 from
  `/home/clawd/research/scion-experiments/v04-phase4-focused-cvrp-measreadiness-20260611-4r-gpt55-20260611T224916Z-claw/campaign/champions/champion_v1`
- Cases: 8
- Seeds: `11,29,43,59,73,79,97,103`
- Replicates: 3
- Seed offset: `1000003`
- Expected pairs: `8 * 8 * 3 = 192`
- No LLM calls

Artifact:

- `schema=scion.aa_noise_floor.v1`
- `problem_id=cvrp`
- `stage=screening`
- `selected_surface=solver_design`
- `replicate_count=3`
- `n_pairs=192`
- `selected_seeds=[11,29,43,59,73,79,97,103]`
- `seed_offset=1000003`
- `pair_evidence` rows: `192`

Selected cases:

- `cvrplib/A/A-n64-k9.vrp`
- `cvrplib/B/B-n63-k10.vrp`
- `cvrplib/E/E-n101-k14.vrp`
- `cvrplib/P/P-n65-k10.vrp`
- `cvrplib/CMT/CMT2.vrp`
- `cvrplib/CMT/CMT4.vrp`
- `cvrplib/M/M-n200-k17.vrp`
- `cvrplib/X/X-n110-k13.vrp`

Pair evidence completeness:

- Per case: `24` rows each.
- Per replicate: `64` rows each.
- Outcome counts: `74` win, `85` loss, `33` tie.
- Required row fields were present: case, replicate, candidate seed, resolved
  case path, safe case resolution, champion and candidate elapsed milliseconds,
  time limit, objective values, deltas, and outcome.
- Candidate/champion elapsed values were positive.
- Case resolution was safe for all rows through the declared safe data root.

Runtime policy:

- Artifact policy: `protocol_time_limits`.
- `168` rows used `30s`.
- `24` rows used `45s` for `M/M-n200-k17.vrp`.
- Runtime policy metadata recorded `resolved_unique_sec=[30,45]` and the
  formal screening rule for `150-250` dimensions at `45s`.

## Power Result

Protocol power:

- `mde_at_power_80=9.6`
- `recommended_min_effect=9.6`
- `false_pass_rate_at_current_gate=0.0`
- `recommended_min_seeds=16`

Per-case absolute delta summaries:

| Case | P50 abs delta | P90 abs delta | Max abs delta | Tie rate |
| --- | ---: | ---: | ---: | ---: |
| `A-n64-k9` | 10.0 | 16.4 | 26.0 | 0.0833 |
| `B-n63-k10` | 14.5 | 44.5 | 54.0 | 0.0833 |
| `CMT2` | 14.0 | 28.7 | 37.0 | 0.0000 |
| `CMT4` | 16.5 | 42.8 | 60.0 | 0.0000 |
| `E-n101-k14` | 9.0 | 19.4 | 23.0 | 0.1250 |
| `M-n200-k17` | 0.0 | 8.0 | 13.0 | 0.7500 |
| `P-n65-k10` | 9.0 | 17.0 | 23.0 | 0.0000 |
| `X-n110-k13` | 12.5 | 76.8 | 90.0 | 0.3333 |

Interpretation:

- The 8-seed check did not materially improve CVRP measurement resolution.
- MDE moved from Phase 1's `9.9` to `9.6`, while the declared practical
  screening delta remains `2.0`.
- The current screening instrument is still unable to reliably detect effects
  at the declared practical scale.
- Any CVRP candidate with expected effect around `0.1%` to `3%`, or with raw
  total-distance movement near `2.0`, remains at high risk of being dominated
  by measurement noise.

## Caveat

`CMT/CMT4.vrp` has `DIMENSION : 151` in the file, but this artifact used `30s`
rows for `CMT4`. The current time-limit resolver appears to infer dimension
from filename patterns such as `n###` or `tai###`; `CMT4` does not match, so it
falls back to the screening default `30s`. If protocol semantics require using
the VRP file's `DIMENSION` field, `CMT4` should have used the `150-250` rule and
`45s`.

This caveat does not reverse the main low-power conclusion: even with the
current mixed 30s/45s run, the measured MDE remains far above
`practical_delta_screen=2.0`. It does mean a future formal power run should fix
or explicitly pre-register CMT dimension handling before claiming protocol-time
fidelity.

## Decision

Accepted as a v0.4 measurement diagnostic.

Do not use current CVRP as the first formal governance ON/OFF target, and do
not launch a long CVRP promotion campaign on the assumption that 8 seeds solved
the measurement problem.

Next options:

- Repair or pre-register CVRP dimension/time-limit resolution for CMT cases,
  then rerun the relevant A/A check if exact protocol-time fidelity is needed.
- Try a larger pre-registered power rung, such as more seeds or a larger case
  set, if the research budget justifies it.
- Revisit the declared CVRP practical effect scale and gates so they match the
  measurable effect size, rather than claiming sensitivity to `2.0` raw
  distance when the instrument's MDE is about `9.6`.
- Treat CVRP v0.4 as a low-power diagnostic and runtime/research-mechanics
  pressure test until the measurement instrument changes.

# CVRP Candidate Large-X Replay Postrun - 2026-06-15

## Purpose

This no-LLM diagnostic replay tested the two Phase C ALNS-only
validation-positive candidates on large-X cases against the completed champion
large-X runtime curve.

The goal was to separate three explanations for the Phase C validation-to-frozen
collapse:

- runner timeout/grace made large-X evidence incomplete;
- more large-X budget would reveal candidate improvement;
- the candidates themselves lacked large-X search leverage.

This is problem-owned postrun diagnostic evidence only. It is not Scion Protocol
evidence and does not alter `DecisionFeatures`.

## Artifacts

- Root:
  `/home/clawd/research/scion-experiments/v04-cvrp-candidate-largeX-replay-20260615T164410Z`
- Status:
  `status=completed`, `completed_at_utc=2026-06-15T19:05:03Z`
- Comparison:
  `/home/clawd/research/scion-experiments/v04-cvrp-candidate-largeX-replay-20260615T164410Z/candidate_vs_champion_largeX.csv`
- Baseline summary:
  `/home/clawd/research/scion-experiments/v04-cvrp-largeX-runtime-curve-20260615T150454Z/summary.csv`

Candidates:

- `rep01_route_limit_regret_4504a238`
- `rep02_adaptive_destroy_lexsa_cc6f489c`

Shape:

- Cases: `X-n401-k29`, `X-n573-k30`, `X-n641-k35`, `X-n1001-k43`
- Seeds: `61`, `89`
- Multipliers: `1`, `4`
- Candidate rows: `16` per candidate
- Direct solver only; no LLM and no APS

## Results

Overall completed-pair result across both candidates:

- Planned candidate/champion pairs: `32`
- Completed candidate and completed champion pairs: `29`
- Objective W/L/T: `2/0/27`
- Mean candidate-minus-champion delta: `-8.6897`
- Median delta: `0.0`
- Route-count comparison: `0` candidate improvements / `0` regressions /
  `29` ties
- Missing/incomplete rows were concentrated on `X-n1001-k43 seed61`: rep01 had
  one candidate-timeout/champion-timeout row and one candidate-timeout/
  champion-completed row; rep02 had one candidate-timeout/champion-timeout row.

The incomplete `X-n1001 seed61` rows confirm that large-X runner grace was a
real evidence-completeness issue, but the completed rows are enough to reject
the stronger explanation that these validation-positive candidates only needed
more wrapper grace to show broad large-X leverage.

### rep01_route_limit_regret_4504a238

Status reconciliation:

- Rows: `16`
- Completed candidate and completed baseline pairs: `14`
- Candidate timeout / baseline timeout: `1`
- Candidate timeout / baseline completed: `1`

Completed-pair objective result:

- W/L/T: `2/0/12`
- Mean candidate-minus-baseline delta: `-18.0`
- Median delta: `0.0`
- Nonzero wins: two rows at `X-n641-k35`, seed `89`, multipliers `1` and `4`,
  each delta `-126`
- Route regressions visible from summaries: `0`

Telemetry:

- Candidate best-update count on completed rows: all `0`
- Candidate total best updates: `0`
- Candidate iterations: min `125`, median `267.5`, max `881`
- Candidate runtime-budget hit split: `7` true / `7` false among completed rows
- Median runtime delta on completed rows: `+27.26s` versus champion
- Runtime split: `8` slower / `6` faster versus champion

Interpretation: the only nonzero improvement was the already-observed
`X-n641 seed89` delta. It repeated at both multipliers but did not come with
best-update trace evidence, so it does not show a broad large-X search leverage
mechanism.

### rep02_adaptive_destroy_lexsa_cc6f489c

Status reconciliation:

- Rows: `16`
- Completed candidate and completed baseline pairs: `15`
- Candidate timeout / baseline timeout: `1`

Completed-pair objective result:

- W/L/T: `0/0/15`
- Mean candidate-minus-baseline delta: `0.0`
- Median delta: `0.0`
- Route regressions visible from summaries: `0`

Telemetry:

- Candidate best-update count on completed rows: all `0`
- Candidate total best updates: `0`
- Candidate iterations: min `1`, median `2`, max `10`
- Candidate runtime-budget hit split: `12` true / `3` false among completed rows
- Median runtime delta on completed rows: `+56.05s` versus champion
- Runtime split: `12` slower / `3` faster versus champion

Interpretation: this candidate produced no objective movement on large-X. The
very low iteration counts and zero updates make it a plateau/tie result, not an
evidence-complete large-X improvement.

## Interpretation

The replay confirms that Phase C runner timeout/grace was a real evidence
completeness problem, especially on `X-n1001 seed61`; however, once replayed
with sufficient wrapper grace, the validation-positive candidates still showed
little to no large-X mechanism leverage.

The strongest statement supported by this artifact is:

- Phase C ALNS-only validation positives were not merely killed by runner grace.
- They mostly collapse to ties on large-X.
- Simple extra time and replay grace do not turn them into broad large-X
  improvements.
- Candidate-specific best-update telemetry gives no evidence of sustained
  large-X search progress.

This does not prove CVRP is hopeless. It says these two Phase C mechanisms are
weak large-X hypotheses. The next CVRP work should use targeted mechanism
diagnostics, such as the separate two-opt size-gated replay, rather than
re-running the same Phase C candidates for more rounds.

Operationally, the next gate before another CVRP LLM campaign is a targeted
no-LLM mechanism replay that shows nonzero best-update density and objective
movement on large-X. The size-gated two-opt replay is the current candidate for
that gate. If it also collapses to ties, the next LLM campaign should start from
a sharper large-X mechanism brief rather than more rounds of the same Phase C
families.

## Boundary Note

All case, BKS-gap, runtime, timeout, iteration, and best-update evidence here is
problem-owned postrun diagnostic material. It may guide human-approved proposal
seeds and experiment design, but it must not enter generic `DecisionFeatures`.

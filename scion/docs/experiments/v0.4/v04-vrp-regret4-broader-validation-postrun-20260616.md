# VRP Regret4 Broader No-LLM Validation Postrun - 2026-06-16

## Boundary

This is a no-LLM/no-APS direct VRP mechanism validation for the external
`Helmholtz` phase K `regret4_repair` candidate. It is not a Scion campaign, not
Scion Protocol evidence, not promotion evidence, and not an accepted solver
change.

The worker read the v3 architecture first and kept the candidate in the
problem-owned VRP validation lane. The main checkout was not modified.

## Artifacts

Artifact root:

`/home/clawd/research/scion-experiments/v04-vrp-regret4-broader-validation-20260616`

Required outputs are present:

- `README.md`
- `validation_results.jsonl`
- `summary.json`
- `summary.md`

The worker created clean `git archive HEAD` baseline and candidate scratch
workspaces, copied CVRPLIB data into each, and applied the phase K
`candidate.patch` only in the candidate copy.

## Matrix

- Cases: `A-n60-k9`, `M-n151-k12`, `X-n120-k6`, `X-n143-k7`,
  `X-n204-k19`, `B-n66-k9`, `E-n76-k10`, `P-n70-k10`
- Seeds: `0..9`
- Budget: `1.0s`
- Workers: `4`
- Rows: `80`

No `2.0s` diagnostic tier was run because the primary result failed acceptance
clearly rather than landing near a borderline decision.

## Results

Aggregate:

- Complete rows: `80/80`
- Overall W/T/L: `21/31/28`
- W-L margin: `-7`
- Mean delta: `-4.4625`
- Median delta: `0.0`
- Failures: `0`
- Feasibility regressions: `0`
- Route-count regressions: `0`
- Repeated regression families: `E`, `M`, `P`

Per-family summary:

| Family | Rows | W/T/L | Mean delta | Median delta | Regressions |
|---|---:|---:|---:|---:|---|
| A | 10 | `3/4/3` | `-1.7` | `0.0` | none repeated |
| B | 10 | `5/0/5` | `0.4` | `0.0` | mixed |
| E | 10 | `2/1/7` | `13.8` | `10.5` | repeated losses |
| M | 10 | `3/3/4` | `-0.5` | `0.0` | repeated losses |
| P | 10 | `2/3/5` | `6.6` | `0.5` | repeated losses |
| X | 30 | `6/20/4` | `-18.1` | `0.0` | no repeated family failure |

Negative delta means candidate better. The candidate improved mean distance in
some slices, especially X-family rows, but the overall W-L margin is negative
and repeated family-specific regressions violate the pre-registered acceptance
rule.

## Decision

Reject as-is for Scion fixed replay. Recommendation:
`reject_or_request_narrower_diagnostic`.

The candidate preserves feasibility and route-count constraints, but it should
not proceed to Scion fixed replay or become a default solver change because:

- overall W-L margin is negative (`21` wins vs `28` losses);
- repeated regressions occur in `E`, `M`, and `P`;
- median delta is neutral rather than positive;
- the positive X signal is not broad enough to justify a general solver-design
  candidate.

If revisited, it should be as a narrower problem-owned diagnostic for the X
slice or as a new mechanism-family hypothesis, not as the original broad
`regret4_repair` patch.

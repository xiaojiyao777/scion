# v0.5 Governance Ablation Preregistration

*Date: 2026-06-29*
*Status: Preregistered design only; do not launch during v0.4*
*Basis: `scion/design/v0.5-evidence-uplift-roadmap.md` W2*
*Boundary authority: `scion/design/scion-architecture-v3.md`*

## Question

Does Scion's full research governance create measurable value over a naive
generate-and-filter loop when the problem has enough signal to support real
promotion decisions?

This preregistration exists to prevent post-hoc arm changes, threshold changes,
or selective interpretation after seeing results.

## Non-Goals

- Do not run this matrix as a v0.4 closeout substitute.
- Do not use low-SNR CVRP as the primary governance-value target.
- Do not add new governance components to make an arm look better.
- Do not let LLM prose, raw problem diagnostics, BKS/case facts, prompt text,
  or branch-lesson prose enter `DecisionFeatures`.

## Start Conditions

The matrix may start only after:

- v0.4 closeout has a final CVRP/warehouse interpretation;
- warehouse remains a calibrated positive-control target;
- a second signal-bearing target is available, either the v0.5 third problem
  or an approved warehouse hard variant;
- local/WSL completion preflight is green for the selected model;
- all arm configurations, budgets, seeds, and blind refit rules are frozen in
  this document or a dated amendment before launch.

## Arms

| Arm | Name | Behavior |
| --- | --- | --- |
| A | `full-governance` | Current Scion governance: branch lifecycle, split exposure, measurement governance, Contract, Verification, Protocol, Safe Feature extraction, deterministic Decision. |
| B | `naive` | Proposal -> Verification to prevent crashes -> single screening point estimate keep/discard. No branch governance, no staged split exposure, no lineage-based context governance. |
| C | `stats-degraded` | Governance remains on, but statistical protocol is deliberately degraded to single-seed screening point estimates before any full-protocol refit. |

Implementation should use a `--governance-profile` style configuration if
needed, but the implementation must reuse existing components rather than
creating a second research system.

## Targets

Primary required target:

- Warehouse, using the current calibrated positive-control configuration.

Second required target before final v0.5 interpretation:

- The v0.5 third problem, if integrated; otherwise a preregistered warehouse
  hard variant that remains signal-bearing and differs materially from the
  existing positive-control setup.

CVRP role:

- CVRP may be included as a measurement stress-control only. It must not be
  used to decide K1/S1 because its current effect sizes may be below protocol
  MDE.

## Repeats And Budget Alignment

Per target and arm:

- At least 3 independent campaigns.
- Same starting champion and problem/protocol version.
- Same model.
- Same maximum LLM token budget.
- Same maximum protocol-evaluation budget.
- Same wall-clock budget class when running on comparable hardware.

Fairness rule:

- Do not compare arms by rounds alone. The naive arm is cheaper per round, so
  the primary cost comparison uses fixed token and protocol-evaluation budgets.

## Blind Refit Rule

Every candidate that Arm B or Arm C would keep/promote must be replayed through
Arm A's full frozen protocol after the arm run finishes.

The refit operator must not know which arm produced the candidate. The refit
result is the only source for:

- true promotion count;
- false-positive count;
- frozen retained effect size;
- final promotion-grade interpretation.

## Primary Metrics

Per target and arm:

- True promotions: kept/promoted candidates that pass blind full-protocol refit.
- False-positive rate: kept/promoted candidates that fail blind full-protocol
  refit divided by all kept/promoted candidates.
- Unit cost per true promotion: tokens, wall-clock time, and protocol
  evaluations divided by true promotions.
- Best final champion quality versus the shared starting champion.
- Mechanism diversity trajectory: distinct mechanism families over time and
  whether search collapses to repeated families.

## Secondary Diagnostics

Record but do not use as the primary K1/S1 decision:

- proposal quality-block rates;
- verification failure rates;
- protocol failure taxonomies;
- candidate crash/invalid-output counts;
- context size and prompt-token distribution;
- branch parking/rejection/clean-fork counts;
- measurement readiness warnings.

## Decision Criteria

K1 is triggered if, on signal-bearing targets, Arm B or Arm C has no worse true
promotion rate per unit cost than Arm A and does not produce an unacceptable
false-positive rate under blind full-protocol refit.

S1 is supported if Arm A has either:

- materially lower false-positive rate at comparable true-promotion output; or
- materially better true-promotion output per unit cost at comparable
  false-positive rate.

If neither condition is clear after the preregistered sample, the report must
state "data insufficient" and give a fixed top-up plan before any additional
runs are launched.

## Analysis Report

The final report should be written to:

```text
scion/reports/governance-ablation-YYYYMMDD.md
```

It must include:

- the frozen arm configuration;
- all run roots;
- all blind refit roots;
- exact model and environment;
- budget usage;
- primary and secondary metrics;
- K1/S1 interpretation;
- deviations from this preregistration.

## Governance Freeze

During the matrix, governance changes are allowed only when they are:

- bug fixes required to make a preregistered arm runnable;
- subtractive simplifications that do not change the arm definition;
- explicit amendments dated before affected runs begin.

Every governance change must answer which preregistered evidence field it
protects. Otherwise it waits until after the matrix.

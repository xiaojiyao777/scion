# Framework Findings

This document evaluates the 2026-05-05 dual Sonnet run against the v3 blueprint
and the v0.4 design goals.

## v3 Blueprint Alignment

The v3 loop remains the correct interpretation frame:

```text
hypothesis -> branch -> code -> contract -> verification -> protocol
-> structured decision -> promotion/abandon -> evidence -> context feedback
```

The run shows that this loop is mostly operating:

- LLM output was treated as tainted proposal/code input.
- Contract and verification gates rejected unsafe or inconsistent candidates.
- Decision outcomes were driven by structured metrics and reason codes.
- Frozen promotion remained scarce and governed.
- Warehouse promotions created immutable champion snapshots.
- Runtime evidence entered protocol metrics and proposal feedback.

The main deviations are not in the core accept/reject discipline. They are in
research-surface richness, novelty semantics, and closeout evidence.

## v0.4 Goal 1: Runtime and Efficiency as Default Governance

Status: mostly met, with reporting gaps.

Evidence:

- Pair-level runtime fields are present in raw metrics and summaries.
- CVRP candidate timeout failed closed.
- Warehouse produced no runtime-failed pairs.
- Static contract blocked unbounded loops.
- Runtime regression rates were visible in screening outputs.

Remaining issues:

- CVRP round 42 is clearer in DB lineage than in `campaign_summary.json`; the
  summary still presents the row primarily as `SCREENING_FAIL_WIN_RATE`.
- Final quality/runtime evidence refs are missing in both campaigns.
- Unreferenced `v8_run*` metric files create artifact noise for future evidence
  manifests.

Design implication:

Runtime governance is now part of the default Scion loop, but evidence closeout
and summary reason-code normalization still need a hardening pass.

## v0.4 Goal 2: CVRP as a Second Problem Class

Status: adapter/protocol execution works; optimization surface is still too
narrow.

Evidence:

- CVRP completed 50 rounds and 40 evaluated protocol experiments.
- All four declared research surfaces appeared in summary coverage:
  `route_local`, `route_pair`, `ruin_recreate`, and `search_policy`.
- `search_policy` was loaded and its runtime fields appeared in metrics.
- CVRP-specific objective policy used `fleet_violation -> total_distance`.
- The run did not depend on warehouse fallback semantics.

The 0-promotion result is explainable:

- Generated operators run after a strong ALNS+VNS baseline.
- Most local/pair/ruin operators had no accepted improvements.
- The one evaluated `search_policy` change made runtime worse and did not
  improve enough to clear screening.
- Four policy attempts were blocked before evaluation by coarse novelty.

Design implication:

The research-surface model is the right direction. The next CVRP step should
move from "operator design space" toward "heuristic algorithm design space"
without discarding operator optimization. Operators are one surface; they are
not the whole algorithm for CVRP.

## v0.4 Goal 3: Campaign Elegance and Maintainability

Status: improved enough to run the experiment; still not fully closed.

Evidence:

- Campaign execution now has extracted services for proposal, evaluation,
  promotion, evidence, branch stepping, workspace lifecycle, and decision
  coordination.
- Proposal/schema failures are represented as step rows.
- Frozen budget is persisted.
- Initial champion state is persisted.

Remaining issues:

- CVRP final state retained one active branch after max-round stop.
- Warehouse `promotion_experiment_id` is not written to champion rows.
- Proposal/code-generation timeout observability is split across summary,
  traces, DB rows, and run logs.
- Formal readiness is reported but not satisfied because final evidence refs
  are not produced.

Design implication:

The remaining campaign work is less about splitting more files and more about
making lifecycle state and evidence closeout first-class. A "thin campaign"
should be able to answer, from durable state alone:

```text
what happened, why it happened, where the evidence is, and whether the run is
formally closeable
```

## CVRP vs Warehouse: Why Outcomes Differed

Warehouse delivery v0.3 exposes an operator pool that is close to the heuristic
algorithm itself. A new operator can directly affect assignment and packing
decisions. That is why branch-level operator hypotheses can compound.

CVRP currently exposes generated operators mostly as post-baseline polishers.
The real search system is larger:

- construction;
- destroy/repair selection;
- local neighborhoods;
- acceptance policy;
- restart/perturbation;
- adaptive scheduling;
- budget allocation.

This explains why warehouse produced 3 promotions while CVRP produced none.
It does not mean Scion only works for warehouse. It means the problem package
must expose the right algorithm-design surfaces for the problem class.

## Context Quality

The previous 2026-05-04 run suffered from context compression that hid failure
causes. This run is better:

- no warehouse hardcoding was observed in CVRP prompts by the artifact audit;
- runtime and no-op feedback were present;
- CVRP route-native surfaces were visible.

But the search still repeated low-impact families. The remaining context issue
is not contamination; it is actionability. CVRP feedback should make the next
move clearer:

- "post-baseline operator accepted no moves" should point toward policy,
  earlier search-stage, or portfolio surfaces;
- "singleton policy duplicate" should not block semantic variants;
- "tie-dominated but valid execution" should be distinct from API/schema
  failure.

## Formal Evidence Status

Both campaigns are valid framework runs but not final formal evidence packages.

Missing:

- `final_quality.json`;
- `final_quality.csv`;
- `per_case_quality.csv`;
- `runtime_summary.json`;
- `failure_summary.json`;
- `evidence_manifest.json`;
- populated `final_evidence_refs` in `campaign_summary.json`.

The v0.4 design requires separating promotion evidence from final quality
evidence. This run has promotion/process evidence, especially for warehouse,
but not final closeout evidence.

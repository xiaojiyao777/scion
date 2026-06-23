# Warehouse v2 Positive-Control Plateau Postrun

Date: 2026-06-23

## Purpose

This run is the clean champion-`v2` warehouse positive-control rerun after the
v0.4 framework, launcher, prompt/context, and runtime-semantics repairs. Its
purpose is not to tune warehouse-specific behavior. Its purpose is to check
whether Scion can support effective research after a known warehouse promotion
checkpoint: continue or reject hypotheses with current-run evidence, use
branch-local lessons, and distinguish a real post-`v2` plateau candidate from
quality-blocked or incomplete-handoff evidence.

## Artifacts

- WSL run root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-wh-v2-positive-2f8e9f21-current-8r-gpt55-20260623T161630Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-wh-v2-positive-2f8e9f21-current-8r-gpt55-20260623T161630Z-claw`
- WSL runtime commit at launch: `2f8e9f21`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-validation-transfer-contract-rerun6r-ce5d884-20260617T152944Z/rep01/full_context/campaign`
- Model: `gpt-5.5`
- Rounds: `8`

Strict launch readiness passed before launch: runtime commit matched the
prepared manifest, runtime guard paths were clean, the prepared contract was
complete, the warehouse v2 follow-up handoff and prompt-context readiness were
present, and completion preflight was healthy.

The stored WSL postrun readiness generated at postrun time passed with
`current_run_analysis_ready=true`, `delegation_ready=true`, and no required or
optional readiness failures. A later checker rerun after the WSL checkout
advanced is covered by the stored-inventory recheck repair report. The local
mirror was produced with `scripts/sync_wsl_run_root.py --execute
--skip-postrun-check --format json`; the WSL postrun artifacts remain
authoritative because they contain WSL absolute paths.

## Lifecycle

- Wrapper exit/status: `0` / `finished`
- Validity/completeness: `valid` / `complete`
- Stop reason: `max_rounds_exhausted`
- Requested/effective rounds: `8` / `8`
- Effective Protocol rows: `8`
- Protocol metric rows: `10`
- Formal screened/evaluated candidates: `8` / `8`
- Proposal attempts total/consumed: `16` / `14`
- Proposal quality blocks: `6`
- Active-slot blocked attempts: `0`

The run completed naturally. The quality blocks did not prevent eight effective
Protocol rounds and did not indicate a scheduler or active-slot framework
blocker.

## Champion Progress

This is not new promotion evidence.

- Starting/current champion version: `2` / `2`
- Champion version gain: `0`
- Interpretation: `no_champion_version_gain_observed`

Some copied or resumed summaries still include the historical champion-`v2`
promotion evidence from the source campaign. Current-run champion progress must
therefore use the postrun analysis-brief/readiness champion-progress fields, not
only the aggregate `summary.json` promotion counter.

## Measurement Signal

Measurement readiness was `ready` with MDE `577.5`. All current-run effect rows
were below MDE, and every row with a CI high had CI high below MDE.

| Mechanism family | Rows | Positive | At/above MDE | CI high below MDE | Max effect/MDE |
|---|---:|---:|---:|---:|---:|
| empty_return_elimination | 1 | 0 | 0 | 1 | 0.0 |
| hazard_dg_downgrade_pack | 5 | 0 | 0 | 5 | 0.0 |
| merge_vehicles | 1 | 0 | 0 | 1 | 0.0 |
| move_order | 1 | 0 | 0 | 1 | -0.692641 |
| subcategory_upgrade_consolidate | 2 | 0 | 0 | 2 | 0.0 |

The protocol-effect interpretation was `all_available_ci_high_below_mde`.
Warehouse follow-up interpretation was
`protocol_evaluated_plateau_review_ready`; evidence gaps were empty and
`launch_required_before_plateau_conclusion=false`.

## Research Continuity

The run shows effective research behavior even though it did not promote:

- Active research shape: `deep_focused`
- Max/mean branch depth: `8` / `3.2`
- Active branch:
  `df94bd71-e4ca-40d5-91c9-99fc26048bf7`
- Active mechanism family: `hazard_dg_downgrade_pack`
- Branch depth distribution: `1=1, 2=2, 3=1, 8=1`
- Same-mechanism follow-up selected/observed/missed: `11` / `11` / `0`
- Branch lessons satisfied/required: `8` / `10`
- Branch-lesson semantic gaps: `0`
- Research-context actionability gaps: none

This is the key framework result: Scion did not stop at shallow isolated
attempts. It followed branch-local evidence, selected same-mechanism follow-up
when observed, retained prompt/source/context evidence, and produced
MDE-aware rejection rather than a false promotion.

## Quality And Failure Taxonomy

The run had six proposal quality blocks. The main blocked shapes were missing
bounded candidate/runtime policy, missing validation-transfer diagnostics, and
missing split-vs-cost effect-scope reasoning. These were proposal-quality
controls, not runaway runtime or scheduler failures.

Postrun failure report:

- `total_failures=0`
- no recent fatal failures
- nonfatal taxonomy still observed one `agentic_proposal:code_generation_failed`
  shape associated with proposal-quality blocking

The quality taxonomy is useful next-prompt guidance. It is not plateau evidence
by itself and did not block current-run Protocol evidence.

## Interpretation

Accepted interpretation for v0.4 framework evidence:

- Warehouse effective research is restored for this positive-control path:
  current-run evidence supports deep continuation, evidence-backed rejection,
  and plateau-review readiness after champion `v2`.
- The run does not prove continuous improvement from `v2`; champion stayed
  `v2`, every effect row was below MDE, and there was no positive-at-MDE row.
- The result is strong enough to stop blindly relaunching warehouse. One narrow
  repeat is only needed if the project wants an independent solver-level
  plateau confirmation; it is not the next framework repair prerequisite.
- v0.4 should now use this warehouse result as positive effective-research
  evidence and return attention to CVRP/VRP, where framework behavior has
  improved but solver promotion remains absent.

## Boundary

The conclusion is problem evidence and postrun delegated-analysis evidence. It
does not add warehouse-specific exceptions to generic Scion core, scheduler
logic, `DecisionFeatures`, Protocol gates, or runtime-pressure semantics.

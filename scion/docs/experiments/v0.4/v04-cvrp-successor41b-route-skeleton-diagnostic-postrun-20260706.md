# CVRP successor41b route skeleton diagnostic postrun

Date: 2026-07-06

## Run

Run root:

`/home/clawd/research/scion-experiments/v04-cvrp-successor41b-route-skeleton-diagnostic-server-claw-2r-gpt55-20260706T065434Z-claw`

Launcher commit: `cbfc4286`

The server-local `claw` run used local `gpt-5.5`, `--rounds 2`,
`--completion-preflight`, full proposal context, and no agentic tool or
observation caps. Completion preflight was healthy. The wrapper finished with
exit status 0, `run_validity_status=valid`,
`run_completeness_status=complete`, and
`postrun_acceptance_status=ready`.

## Accounting

- requested rounds: 2
- effective screening rounds: 2
- protocol metric results: 2
- formal screened candidates: 2
- proposal attempts: 4
- proposal quality blocks: 2
- LLM traces: 12
  - `hypothesis_target_intent`: 4
  - `hypothesis`: 4
  - `tool_selection`: 2
  - `code`: 2

Both quality blocks were non-infra blocks from
`cvrp_solver_design_causal_path_contract`. The first missed
`material_difference` and
`branch_lesson_usage.clean_fork_diversity_claim`; the second missed
`material_difference`. The retries then passed and produced code.

## Screening Results

Both screened candidates completed all 48 formal pairs with zero failed pairs.

Candidate `3a7ce17f-496a-4622-84ac-f1942146c258`:

- pair W/L/T: `17/17/14`
- median delta: `0.0`
- mean delta: `-0.12`
- P family: `2/4/2`, median `-2.0`
- B family: `0/4/0`, median `-5.0`
- CMT4: `1/0/3`, median `0.0`
- route-skeleton telemetry: runtime observed on 42/48 pairs, positive
  route-skeleton effect fields on 28/48 pairs

Candidate `40ef8f4e-fb0b-4681-90b3-12c84ae89866`:

- pair W/L/T: `12/15/21`
- median delta: `0.0`
- mean delta: `0.56`
- P family: `0/5/3`, median `-3.0`
- B family: `2/2/0`, median `-3.0`
- CMT4: `1/0/3`, median `0.0`
- route-skeleton telemetry: runtime observed on 48/48 pairs, positive
  route-skeleton effect fields on 33/48 pairs

The postrun research-efficiency report classifies both screening rows as below
MDE; max median delta is `0.0`, effect-to-MDE is `0.0`, and there is no
promotion signal.

## Case-Protection Caveat

The guidance required CMT2/CMT4 protection or an explicit split caveat. CMT2 is
present in `scion/problems/cvrp/formal/split_manifest.yaml`, but the actual
screening case set for this run included CMT3 and CMT4, not CMT2, and
`requested_priority_case_ids` was empty. Treat this as a measurement/enforcement
gap: protected-case intent reached the prompt and contract, but was not forced
into the measured case selection.

## LLM Trace Assessment

The model calls were healthy and used `gpt-5.5`. Target-intent calls selected
the correct mechanism and target file. The code calls had full source
visibility for the key solver files and no ledger truncation. Hypothesis calls
had one truncated `hypothesis_target_intent_preflight` entry, but the critical
successor41b guidance, prepared obligations, source context, branch lessons,
and telemetry requirements were visible.

The schema failures were reasonable, but costly. The model used plausible field
names such as `new_dimensions` or prose-only protection, while the contract
requires exact `material_difference.changed_dimensions`,
`material_difference.contrast`, `material_difference.evidence`, and structured
`branch_lesson_usage.clean_fork_diversity_claim`. This is not a reason to relax
the gate; the next repair should make the exact schema more prominent in the
prompt/retry template.

## Code Assessment

Both code patches improved over successor41's scheduler-helper growth by adding
a dedicated `policies/baseline_modules/route_skeleton_repair.py` module and
keeping scheduler integration narrow.

The discarded first patch was closer to the design diagnostically: it returned a
typed comparator result with default distance, skeleton distance, selected
label, margin, effort, and no-op reason. The retained branch simplified the
module and let it record telemetry directly, but did not retain structured
default-vs-skeleton fields such as selected label and no-op reason.

Both implementations activated the mechanism, but positive local skeleton
repair telemetry did not convert into final objective improvements after the
rest of ALNS/VNS. The mechanism remains loss-prone on P/B/E families and does
not produce a positive-at-MDE aggregate row.

## Decision

Do not long-run successor41b. Do not continue same-mechanism threshold tuning or
another route-skeleton repair optimization follow-up in v0.4.

Treat `route_skeleton_regret_repair` as diagnostic-exhausted, below-MDE,
protected-case-risk evidence. It may still be used as a telemetry or prompt
schema lesson, but not as the next optimization candidate.

## Next Actions

1. Update CVRP guidance so successor41b is no longer a live target-intent
   requirement.
2. Keep the causal-path quality gate, but put the exact
   `material_difference` schema into the retry template and prompt surface.
3. Add measurement/TASK guidance that protected CMT2/CMT4 cases must either be
   forced into the next formal screening case set or recorded as an explicit
   unresolved split caveat.
4. Clean-fork to a materially different CVRP-owned causal path after the schema
   and protected-case enforcement repairs are in place.

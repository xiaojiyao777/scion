# CVRP successor39 bounded dual repair selector postrun

Date: 2026-07-06

Run root:
`/home/clawd/research/scion-experiments/v04-cvrp-successor39-bounded-dual-repair-selector-server-retry-2r-gpt55-20260706T004158Z-claw`

## Verdict

Successor39 is valid current-run evidence, but not promotion evidence.

The run completed with local `gpt-5.5`, four model calls
(`hypothesis_target_intent`, `hypothesis`, `tool_selection`, `code`), no
model-call failure, no proposal-quality failure, no telemetry failure, and no
postrun acceptance failure. It screened two rows and promoted no champion.

Treat unchanged `bounded_dual_repair_selector` as reviewed below MDE. Do not
start a long-run or same-mechanism expansion from this evidence unless a future
design names a materially different causal path and fixes attribution quality.

## Evidence Summary

- Run validity: valid and complete.
- LLM calls: `gpt-5.5` x4 through the OpenAI-compatible provider.
- Protocol rows: 2 screening rows, 0 validation rows, 0 frozen rows.
- Champion promotions: 0.
- Postrun aggregate: 8 case wins, 5 case losses, 7 case ties; 41 pair wins,
  33 pair losses, 6 pair ties.
- Best row: median delta `0.75`, CI `[-6.25, 6.5]`, effect/MDE `0.075758`;
  the CI high stayed below the 9.9 MDE.
- Row 1: median delta `0.0`, CI `[-3.5, 6.5]`.
- CMT protection: CMT2 was positive in the expanded row (`+5.5` median), but
  CMT4 was negative (`-4.0` median). B and P families carried losses.
- Branch card status: marginal, candidate code discarded, evidence retained,
  mechanism contract observed positive effect, no promotion.

## Mechanism Analysis

The mechanism activated and produced local positive selector-phase telemetry,
but the local repair-selection signal did not propagate into promotion-grade
final solver objective improvement.

The implementation also showed attribution weakness: the default-vs-alternate
comparison was too compressed for later analysis, and the selected repair path
did not cleanly isolate whether objective changes came from the selector,
downstream VNS/polish, or trajectory noise.

Do not extend the same mechanism as-is. A narrowly scoped diagnostic follow-up
would only be useful if it isolates alternate-repair RNG, records default and
alternate operator/distance before VNS, records selected operator and accepted
flag, aligns repair-weight credit with the selected repair, and reports
post-VNS/final propagation. Otherwise the next CVRP slot should clean-fork to a
different problem-owned causal path.

## Prompt/Context Finding

The run exposed a framework research-quality issue.

The hypothesis stage saw successor39 focus, but fine-grained prepared evidence
obligations were not preserved as a stable contract into code generation. The
code prompt had no section truncation, yet it mainly saw the compressed
hypothesis implementation brief, which was declared the code-phase source of
truth. That allowed required details such as default repair operator/distance,
alternate repair operator/distance, selected operator, accepted flag, pre-VNS
objective delta, and CMT2/CMT4 evidence to collapse into broad telemetry
fields.

This is a negative context-composition path, not a budget-saving win.

## Accepted Framework Repair

The current checkout fixes the harmful path by:

- preserving typed/raw prepared evidence requirements in the launch guidance
  payload;
- rendering `Prepared Research Obligations` in target-intent, formal
  hypothesis, and code prompts;
- making code generation treat the implementation brief together with prepared
  obligations as source of truth;
- propagating prepared focus into code context and agentic patch flow;
- classifying the new prompt section as `research_signal` in prompt manifests;
- rejecting truncated target-file previews as sufficient grounding for
  solver-design target binding while still accepting full file reads or full
  target slices.

Targeted tests:

- `pytest -q scion/scion/tests/unit/test_research_surfaces_cvrp_context.py::test_cvrp_hypothesis_context_uses_prepared_launch_research_focus scion/scion/tests/unit/test_prepared_successor_focus.py scion/scion/tests/unit/test_problem_opportunity_prompt_projection.py`
- `pytest -q scion/scion/tests/unit/test_agentic_target_file_grounding.py::test_algorithm_slice_receipt_is_not_sufficient_target_file_grounding scion/scion/tests/unit/test_agentic_target_file_grounding.py::test_full_algorithm_slice_is_sufficient_target_file_grounding scion/scion/tests/unit/test_agentic_target_file_grounding.py::test_truncated_algorithm_file_grounding_is_not_sufficient scion/scion/tests/unit/test_agentic_target_file_grounding.py::test_target_intent_preflight_grounds_non_top_existing_target_before_first_hypothesis scion/scion/tests/unit/test_research_surfaces_cvrp_context.py::test_cvrp_hypothesis_context_uses_prepared_launch_research_focus scion/scion/tests/unit/test_prepared_successor_focus.py`

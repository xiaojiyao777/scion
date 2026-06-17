# CVRP Adaptive Trigger Agentic 4R Postrun

Date: 2026-06-17

## Purpose

Run a short CVRP agentic campaign after exposing the adaptive embedded-VNS
cadence-2 opportunity to solver-design proposal context. The intended research
task was to refine cadence-2 using objective, remaining-budget, recent
best-update, or repaired-candidate-improvement triggers rather than broad VNS
removal.

## Run

- Branch/commit: `codex/v04-evidence-repair-plan`, `7104928`.
- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-adaptive-trigger-agentic-4r-7104928-rerun-20260617T170017Z`
- Server sync:
  `/home/clawd/research/scion-experiments/v04-cvrp-adaptive-trigger-agentic-4r-7104928-rerun-20260617T170017Z`
- Model/provider: WSL-local `gpt-5.5`, `SCION_BASE_URL=http://127.0.0.1:8080`,
  `SCION_API_KEY=pwd`.
- Shape: `--rounds 4`, `--time-limit-sec 30`,
  `--agentic-session-timeout-sec 900`, measurement governance `on`,
  `compact-measurement-diagnostics`, disabled early stop, agentic proposal.
- Wrapper result: `exit_code=0`, `status=finished`,
  `started_at=2026-06-17T17:00:17Z`,
  `ended_at=2026-06-17T18:56:51Z`.

The immediately preceding shakedown that used `SCION_API_KEY=local-proxy`
failed with proxy `401 invalid_api_key` and is not research evidence.

## Campaign Accounting

- Stopped reason: `max_rounds_exhausted`.
- Experiments/effective rounds: `4/4`.
- Protocol rows: `4` screening, `0` validation, `0` frozen.
- Formal candidate artifacts: `3`.
- LLM traces: `19`, all `gpt-5.5`; request kinds `hypothesis=3`,
  `hypothesis_target_intent=3`, `tool_selection=8`, `code=5`.
- Champion remained `v1`; no promotion dossier.
- Runtime budget diagnostics: all four screening rows reported
  `SCREENING_RUNTIME_BUDGET_SATURATION`.

## Screening Results

Scion's DecisionFeatures are the authority for win/loss/tie semantics.

| Step | Branch | Target | Decision | Case W/L/T | Pair W/L/T | Median Delta | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | `d4bb4a52` | `destroy_repair.py` | `expand_screening` | `2/2/4` | `8/7/17` | `0.0` | Initial `route_limit_aware_regret_repair`; sufficient runtime evidence. |
| 2 | `d4bb4a52` | `destroy_repair.py` | `continue_explore` | `2/1/9` | `8/5/35` | `0.0` | Weak-signal continuation accepted. |
| 3 | `d4bb4a52` | `destroy_repair.py` | `continue_explore` | `2/2/4` | `7/8/17` | `0.0` | Same-branch refinement retained as active/marginal. |
| 4 | `24661c18` | `local_search.py` | `abandon` | `2/4/2` | `12/17/3` | `-3.0` | Clean-fork `inter_route_2opt_segment_relink`; archived as regression/loss-heavy. |

The main positive signal is not promotion. It is that the repaired framework
produced a branch with depth `3`, preserved a same-mechanism weak-positive
line, and passed branch-local lessons into later prompts. The active branch is
`route_limit_aware_regret_repair`, with best checkpoint retained and allowed
next actions including `refine`, `tune`, `integrate`, `parameterize`,
`diagnostic`, `observability`, `repair`, and `telemetry_wiring`.

## Mechanism Audit

The first route-limit repair candidate modified `destroy_repair.py` and wired
the new repair path through `scheduler.py`. When greedy/regret insertion could
not place a removed customer and the solution was already at `max_routes`, it
tried a bounded one-customer displacement before failing closed instead of
opening a new route. It recorded mechanism telemetry under
`route_limit_aware_regret_repair`.

The same-branch refinement added a local net-distance/reinsertability guard for
the displacement candidate and kept the same mechanism id.

The fourth candidate added an inter-route 2-opt segment relinking move to
`local_search.py`. It was a clean-fork diversity attempt, not a cadence-2
trigger refinement, and was abandoned by lifecycle policy.

## Prompt-Context Audit

Postrun audit found that the intended cadence-2 opportunity did not reach the
actual hypothesis prompts. The prompts contained generic solver-design provider
fallback guidance, but did not contain the CVRP provider text beginning
`Current CVRP no-LLM opportunity... adaptive embedded-VNS cadence-2...`.

Root cause: agentic context sanitization removes provider objects, while the
prompt engine's solver-design provider resolver short-circuited on the
non-callable sanitized `solver_design_prompt_provider` placeholder instead of
using `solver_design_prompt_provider_ref`.

Local repair after the run:

- `scion/scion/proposal/engine/solver_design_prompts.py` now ignores
  non-callable provider placeholders and can instantiate a provider from
  `solver_design_prompt_provider_ref`.
- `scion/scion/problems/cvrp/solver_design_provider.py` now treats the
  cadence-2 adaptive embedded-VNS opportunity as the explicit exception to the
  older "avoid blind scheduler tweaks" guidance, so the provider no longer
  steers away from the current target.
- `scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py` now
  covers sanitized provider context and asserts the cadence-2 opportunity text
  appears in the hypothesis prompt.

Validation:

- `python -m pytest scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py -q`
  -> `19 passed`.
- `python -m pytest scion/scion/tests/unit/test_cvrp_solver_design_provider.py scion/scion/tests/unit/test_research_surfaces_cvrp_context.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py -q`
  -> `45 passed`.
- `python -m py_compile scion/scion/proposal/engine/solver_design_prompts.py scion/scion/problems/cvrp/solver_design_provider.py`
  passed.
- `git diff --check` passed.

## Conclusion

Accepted as positive CVRP research-loop behavior evidence: Scion produced
replayable formal candidates, completed four screening rows, preserved a
same-mechanism weak-positive branch across multiple rounds, and rejected a
loss-heavy clean fork.

Not accepted as evidence that the cadence-2 adaptive embedded-VNS opportunity
was actually refined, because the opportunity text was absent from the live
hypothesis prompts. The provider-ref prompt repair must be included before the
next targeted CVRP agentic campaign.

Next action: rerun a short targeted CVRP campaign after this prompt repair and
verify in the live trace that the cadence-2 opportunity text is present before
interpreting the candidate mechanisms.

# v0.4 Mechanism Evidence Contract Repair

Date: 2026-06-23
Branch: `codex/v04-evidence-repair-plan`
Status: local and WSL focused tests pass; the old-checkout WSL solver-depth run
has finished and is accepted as Design K trigger evidence. The next step is a
synchronized CVRP solver-depth rerun from WSL head `92fff094`.

## Purpose

Design K repairs a generic v0.4 research-loop gap. A formal candidate can
declare a mechanism and add telemetry calls, but integrate the mechanism behind
a runtime path that Protocol does not execute. Screening then has structured
telemetry diagnostics showing that the declared mechanism was not evaluated or
triggered, yet the branch can be released as ordinary inactive evidence and the
scheduler may choose a clean fork.

That failure shape is framework evidence, not a CVRP heuristic conclusion.
The repair normalizes declared-mechanism telemetry diagnostics into a compact
mechanism-evidence contract used only by proposal, lifecycle, branch cards, and
scheduling. It is excluded from `DecisionFeatures`.

## Trigger Evidence

WSL trigger root:

`/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-solverdepth-65115459-postauthority-6r-gpt55-20260623T084213Z-claw`

Local mirror:

`/home/clawd/research/scion-experiments/v04-cvrp-solverdepth-65115459-postauthority-6r-gpt55-20260623T084213Z-claw`

WSL postrun acceptance is the authority for this old-checkout root. The local
mirror preserves artifacts for audit, but local postrun identity checks see the
original WSL `run_root` embedded in rebuild manifests.

This root finished from old WSL commit `65115459`, before the current local
Design H/I/J/K repairs were synced. Postrun acceptance passed: wrapper/postrun
exit `0`, readiness exit `0`, validity `valid`, completeness `complete`, 6 of
6 effective Protocol rows, 0 proposal quality blocks, 0 active-slot blocks, and
`last_stop_reason=max_rounds_exhausted`.

The accepted postrun brief reports no solver progress: champion stayed `v1`,
there were 0 promotions, all six protocol rows were below CVRP MDE, research
continuity was `wide_shallow`, max branch depth was 1, and the large-two-opt
summary reported missing direct mechanism signal.

The final current screening metrics are sufficient trigger evidence for
Design K:

- They declared `large_instance_intra_route_two_opt_seed`.
- They had telemetry guard `passed=true`, with warning diagnostics rather than
  hard gate failures.
- They showed `diagnostic_kind=not_evaluated/not_triggered` for the declared
  mechanism.
- They had phase buckets without the declared mechanism phase.

Interpretation: the agent reached formal hypothesis and code generation, but
the declared mechanism was not reached by the formal screening runtime path.
That should produce branch-local integration follow-up pressure, not a solver
quality conclusion and not automatic same-mechanism depth credit for a later
clean fork.

## Repair

New generic module:

- `scion/scion/core/mechanism_evidence_contract.py`

Thin integrations:

- `scion/scion/core/decision_lifecycle_actions.py` writes
  `mechanism_evidence_contract` into branch screening evidence and mirrors a
  compact status into `phase_activation_summary`.
- `scion/scion/core/branch_hygiene.py` treats a contract with
  `followup_required=true` and `decision_features_excluded=true` as an
  actionable diagnostic, allowing existing diagnostic scheduling lanes to
  select the branch.
- Branch cards expose compact mechanism contract status for proposal and
  operator visibility.

The contract maps structured telemetry guard diagnostics generically:

- `not_evaluated/not_triggered` -> `declared_not_triggered`, follow-up
  required.
- `wiring_suspect` / `runtime_budget_zero_or_subms` -> wiring/runtime
  diagnostic follow-up.
- `activated_no_positive_effect` -> effect-attribution follow-up.
- `evaluated_no_effect` -> observed no-effect, no wiring repair by default.
- Positive effect statuses -> observed positive evidence, no repair pressure.

## Verification

Local focused tests:

```bash
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/core/test_mechanism_evidence_contract.py scion/scion/tests/test_scheduler.py
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/core/test_branch_hygiene_status.py scion/scion/tests/unit/core/test_branch_card_scheduling_status.py scion/scion/tests/unit/test_runtime_telemetry_guard_mechanism_diagnostics.py
PYTHONPATH=scion python -m pytest -q scion/scion/tests/unit/test_screening_feedback_tiers_memory.py scion/scion/tests/unit/test_expected_telemetry_activation_contract.py
PYTHONPATH=scion python -m pytest -q scion/scion/tests/test_protocol_surface_runtime.py
PYTHONPATH=scion python -m py_compile scion/scion/core/mechanism_evidence_contract.py scion/scion/core/decision_lifecycle_actions.py scion/scion/core/branch_hygiene.py scion/scion/core/branch_cards.py scion/scion/core/branch_cards_evidence.py scion/scion/core/branch_cards_rendering.py scion/scion/tests/unit/core/test_mechanism_evidence_contract.py
git diff --check
```

Observed local results:

- `53 passed`
- `35 passed`
- `17 passed`
- `13 passed`
- py-compile passed
- `git diff --check` passed

The `test_evaluation_pipeline.py -k telemetry_guard` probe selected no tests;
it was not counted as coverage.

## Residual Work

WSL sync and focused verification are complete. Local head `416aec82` was
synced to WSL head `92fff094`; WSL conda passed the Design K/core groups
(`53`, `35`, and `30` tests), launcher/guidance tests (`48 passed`),
launch/postrun tool tests (`227 passed`), direct launcher entry checks,
py-compile, and diff checks.

Relaunch a synchronized CVRP solver-depth check from WSL head `92fff094`.
Acceptance requires showing that a declared not-triggered mechanism is routed
as branch-local diagnostic follow-up rather than being counted as ordinary
inactive clean-fork breadth.

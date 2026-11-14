# 04 - Branch Lifecycle and Evaluation

Audit focus: v3 branch lifecycle, scheduling, evaluation forwarding, and workspace retention behavior.

## P0 Findings

No P0 branch-lifecycle finding was identified. The current scheduler and lifecycle model are substantially closer to v3 than older retry-loop behavior, and high-priority branch states are explicit.

## P1 Findings

### P1-1: Regressive low-to-mid screening branches can continue and preserve workspace

- File paths:
  - `scion/scion/core/decision.py:87`
  - `scion/scion/core/decision.py:101`
  - `scion/scion/core/branch_lifecycle_policy.py:105`
  - `scion/scion/core/branch_lifecycle_policy.py:113`
  - `scion/scion/core/decision_finalizer.py:301`
  - `scion/scion/core/decision_finalizer.py:455`

- Problem:
  Screening candidates with `win_rate < 0.5` become `CONTINUE_EXPLORE`. The soft-abandon policy only applies when `win_rate < 0.3`. Separately, `_continue_explore` preserves branch workspace whenever `stats.win_rate > 0`, before applying the stricter low-signal preservation checks. A candidate around `win_rate=0.4` with negative median delta, losses, or runtime slowdown can therefore continue and keep a workspace.

- Why this violates or deviates from v3:
  v3 branch lifecycle distinguishes weak positive/mostly-tie signals from regressive candidates. Continuing a regressive branch after effective screening burns exploration budget and can carry bad active facts forward.

- Suggested fix:
  Apply lifecycle soft-abandon analysis to all screening `CONTINUE_EXPLORE` outcomes, not only `win_rate < 0.3`. Replace the unconditional `has_positive_signal = win_rate > 0` workspace preservation with the same non-regression predicate used by `_preserve_low_signal_screening_workspace`: non-negative median delta, no candidate failed pairs, no severe runtime slowdown/regression, and lifecycle reason codes that justify preservation.

- Suggested tests:
  Add tests for:
  - `win_rate=0.4`, `median_delta < 0`, losses present: soft-abandon or discard workspace.
  - `win_rate=0.4`, runtime slowdown/regression: soft-abandon or discard workspace.
  - weak positive mostly-tie, non-negative delta, no runtime regression: keep exploring and preserve workspace.

### P1-2: Validation telemetry repair path can bypass validation-stage semantics

- File paths:
  - `scion/scion/core/telemetry_validation.py:32`
  - `scion/scion/core/decision.py:29`

- Problem:
  Validation-stage telemetry activation failures are considered repairable, and decision logic returns `CONTINUE_EXPLORE` before validation-stage outcome logic.

- Why this violates or deviates from v3:
  Branch lifecycle should clearly separate exploratory repair from validation gate failure. A validation telemetry failure is not validated evidence; treating it as a normal continuation can hide gate failure in branch history.

- Suggested fix:
  Add an explicit branch lifecycle state or decision reason for validation telemetry repair, or make validation telemetry failures fail closed and require a fresh candidate/repair cycle from screening.

- Suggested tests:
  Add branch-state transition tests for validation telemetry guard failure showing the branch does not enter a generic `CONTINUE_EXPLORE` path without an explicit validation-repair state/reason.

## P2 Findings

### P2-1: `BLOCKED_INFRA` branches count against active capacity while unschedulable

- File path:
  - `scion/scion/core/scheduler.py:58`

- Problem:
  `BLOCKED_INFRA` branches are excluded from schedulable branches but still count toward `max_active_branches`.

- Why this violates or deviates from v3:
  This may be an intentional safety brake, but it can stall campaign progress if infra-blocked branches accumulate and no recovery/abandon cleanup runs promptly. v3 wants explicit infrastructure recovery without starving exploration.

- Suggested fix:
  Either document this as an intentional capacity policy and add recovery pressure, or exclude long-lived `BLOCKED_INFRA` branches from active capacity after a bounded recovery window.

- Suggested tests:
  Add scheduler tests where all active branches are `BLOCKED_INFRA` and the campaign is below/at capacity under the chosen policy. Assert the expected action is stable and documented.

### P2-2: Evaluation forwarding of selected surface is conditional on protocol shape

- File path:
  - `scion/scion/core/evaluation_pipeline.py:317`

- Problem:
  `_should_forward_selected_surface` only forwards `selected_surface` if the protocol method accepts the keyword and `_protocol_has_research_surfaces(protocol)` returns true.

- Why this violates or deviates from v3:
  For adapter-backed v3 protocols, selected surface is part of the safety boundary. A custom/stub protocol that accepts `selected_surface` but does not expose `research_surfaces` may silently skip selected-surface audit.

- Suggested fix:
  Fail closed for adapter-backed v3 problems when a selected surface is required but the protocol does not expose research-surface metadata. For pure legacy protocols, keep the current compatibility behavior explicitly gated.

- Suggested tests:
  Add a protocol stub that accepts `selected_surface` but lacks `research_surfaces`; assert v3 adapter-backed evaluation fails closed or logs a hard lifecycle failure instead of silently dropping the selected surface.


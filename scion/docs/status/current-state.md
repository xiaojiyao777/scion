# Scion v0.4 Current State

*Last updated: 2026-06-12*

This file is the short operational snapshot for onboarding and day-to-day
handoff. Historical repair and experiment notes were moved to
[`v0.4-history.md`](v0.4-history.md). Detailed experiment analyses live under
[`../experiments/v0.4/`](../experiments/v0.4/).

## Current Snapshot

Active implementation line: **v0.4 on `codex/v04-evidence-repair-plan`**.

The current project state is no longer "keep repairing v0.4 until the next
CVRP validation run." The latest 6/9-6/11 review set changes the operating
interpretation:

- The v3 control boundary remains the governing architecture:
  [`../../design/scion-architecture-v3.md`](../../design/scion-architecture-v3.md).
  LLM output is tainted proposal material; Contract, Verification, Protocol,
  safe feature extraction, and deterministic Decision remain the only path to
  promotion or abandonment.
- The required post-run audit method is now
  [`../../reports/v04-audit-agent-experiment-guide-20260609.md`](../../reports/v04-audit-agent-experiment-guide-20260609.md).
  Before interpreting a run, resolve the effective launched configuration from
  `launch.env`, `run.sh`, copied champion files, metrics, status, and summary;
  then separate proposal attempts, quality blocks, protocol rows, formal
  candidate artifacts, branch lifecycle, and Decision evidence.
- The 2026-06-10 CVRP/Warehouse 8R comparison, reviewed in
  [`../../reports/v04-core-framework-review-20260611.md`](../../reports/v04-core-framework-review-20260611.md)
  and
  [`../../reports/v04-core-framework-code-review-20260611.md`](../../reports/v04-core-framework-code-review-20260611.md),
  found no P0 break in the generic Scion loop. Warehouse still demonstrated the
  full screening -> validation -> frozen -> promotion path, while CVRP failed
  in screening because realistic candidate effects were below the current
  protocol's measurement resolution.
- The earlier
  [`../../reviews/scion-v04-diagnostic-audit-20260609.md`](../../reviews/scion-v04-diagnostic-audit-20260609.md)
  remains useful for the "research object must be measurable" lesson, but its
  strongest all-tie/VNS-erasure framing should be read through the later 6/11
  audits: non-tie CVRP pairs exist, yet win/loss signal is still too close to
  noise for the current gate.
- The current forward plan is split across v0.4 closeout and the 6/11
  evidence-uplift proposal:
  [`../../design/v0.5-evidence-uplift-roadmap.md`](../../design/v0.5-evidence-uplift-roadmap.md).
  v0.4 should land the repair/readiness pieces needed to make VRP and
  warehouse research meaningful; v0.5 should run the broader controlled
  experiment matrix that evaluates Scion's value.

## Current Interpretation

v0.4 is still the code version, and it must finish the repair work needed for
real VRP and warehouse research before v0.5 starts the broad experiment matrix.
CVRP/VRP is not written off: prior Scion history includes a VRP runtime/algorithm
efficiency promotion where candidate quality did not regress and runtime was
better than baseline. The v0.4 task is to make that kind of evidence measurable
and reproducible under the current framework, while preserving the v3 boundary.

The current high-value v0.4 work is now a closeout-and-next-rung sequence:

1. Preserve the completed v0.4 measurement/runtime semantics repairs:
   problem-owned practical deltas, budget-exhausting runtime interpretation,
   no meaningless runtime-tie fresh replay, and A/A noise-floor calibration.
2. Use the Phase 4 audits to decide the next measurement rung. CVRP is now
   auditable and produces real solver-design signals, but its 4-seed screening
   protocol is still underpowered relative to the Phase 1 MDE.
3. Preserve and validate runtime-improvement promotion semantics for VRP:
   candidates may advance when objective quality ties or remains non-regressive
   and runtime evidence is complete and materially better.
4. Treat the completed warehouse ON/OFF run as a shakedown, not a formal
   governance-value conclusion. It validated the switch and warehouse promotion
   path, but the LLM trajectories and promoted patches diverged. Formal
   governance experiments should use fixed-candidate replay first; fixed-order
   proposal replay is deferred. The completed CVRP 8-seed A/A check still
   measured MDE `9.6`, so CVRP remains low-power for
   `practical_delta_screen=2.0` and should not be the next formal governance
   target or long promotion campaign without another pre-registered measurement
   change.
5. Use v0.5 for the larger experiment program: governance ablations,
   reproduction matrices, problem-family comparisons, prompt/context ablations,
   and mechanism studies that quantify Scion's value.

The active v0.4 task breakdown is
[`../planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md`](../planning/v0.4/v0.4-evidence-repair-and-validation-plan-20260611.md).

## 2026-06-11 Implementation Snapshot

- Measurement layer: `ProblemSpecV1.measurement` now declares runtime model,
  pairing validity, effect metric/unit, practical deltas, and calibration refs.
  Protocol config resolves those values for screening/validation thresholds and
  CLI entrypoints thread problem-v1 measurement into protocol config.
- Runtime governance: CVRP declares `runtime_model: budget_exhausting`; runtime
  budget saturation becomes non-actionable info in that model; meaningless
  fresh-champion replay for cached runtime ties is disabled; V9 now treats
  budget-exhausting runtime as budget compliance instead of champion slowdown
  ratio.
- A/A calibration: `scion/tools/calibrate_aa_noise.py` can produce
  `scion.aa_noise_floor.v1` artifacts. Minimal CVRP controlled smoke passed at
  5s/10s. Phase 1 formal A/A is concluded: warehouse create/modify
  calibrations finished cleanly, and the final CVRP protocol-time screening
  calibration finished with `n_pairs=96`, MDE `9.9` raw `total_distance`, and
  false-pass rate `0.0`. The final note is
  [`../experiments/v0.4/v04-phase1-aa-calibration-20260611.md`](../experiments/v0.4/v04-phase1-aa-calibration-20260611.md).
- Phase 1 calibration evidence closure: the A/A tool now records replayable
  pair evidence, selected cases/seeds, replicate count, seed offset, bootstrap
  samples, selected surface, safe data roots, case resolution, elapsed runtime,
  and runtime-policy metadata. It can wire declared problem data roots and can
  use protocol-resolved per-case time limits. The CVRP uniform-60s artifact
  remains a legacy uniform-budget estimate; the protocol-time artifact is the
  formal Phase 1 result.
- Research shape/context: campaign summary/status expose read-only branch-depth
  and mechanism-family diagnostics; prompt manifests expose block-family token
  accounting and research-signal/governance ratios; hypothesis prompts now show
  compact branch/history/research signals before broader governance rules.
- Verification: focused regression currently covers measurement/runtime/V9,
  prompt context density, campaign observability, and CVRP actionability paths.

## 2026-06-11 Phase 0 Evidence Baseline

The paired 4R verification runs launched from commit `0a6a2f5` have both
finished with wrapper exit status 0. The frozen postrun baseline is
[`../experiments/v0.4/v04-evidence-verify-4r-gpt55-20260611-phase0-postrun.md`](../experiments/v0.4/v04-evidence-verify-4r-gpt55-20260611-phase0-postrun.md).

- CVRP run:
  `/home/clawd/research/scion-experiments/v04-evidence-verify-cvrp-4r-tl30-20260611-4r-gpt55-20260611T145506Z-claw`
  ended at `2026-06-11T16:26:59Z`. It completed `4/4` effective rounds, all
  screening rows; validation and frozen rows were both 0. Pair-level movement
  existed, but case-level gate win rates remained below threshold and no
  candidate advanced.
- Warehouse run:
  `/home/clawd/research/scion-experiments/v04-evidence-verify-warehouse-4r-defaultbudget-20260611-4r-gpt55-20260611T145506Z-claw`
  ended at `2026-06-11T15:30:12Z`. It completed `4/4` effective rounds with a
  full screening -> validation -> frozen -> promotion path for
  `operators/consolidate_subcategory.py`, producing champion v2, followed by a
  failed modify attempt.
- Runtime governance check: neither run consumed fresh-runtime replay rows.
  CVRP cached champion runtime aggregates were excluded from standalone speed
  claims; warehouse runtime evidence remained high-confidence.
- Context check: CVRP prompt manifests remain much larger than warehouse and
  still need problem-owned diagnostics for per-case opportunity, MDE/noise, and
  mechanism-effect ranking. Source/code visibility was present and must remain
  protected during any context compression.

The current step is Phase 4 closeout from `TASK.md`. First-rung CVRP and
warehouse validation runs are complete and audited. Phase 3 measurement
readiness is integrated: compact Phase 1 A/A artifacts are installed, CVRP and
warehouse `calibration_ref` paths resolve, and missing/stale/incompatible
calibration is visible as readiness/status without exposing raw A/A diagnostics
to `DecisionFeatures`. The next gate is not a blind long campaign; it is a
power-adjusted CVRP measurement check and a governance on/off design that uses
an effect-measurable problem/protocol.

## 2026-06-11 Phase 1 A/A Calibration

Phase 1 is concluded and recorded in
[`../experiments/v0.4/v04-phase1-aa-calibration-20260611.md`](../experiments/v0.4/v04-phase1-aa-calibration-20260611.md).

- Warehouse `create_new` A/A finished with `n_pairs=60`,
  `mde_at_power_80=1725.0` raw `total_cost`, and
  `false_pass_rate_at_current_gate=0.0`.
- Warehouse `modify` A/A finished with `n_pairs=36`,
  `mde_at_power_80=577.5` raw `total_cost`, and
  `false_pass_rate_at_current_gate=0.0`.
- CVRP `modify` A/A has one failed diagnostic run, one successful legacy
  estimate, and one successful formal protocol-time run. The first safe-root
  `tl30` run failed on `M/M-n200-k17.vrp` with a solver timeout, confirming
  that calibration needed protocol runtime-rule support. The corrected
  uniform-60s legacy run finished at `2026-06-11T20:34:59Z` with `n_pairs=96`,
  `mde_at_power_80=8.7` raw `total_distance`, and
  `false_pass_rate_at_current_gate=0.0`; its artifact is
  `/home/clawd/research/scion-experiments/v04-phase1-aa-cvrp-screening-modify-r3-tl60-saferoot-20260611T175414Z-claw/aa_noise_floor.json`.
  This remains a legacy uniform-budget estimate.
- The repaired formal protocol-time CVRP A/A run finished at
  `2026-06-11T22:03:18Z` from commit
  `a43dc2be371b5f2f209477df54883708b8750055` with wrapper exit status 0:
  `/home/clawd/research/scion-experiments/v04-phase1-aa-cvrp-screening-modify-r3-protocoltime-20260611T191356Z-claw/aa_noise_floor.json`.
  It used the formal split, seed ledger, declared data-root wiring, and
  `--runtime-policy protocol_time_limits`. It produced `n_pairs=96`,
  `mde_at_power_80=9.9` raw `total_distance`,
  `false_pass_rate_at_current_gate=0.0`, and `recommended_min_seeds=8`.
  Pair evidence is complete and protocol-resolved pair time limits are present.
- Read-only subagent cross-check `019eb86b-228f-7e92-913a-c7e873614a5e`
  accepted the legacy CVRP interpretation: Phase 0 CVRP median effects were all
  `0.0`, the best CI upper bound was `8.0`, and the legacy MDE was `8.7`, so
  the evidence supports "below measured screening power" rather than
  "mechanism disproven."
- Read-only subagent cross-check `019eb8b9-005b-7203-a3b2-d7dcc1e4bec8`
  validated the final protocol-time CVRP artifact and accepted it as satisfying
  the CVRP-specific Phase 1 checklist.
- Phase 1 conclusion: current CVRP `practical_delta_screen=2.0` is below the
  formal A/A MDE of `9.9` by `4.95x`. Phase 0 CVRP failures were below measured
  screening power, not proof that the mechanisms were intrinsically bad. Phase
  2 framework repair can start, but blind gate/lifecycle tuning is not an
  accepted fix.

## 2026-06-11 Phase 2 Framework Repair

Phase 2 first repair slice is integrated in
`codex/v04-evidence-repair-plan`.

- F-1/F-2 baseline verified: problem-owned practical deltas resolve into
  protocol thresholds; `runtime_model: budget_exhausting` suppresses
  meaningless runtime-tie fresh replay, downgrades budget saturation to info,
  and keeps V9 semantics as budget compliance. Focused F-1/F-2 suite passed
  with `135 passed`.
- F-3 low-SNR repair: `ProtocolConfig` now resolves deterministic
  `pairing_validity` from problem measurement declarations. Screening gates and
  Decision can expand tie-heavy or weak non-negative low-SNR evidence below
  `0.5` aggregate win rate only for `trajectory_divergent` problems. Negative
  median delta, loss-heavy evidence, candidate failures, runtime guard
  failures, and true runtime regressions still fail closed.
- Lifecycle depth: trajectory-divergent low-SNR research receives relaxed
  lifecycle thresholds so same-mechanism follow-up can continue beyond shallow
  one-off attempts. Warehouse `trajectory_stable` behavior remains unchanged.
- Context/source repair: hypothesis prompts receive tainted problem-owned
  measurement/noise/opportunity diagnostics as research signal while filtering
  raw calibration rows, validation/frozen detail, BKS/gap detail, LLM text,
  prompt ratios, and raw cross-branch material. Code-phase prompt manifests now
  expose `code_phase_source_guarantees` / `source_visibility_guarantees` so
  target source and required integration source survival can be audited after
  compression.
- v3 boundary cleanup: generic mechanism-signature grouping no longer hardcodes
  `vns`; the v3 generic-layer boundary test passes.
- Integrated verification:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/test_config.py scion/scion/tests/test_problem_bridge.py scion/scion/tests/test_problem_adapter.py scion/scion/tests/test_cli_run_options.py scion/scion/tests/test_protocol_stats_gates.py scion/scion/tests/test_decision_screening.py scion/scion/tests/unit/core/test_branch_lifecycle_policy.py scion/scion/tests/unit/core/test_scheduler_runtime_evidence_pressure.py scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py scion/scion/tests/test_verification_gate_integration.py scion/scion/tests/unit/test_runtime_feedback_guidance.py scion/scion/tests/unit/test_hypothesis_context_profiles.py scion/scion/tests/unit/test_prompt_manifest_accounting.py scion/scion/tests/unit/test_cross_branch_research.py scion/scion/tests/unit/test_agentic_solver_design_prompt_payloads.py scion/scion/tests/unit/test_agentic_target_file_grounding.py scion/scion/tests/unit/test_agentic_session_tool_selection.py`
  passed with `311 passed`. The follow-up boundary subset
  `test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py` plus key Phase
  2 tests passed with `149 passed`.

## 2026-06-11 Phase 3 Measurement Readiness

Phase 3 minimal measurement readiness is integrated.

- `scion.measurement.readiness.measurement_readiness_status()` resolves
  problem-owned `calibration_ref` paths, checks schema/problem/metric/unit
  compatibility, reports missing/unreadable/incompatible/incomplete/stale
  states, and reduces compatible A/A artifacts to deterministic status fields:
  MDE, noise band, effect-to-MDE ratio, signal-to-noise tier, age, and reason
  code.
- `ProtocolConfig.measurement_readiness` carries only reduced enum/numeric
  readiness status. Proposal context may see the tainted problem-owned
  `calibration_ref`, but raw pair rows, per-case details beyond the reduced
  noise band, BKS/gap detail, and free-form text remain excluded from
  `DecisionFeatures`.
- Compact Phase 1 calibration artifacts are installed at
  `scion/scion/problems/cvrp/formal/calibration/aa_noise_floor.json` and
  `surrogate/calibration/aa_noise_floor.json`. These compact artifacts include
  source artifact refs and SHA256 hashes but omit raw `pair_evidence`.
- As of 2026-06-11, CVRP readiness is `ready`, MDE `9.9`, effect-to-MDE ratio
  `0.202`, tier `low_power`; warehouse readiness is `ready`, MDE `577.5`,
  effect-to-MDE ratio about `1.7e-6`, tier `low_power`.
- Focused Phase 3 verification passed with `34 passed` across measurement
  readiness, problem bridge, config, and hypothesis-context tests.

Phase 4 first-rung validation has since completed. The postrun audits now
provide the branch-depth, same-mechanism continuation, cross-branch transfer,
prompt context, runtime semantics, and A/A-MDE interpretation required before
the next experiment rung.

## 2026-06-11 Phase 4 Focused Validation Launched

The first-rung 4R focused validation runs are launched from commit `32ab596`
with local `gpt5.5`, `--disable-early-stop`, and `--agentic-proposal`.

- CVRP formal:
  `/home/clawd/research/scion-experiments/v04-phase4-focused-cvrp-measreadiness-20260611-4r-gpt55-20260611T224916Z-claw`
  (launcher PID `1753912`). It uses
  `scion/problems/cvrp/formal/protocol.yaml`,
  `scion/problems/cvrp/formal/split_manifest.yaml`,
  `scion/problems/cvrp/formal/seed_ledger.yaml`,
  `SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp`,
  and `--time-limit-sec 30`.
- Warehouse production:
  `/home/clawd/research/scion-experiments/v04-phase4-focused-warehouse-measreadiness-20260611-4r-gpt55-20260611T225004Z-claw`
  (Python PID `1754001`). It uses
  `scion/problems/warehouse_delivery/protocol_prod.yaml`,
  `scion/problems/warehouse_delivery/split_manifest_prod.yaml`,
  `scion/problems/warehouse_delivery/seed_ledger.yaml`, and
  `--time-limit-sec 30`.

Do not advance to governance on/off until these runs finish and are audited
against `v04-audit-agent-experiment-guide-20260609.md`: effective rounds,
formal screened candidates, branch depth, same-mechanism follow-up,
cross-branch transfer, prompt context/source visibility, runtime semantics, and
candidate evidence relative to A/A MDE.

Warehouse status: the warehouse run finished with wrapper exit status 0, but it
is invalid for Phase 4 validation. `run.log` reports `experiments  : 0`; status
shows `effective_rounds_completed=4` and legacy `formal_screened_candidates=4`,
but `effective_protocol_rounds=0`, `protocol_metric_results=0`, and
`screening_protocol_results=0`. All four candidates passed Contract and
Verification, then were abandoned with `CANARY_FAILED` before protocol
screening rows were produced. There is no formal candidate index and protocol
`raw_metrics_ref` is missing. Treat this as a canary evidence/accounting repair
finding, not warehouse research evidence. Worker H is preparing a generic
repair so canary-vetoed candidates are not misreported as formal
screened/effective protocol evidence and canary failure details are auditable
before rerun.

Canary accounting repair status: Worker H's generic repair has passed main
thread acceptance in the canary accounting repair commit. Canary vetoes now
persist structured `canary_result` details in status/summary, including case IDs,
seeds, failed case/seed, candidate and champion outcomes, failure reason, and
`raw_metrics_unavailable_reason=canary_veto_before_formal_protocol`. A
canary-vetoed attempt no longer backfills `formal_screened_candidates`,
`protocol_evaluated_candidates`, `screening_protocol_results`, or
`effective_protocol_rounds`; legacy reported counters are retained under
`legacy_*_reported` fields for audit. Terminal runs with consumed effective
attempts but zero protocol rows are marked `invalid_no_protocol_rows`.
Verification passed with
`PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/unit/core -q`
(`489 passed`),
`PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/test_protocol_canary.py scion/scion/tests/unit/protocol/test_protocol_correctness.py scion/scion/tests/test_cvrp_protocol_smoke.py -q`
(`31 passed`), and `git diff --check`.

Warehouse accounting verification rerun: the canonical rerun is
`/home/clawd/research/scion-experiments/v04-phase4-focused-warehouse-canaryfix-foreground-20260611-4r-gpt55-20260611T234843Z-claw`,
launched from repair commit `a6a34d6` with the same production warehouse
protocol/split/seeds and local `gpt5.5`. It finished with wrapper exit 0 at
`2026-06-11T23:55:48Z`, consumed four attempts, produced `experiments  : 0`,
and is correctly invalid as scientific evidence:
`effective_rounds_completed=4`, `formal_screened_candidates=0`,
`protocol_evaluated_candidates=0`, `effective_protocol_rounds=0`,
`screening_protocol_results=0`, `protocol_metric_results=0`, and
`run_validity.reason=invalid_no_protocol_rows`. `campaign_summary.json` contains
four canary-failed steps with `raw_metrics_unavailable_reason=
canary_veto_before_formal_protocol`; the DB has four abandoned branches with
`failure_codes=[CANARY_FAILED]`; no formal candidate index/artifacts were
written.

The rerun also exposes the next warehouse blocker: strict canary case resolution
rejects `artifact:instance_prod_can_s01.json#64a747f955e8` as
`absolute_outside_roots`. Treat that as a warehouse problem-package safe-root
configuration issue, not as agent research evidence. Curie
(`019eb91b-4d3c-74c0-b220-793cbe96639d`) is investigating a minimal
problem-owned fix. The CVRP Phase 4 run remains in progress from commit
`32ab596` at this point in the chronology; do not interpret it as exercising
the later canary accounting fix. That CVRP run has since completed and is
audited below.

Warehouse safe-root repair status: Curie's problem-owned fix is accepted. The
production warehouse split now declares `safe_data_roots:
../../../../scion-data`, allowing the existing production absolute case paths to
resolve under strict protocol without moving warehouse semantics into generic
core. The focused test
`test_warehouse_prod_canary_paths_run_under_strict_protocol` verifies canary
paths resolve as `resolved_safe_data_root` and reach `run_canary` with a mock
runner. Acceptance passed with
`PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/unit/protocol/test_case_path_safety.py scion/scion/tests/unit/test_cli_data_roots.py scion/scion/tests/test_e2e.py::TestWarehouseDeliveryConfig -q`
(`12 passed`) and `git diff --check`.

The warehouse safe-root repair was then committed and used for the canonical
warehouse Phase 4 rerun below.

Warehouse Phase 4 safe-root rerun: the canonical valid warehouse run is
`/home/clawd/research/scion-experiments/v04-phase4-focused-warehouse-saferoot-20260611-4r-gpt55-20260612T000035Z-claw`,
launched from commit `63f01d7` with the production warehouse protocol/split/seeds
and local `gpt5.5`. It finished with wrapper exit 0 at
`2026-06-12T00:17:02Z`, `run_validity.reason=valid`, and champion v1:
`effective_rounds_completed=4`, `effective_protocol_rounds=4`,
`formal_screened_candidates=4`, `protocol_evaluated_candidates=4`,
`screening_protocol_results=5`, `protocol_metric_results=5`,
`validation_protocol_results=0`, and `frozen_protocol_results=0`. The fifth
screening row is a non-counted `fresh_runtime_replay` closure after max rounds;
candidate reconciliation reports 4 formal candidate artifacts and explains the
extra metric row as non-effective/non-counted. Decisions were three
`continue_explore`, one `abandon`, then one non-counted replay
`continue_explore`; no promotion occurred.

The warehouse postrun audit below closes that rerun against the 2026-06-09
guide: branch depth, same-mechanism follow-up, fresh-runtime replay cause,
prompt/source visibility, measurement-readiness context, and candidate evidence
relative to warehouse A/A MDE. Governance on/off remains gated on both
warehouse and CVRP audit completion.

Warehouse Phase 4 postrun audit is complete:
[`../experiments/v0.4/v04-phase4-warehouse-saferoot-4r-postrun-20260612.md`](../experiments/v0.4/v04-phase4-warehouse-saferoot-4r-postrun-20260612.md).
Conclusion: this is valid Phase 4 no-promotion evidence. The count reconciliation
is healthy (`5` screening protocol rows = `4` counted candidates + `1`
non-counted fresh-runtime replay closure), all four formal candidates have
complete replay identity, and no candidate was ready for validation relative to
warehouse A/A readiness. Candidate 1 was weak mixed signal with median delta `50`
below the modify MDE `577.5`; candidates 2 and 3 were zero-effect
same-mechanism follow-ups; the clean fork was negative. Prompt/context visibility
looked adequate and v3 boundaries held. Remaining follow-up: keep
fresh-runtime replay out-of-band in Phase 5 accounting/design and improve
top-level counter rendering so replay closure rows are harder to misread as
extra research candidates.

CVRP Phase 4 first-rung run is complete:
`/home/clawd/research/scion-experiments/v04-phase4-focused-cvrp-measreadiness-20260611-4r-gpt55-20260611T224916Z-claw`,
launched from commit `32ab596` with the formal CVRP protocol/split/seeds and
local `gpt5.5`. It finished with wrapper exit 0, `run_validity.reason=valid`,
and champion v1: `effective_rounds_completed=4`,
`effective_protocol_rounds=4`, `formal_screened_candidates=4`,
`screening_protocol_results=4`, `protocol_metric_results=4`,
`validation_protocol_results=0`, and `frozen_protocol_results=0`. The four
screening decisions were `expand_screening`, `continue_explore`,
`expand_screening`, and `abandon`; no promotion occurred. Postrun audit is
complete:
[`../experiments/v0.4/v04-phase4-cvrp-measreadiness-4r-postrun-20260612.md`](../experiments/v0.4/v04-phase4-cvrp-measreadiness-4r-postrun-20260612.md).
The audit accepts the run as valid screening-only evidence. Count
reconciliation is clean (`4` effective protocol rows, `4` screening metric
rows, and `2` replayable patch artifacts reused by expansion rows), evidence
and lineage are complete, and v3 boundaries held. Runtime semantics are much
healthier than the audited pre-repair pattern: no fresh-runtime replay drain,
budget-exhausting V9 is budget-compliance based, and saturation remains
info-only.

CVRP research interpretation: the agent generated real mechanisms and branch
follow-up. `route_limit_aware_repair` was essentially all tie and did not
approach the Phase 1 MDE. `double_bridge_relink_vns` produced the strongest
signal, moving from `17/9/6` pair evidence initially to `22/19/7` after
expansion, but final median was `-1.25` with CI `[-5.75, 7.25]`; the high CI
bound remains below the CVRP A/A MDE `9.9`. Therefore Phase 4 proves improved
auditability/runtime/context/branch mechanics, but not CVRP quality-improvement
readiness under the current 4-seed protocol. The next CVRP action should be an
8-seed or otherwise power-adjusted screening configuration check before any
long promotion run.

## 2026-06-12 Phase 4 Closeout Next-Rung Design

Two read-only subagent design passes are complete:

- Schrodinger designed the CVRP power check. The next CVRP measurement rung is
  an 8-case x 8-seed x 3-replicate A/A calibration with protocol-resolved
  runtime limits and no LLM calls. It uses temporary run-root copies of
  protocol/seed/split config rather than editing the formal repo baseline. The
  added screening seeds are `73,79,97,103`, preserving the existing
  `11,29,43,59` seeds and avoiding validation/frozen/canary reuse.
- Lovelace designed the governance on/off starting point. The first
  measurement-governance on/off candidate should be warehouse production
  saferoot, not current CVRP. CVRP remains blocked from being the first
  governance-value target until the power-adjusted check shows the measurement
  can detect the expected effect.

CVRP 8-seed A/A postrun:

- Failed diagnostic attempt:
  `/home/clawd/research/scion-experiments/v04-phase4-cvrp-8seed-aa-20260612T011722Z-claw`.
  It exited before solver execution because the temporary protocol copy lived
  outside the formal budgets path, so `cvrplib/...` cases did not receive a
  safe data root.
- Accepted saferoot rerun:
  `/home/clawd/research/scion-experiments/v04-phase4-cvrp-8seed-aa-saferoot-20260612T011824Z-claw`.
  It used run-root copies of `protocol.yaml`, `seed_ledger.yaml`, and
  `split_manifest.yaml`; the split copy declares
  `/home/clawd/research/or-autoresearch-agent/vrp` as `safe_data_roots`. The
  run had `power_cases=8`, screening seeds
  `11,29,43,59,73,79,97,103`, `replicates=3`,
  `--runtime-policy protocol_time_limits`, champion v1 from the completed CVRP
  Phase 4 run, and no LLM calls.
- Report:
  [`../experiments/v0.4/v04-phase4-cvrp-8seed-aa-postrun-20260612.md`](../experiments/v0.4/v04-phase4-cvrp-8seed-aa-postrun-20260612.md).
  The run completed at `2026-06-12T04:13:56Z` with wrapper exit `0`,
  `n_pairs=192`, complete raw pair evidence, MDE `9.6` raw `total_distance`,
  false-pass rate `0.0`, and `recommended_min_seeds=16`.
- Interpretation: the 8-seed check does not solve CVRP measurement power. MDE
  moved only from Phase 1 `9.9` to `9.6`, still `4.8x` above the declared
  `practical_delta_screen=2.0`. CVRP remains a low-power measurement/research
  mechanics pressure test until the protocol, seed/case budget, runtime
  resolution, or effect scale changes. The `CMT4` runtime caveat is now handled
  by an explicit formal-protocol `case_globs` pre-registration that assigns
  `CMT4` to the 45s screening budget.

Governance on/off implementation status:

- The minimal `measurement_governance` switch is implemented and accepted.
  `scion run` exposes `--measurement-governance {on,record-only}`. Default ON
  preserves current measurement-aware protocol/runtime/lifecycle/context
  behavior. Record-only/OFF computes and persists reduced measurement-readiness
  status, but does not copy problem measurement into practical deltas, runtime
  model, or pairing validity, and suppresses prompt-visible measurement
  diagnostics. `objective_opportunity_profile` remains visible because it is
  derived from recent protocol objective deltas and adapter objective policy,
  not from `problem_spec.measurement`.
- Acceptance passed:
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/test_config.py scion/scion/tests/test_cli_run_options.py scion/scion/tests/unit/test_hypothesis_context_profiles.py scion/scion/tests/unit/test_prompt_manifest_accounting.py -q`
  (`40 passed`);
  `PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest scion/scion/tests/test_protocol_stats_gates.py scion/scion/tests/test_decision_screening.py scion/scion/tests/unit/core/test_branch_lifecycle_policy.py scion/scion/tests/unit/core/test_runtime_budget_diagnostics.py scion/scion/tests/test_verification_gate_integration.py -q`
  (`124 passed`);
  full `unit/core` (`489 passed`); problem/boundary/context subset
  (`113 passed`); Python compile on touched files; and `git diff --check`.
- Warehouse production saferoot has now been used for a small ON/OFF shakedown.
  The run validates switch mechanics and the warehouse promotion path, but not
  governance-value causality. Warehouse measurement practical deltas are still
  `0.001`, and the first contrast is driven more by context/readiness exposure,
  replay/accounting behavior, and LLM trajectory divergence than by
  practical-delta thresholds.

Warehouse governance ON/OFF shakedown postrun:

- Launched from commit `f604e81` at `2026-06-12T01:31:19Z` with local
  `gpt5.5`, production warehouse saferoot protocol/split/seeds, `--rounds 8`,
  `--time-limit-sec 30`, `--disable-early-stop`, and `--agentic-proposal`.
- ON arm:
  `/home/clawd/research/scion-experiments/v04-phase5-governance-warehouse-on-pilot-8r-gpt55-20260612T013119Z-claw`,
  `--measurement-governance on`, ended `2026-06-12T02:22:45Z`, wrapper exit
  `0`.
- Record-only/OFF arm:
  `/home/clawd/research/scion-experiments/v04-phase5-governance-warehouse-record_only-pilot-8r-gpt55-20260612T013119Z-claw`,
  `--measurement-governance record-only`, ended `2026-06-12T02:23:30Z`,
  wrapper exit `0`.
- Postrun report:
  [`../experiments/v0.4/v04-phase5-warehouse-governance-onoff-8r-postrun-20260612.md`](../experiments/v0.4/v04-phase5-warehouse-governance-onoff-8r-postrun-20260612.md).
  Both arms were `valid` and `complete` with `8/8` effective protocol rows,
  `6` screening rows, `1` validation row, `1` frozen row, and champion v2.
- Interpretation: this is a successful shakedown, not a causal on/off result.
  ON promoted `split_safe_cost_merge`; record-only promoted `best_of_k_merge`.
  Both modified `operators/merge_vehicles.py`, but the patches and LLM paths
  differed. Record-only suppressed `problem_measurement_diagnostics` while
  still exposing opportunity/runtime/cross-branch research signals. Code-phase
  champion and target source visibility held in both arms.
- Accepted post-shakedown repair slice: `campaign_summary.json` now records
  `measurement_governance`; CLI/status/summary tests assert governance
  observability; prompt/context tests assert record-only measurement diagnostic
  suppression and code-phase source visibility; CVRP formal protocol explicitly
  assigns `CMT4` to the 45s screening budget; expanded-screening borderline
  advance is protocol-configured instead of hidden in `Decision`; fresh-runtime
  replay pressure now distinguishes "no scheduler-eligible replay candidate"
  from materialization failures; and same-branch hypotheses persist
  `parent_hypothesis_id` for branch-depth audits without entering
  `DecisionFeatures`.
- Acceptance for that slice: targeted repair suite `296 passed`, full
  `unit/core` `494 passed`, protocol/adapter subset `99 passed`, Python compile
  on touched core/config files, and `git diff --check`.
- Accepted: fixed-candidate replay manifest builder and measurement-only OFF
  audit assertions are implemented. Fixed-order proposal replay remains deferred
  because the current APS replay surface validates stored artifacts but does not
  safely re-execute the same LLM/tool trajectory, and scheduler order is dynamic.
  The lower-risk v0.4 control is a `fixed_candidate_replay_manifest.v1` built from
  `formal_candidates/index.jsonl` and `candidate.patch.json`, then used to
  evaluate identical patches under `measurement_governance=on` and
  `record_only`.
- Ablation contract decision: current `record_only` means measurement governance
  OFF, not all governance OFF. It may still expose non-measurement objective
  opportunity, runtime feedback, cross-branch research, branch memory, and source
  visibility. Formal reports must name this scope precisely; causal claims need
  `causal_candidate_pairing=true` or an equivalent pre-registered control.
- Acceptance for this gate: real warehouse shakedown artifacts generated fixed
  candidate manifests for both source arms (`5` candidates, `0` omitted rows
  each) without leaking code body, prompt text, LLM rationale, raw measurement
  diagnostics, BKS/gap, or raw A/A rows. Tests passed: `117` focused
  replay/OFF-contract/report tests, `513` core+report tests, `212`
  config/model/context/protocol/Decision tests, Python compile on touched
  implementation files, and `git diff --check`.
- Accepted: fixed-candidate replay executor. The new `scion report
  fixed-candidate-replay` command materializes recorded candidate patches and
  evaluates identical candidates under `measurement_governance=on` and
  `record_only`, producing a posthoc comparison artifact that is explicitly not
  campaign, scheduler, Decision, lifecycle, or promotion input. Real warehouse
  smoke artifact:
  `/home/clawd/research/scion-experiments/v04-phase5-fixed-candidate-replay-smoke-warehouse-20260612T0508Z-claw/fixed_candidate_replay_comparison.v1.json`.
  The smoke replayed one candidate with `row_count=2`, `error_count=0`, no
  code/prompt/raw-diagnostic/BKS/A/A-row leakage, and `causal_candidate_pairing`
  inherited from the manifest. Both rows completed and failed screening with
  all ties, so the smoke validates replayability and governance-arm pairing,
  not candidate efficacy. Acceptance: replay/report focused suite `22 passed`,
  core/config/context regression `592 passed`, Python compile on touched files,
  and `git diff --check`.
- Full warehouse fixed-candidate replay is complete and audited:
  [`../experiments/v0.4/v04-phase5-warehouse-fixed-candidate-replay-postrun-20260612.md`](../experiments/v0.4/v04-phase5-warehouse-fixed-candidate-replay-postrun-20260612.md).
  It replayed all five ON-shakedown formal screening candidates under `on` and
  `record_only`, producing `row_count=10` and `error_count=0` at
  `/home/clawd/research/scion-experiments/v04-phase5-fixed-candidate-replay-warehouse-5c-20260612T0525Z-claw/fixed_candidate_replay_comparison.v1.json`.
  All paired outcomes were identical. Four candidates stayed all-tie screening
  failures; `f40dd9b672cf6cc2` stayed `SCREENING_EXPAND` in both arms. The
  result validates the fixed-candidate control but does not measure LLM
  trajectory governance value. The next governance gate should examine
  prompt/context/proposal trajectory controls on warehouse rather than rerunning
  fixed-candidate screening.
- Report-only proposal trajectory artifacts are accepted. `scion report
  proposal-trajectory-manifest` now summarizes agentic sessions, LLM trace
  indexes, prompt-manifest block-family accounting, and replayable formal
  candidate joins without embedding raw prompts, raw responses, patch bodies,
  raw metrics, validation/frozen details, or Decision inputs. `scion report
  proposal-trajectory-compare` compares these manifests and marks the result
  `observational_only=true` unless a future explicit control-pair key is
  present. Real warehouse ON/OFF trajectory artifacts are under
  `/home/clawd/research/scion-experiments/v04-phase5-proposal-trajectory-warehouse-onoff-20260612T0550Z-claw/`.
  Report:
  [`../experiments/v0.4/v04-phase5-warehouse-proposal-trajectory-compare-20260612.md`](../experiments/v0.4/v04-phase5-warehouse-proposal-trajectory-compare-20260612.md).
  Both arms had `session_count=10`, `trace_count=32`,
  `formal_candidate_count=5`, and `prompt_manifest_loaded_count=32`; exact
  forbidden-key/value scanning found no raw prompt/response/patch/diagnostic
  leakage. The comparison confirms that same-patch protocol evaluation was not
  the source of ON/OFF divergence; the remaining signal is proposal/context
  trajectory distribution. Next experiment design should separately ablate
  measurement diagnostics and broader research context rather than treating
  `record_only` as all-governance-off.

## Legacy Detailed Snapshot Through 2026-06-07

The detailed handoff below is retained for provenance. It predates the 2026-06-09
audit guide, the 2026-06-10 CVRP/Warehouse 8R comparison, and the 2026-06-11
evidence-uplift roadmap. Use the current snapshot above for present operating
guidance.

The v0.4 architecture-audit remediation tracker is
[`../../reports/architecture-audit-v0.4/remediation-status.md`](../../reports/architecture-audit-v0.4/remediation-status.md).
For post-run analysis, treat R-CORE-001 and R-CORE-002 as terminology/status
alignment findings, not current code-behavior findings. Scheduler selection is
deterministic governance, but it is no longer accurately described as a simple
fixed-priority queue: v0.4 branch routing includes active-slot capacity,
lifecycle-driven same-mechanism follow-up, clean-fork preference, park/reclaim,
and diagnostic repair routing. `--rounds` / `max_rounds` means requested
effective screened/formal candidate budget, tracked through
`effective_rounds_completed` and `counts_toward_max_rounds`; proposal attempts,
protocol evaluated candidates, formal screened candidates, telemetry/validation
repair attempts, lifecycle policy blocks, reconcile lifecycle steps, and
scheduler active-slot blocks are separate counters. Remaining validation is
experiment-analysis validation: the next run report must reconcile
`run_validity`, `campaign_loop.max_rounds_semantics`,
`formal_screened_candidates`, `protocol_evaluated_candidates`,
`non_counted_lifecycle_steps`, and `scheduler_active_slot_blocked_attempts`
before interpreting scheduler choice or candidate quality.

The 2026-05-31 smoke-lineage 8-round local `gpt-5.5` validation completed
cleanly (`8/8`, no quality blocks, no telemetry failed experiments) but showed
a generic branch-lifecycle gap: same-branch follow-ups that regressed from a
weak-positive checkpoint could still leave the branch head classified as
`active_weak_positive`. The repair keeps the v3 boundary intact and does not
add research-object semantics to core. Low-win screening now treats
loss-heavy or non-positive-CI results as quality-regressive instead of weak
positive. Before patching an existing weak-positive branch workspace, Scion
captures a generic filesystem/code-hash checkpoint; if screening later marks
the follow-up as regressed, the checkpoint workspace, patch, code hashes,
mechanism ids, and weak-positive status are restored rather than allowing the
regressed head to be exploited. If restore is unavailable, the branch is marked
`regressed_followup`, which the scheduler routes as diagnostic instead of
`exploit_weak_positive`.

The 2026-05-27 smoke-evidence stopped-run follow-up closes three audit gaps.
CVRP-owned premise gates now ignore negated route-removal missing claims such
as "does not claim whole-route destroy is missing" and do not treat
cross-incumbent route reuse/recombination absence as a claim that route
removal or regret repair is absent; direct claims like "baseline lacks route
removal" still hard-block. Agentic sessions now persist a dedicated
`algorithm_smoke_execution_evidence` artifact and compact transcript reference
for `proposal.algorithm_smoke` case ledgers, while legacy V8 run metric files
carry a versioned runtime case ledger instead of only top-level objective
fields. Stopped runs that complete useful evidence but not the requested round
count remain scientifically valid partial evidence, with
`requested_rounds`, `effective_rounds_completed`, `completed_requested_rounds`,
`interrupted`, `partial_in_flight`, and completeness status exposed in
status/summary `run_validity`.

The 2026-05-27 smoke-runtime evidence follow-up makes algorithm-smoke
representative execution auditable. Runtime smoke now records a per-case
execution ledger for canary, provider-selected representative, and screening
cases, including provider hook metadata, attempted/success/failure state,
runtime audit summary, selected-surface active/error/fallback signals,
elapsed time, and digest hashes. Provider representative cases that are
selected but not executed can no longer silently look like a clean smoke pass.
Prompt manifests now include a tool-result visibility ledger with
observation ids, tool names, payload hashes, visible text char/hash evidence,
and rendered/truncated/omitted flags for context observations. Runtime budget
saturation in proposal smoke remains non-blocking but is surfaced as diagnostic
repair guidance, and same-mechanism branch follow-up policy has direct test
coverage for blocking unrelated mechanism ids.

The 2026-05-27 Rawls premise/runtime follow-up strengthens solver-design
pre-screening. `proposal.algorithm_smoke` now asks the problem-owned smoke
provider for representative cases, so the generic smoke runner can cover both
small and medium/problem-representative inputs without hard-coding CVRP case
semantics. Candidate runtime audit failures such as selected-surface runtime
errors, inactive solver evidence, or fallback-emitted events are surfaced as
`algorithm_smoke_runtime_failure` repair signals before full screening. Missing
activation/effect on rare or conditional mechanisms remains diagnostic rather
than a hard failure.

The later 2026-05-27 grounding/telemetry follow-up fixes two remaining
observability and search-guidance gaps from the local 4-round `gpt-5.5`
analysis. CVRP mechanism novelty still stays in the problem provider, but its
route-removal/regret checks now require a clear missing/absent/lacks/no
existing-mechanism claim before a hard `premise_contradicted` block; hypotheses
that explicitly acknowledge existing whole-route removal or regret repair and
then propose an edge-guided/route-edge-aware repair variant are allowed or
diagnosed instead of hard-blocked. Runtime budget saturation remains
non-blocking, but its diagnostic code is now propagated through protocol
reason codes, decision reason codes, finalizer detail, top-level `status.json`,
in-flight protocol status, metrics, and campaign summary so monitors do not
need to inspect raw metrics.

The 2026-05-27 P1/P2 repair strengthens the v0.4 proposal/evaluation audit
path without adding research-object semantics to the generic core. Hypothesis
acceptance now requires sufficiently complete, API-visible provider-declared
active target-file context before accepting proposals against active algorithm
files, with explicit digest/line-coverage/truncation evidence when the file
cannot be fully shown. Required compact context that the planner omits is now
completed deterministically as `framework_required_completion` before
hypothesis finalization and is distinguished from planner-selected tools and
true fallback paths in traces. Existing-file edit protocol remains strict:
new files may use full-file/create, while existing files must use `modify` with
typed `exact_replace` and `source_digest`. Zero-effect telemetry is exposed as
a non-blocking `telemetry_effect_zero` diagnostic in branch lifecycle/status
signals, and runtime budget saturation is promoted into structured
status/summary diagnostics instead of being visible only as scattered log
warnings.

The 2026-05-26 P0 validity/manifest repair closes an infra-only false-success
gap found in a local `gpt-5.5` 4-round codex-proxy diagnostic. Campaign
`status.json` and `campaign_summary.json` now publish `run_validity` and
`run_validity_status`, distinguishing valid runs from
`invalid_infra_only`, `invalid_no_effective_rounds`, and
`invalid_no_experiments`. Proposal-attempt exhaustion caused only by
provider/proxy/transient API failures such as `no_available_accounts` is no
longer reported as normal scientific completion, even when the outer wrapper
exits cleanly after writing artifacts. API-visible prompt manifests also audit
the rendered provider prompt rather than only generic observation receipts:
dedicated full-file projections, `context.read_surface` nested previews, and
bounded algorithm-slice content are marked visible when their content actually
appears in the rendered prompt.

v0.4 has no known open P0 blocker after the 2026-05-26 local `gpt-5.5`
12-round reconcile/accounting validation. The run confirmed
accounting/headroom/lifecycle core behavior, but exposed P1 research-validity
weakness: all screened experiments tied, with repeated branch-lifecycle blocks,
proposal-quality blocks, typed-edit selector failures, and code-stage object
model/API mistakes. The next recommended step after this repair is another
bounded validation with explicit evidence review, not a generic-core algorithm
change. Scion must remain the v3 framework: generic layers own boundary
control, protocol, lineage, audit, and deterministic decisions; CVRP
objective/solver/ALNS/VNS semantics must enter through the problem package and
adapter/provider hooks, not by hard-coding domain logic into `core`,
`proposal`, `contract`, `protocol`, or `runtime`.

The 2026-05-26 P1 research-validity repair keeps those boundaries intact while
making failures cheaper and more actionable. Code generation now consumes a
generic provider hook for active subject code constraints; the CVRP provider
declares the concrete `ObjectiveValue`, `_Solution`/`_Route`, `__slots__`,
telemetry-helper, and public/internal solution API rules, and generic prompts
render those facts without embedding CVRP semantics. Typed `exact_replace`
failures for non-unique `old_string` values now return structured retry
feedback with match counts, candidate line/column hints, nearby snippets, and
unique-old-string guidance; `replace_all=true` is framed only as an intentional
global replacement. Non-clean branch prompts now state that
`same_mechanism_followup_only` branches must keep protected mechanism ids and
only tune/integrate/repair that mechanism, while the scheduler prefers a clean
fork when capacity exists instead of repeatedly asking a non-clean branch for a
new mechanism. CVRP expected-telemetry preview now distinguishes
activation/budget telemetry from effect telemetry and blocks contradictions
where an incumbent-preserving/no-objective-changing mechanism claims positive
effect fields.

The later 2026-05-26 P1 typed-edit/branch-steering repair closes the
existing-file create/full-file loophole observed after commit `09aa479`.
Hypothesis/target previews now reject `create_new` when the target already
exists, code context exposes the existing target source instead of a new-file
placeholder, and patch normalization rejects `action=create`, `create_new`, or
`full_file` against host-visible existing files with retry guidance that the
file must use `modify` + typed `exact_replace` + `source_digest`. New helper
files can still be full-file creates, but any existing integration file in
`additional_changes` must be a typed edit. Branch steering also now exposes an
explicit `hypothesis_generation_mode=same_mechanism_only` for non-clean
follow-up branches, prefers clean research candidates when at capacity, and
continues to create a clean branch/fork when all active research branches are
same-mechanism follow-up only and proposal capacity exists.

The 2026-05-26 Boyle/Laplace follow-up reworks mechanism novelty from a broad
hard gate into an auditable diagnostic system. Duplicate, near-field, family,
and recent-repeat findings now flow as branch/memory/routing diagnostics unless
there is a narrow high-confidence premise contradiction backed by prompt-visible
adapter facts, fact id, digest/provenance, and an exact contradicted span.
Contract C10 therefore records duplicate diagnostics without blocking ordinary
contract passage. Same-mechanism follow-up branches now expose explicit
allowed/protected mechanism ids to the agent and schema preview rejects
unrelated `mechanism_changes` with retry feedback inside the same session.
Typed `exact_replace` patches are preflighted before parsing/normalization, so
missing or null `new_string` in primary or additional changes becomes precise
schema retry feedback instead of a late normalization failure. Full local
regression after this repair: `2288 passed, 1 skipped`.

The 2026-05-25 repair pass closed the main blockers from the local
`gpt-5.5` 8-attempt diagnostic run and the full v0.4 audit. Suspect telemetry
branches now use a generic repair-first lifecycle: a branch marked
`telemetry_wiring_suspect` must repair the same declared mechanism's
telemetry/wiring/trigger path, or the next new mechanism must fork from a clean
baseline branch. Telemetry repair/diagnostic attempts are counted separately
from ordinary proposal attempts and effective screened rounds, with a bounded
per-branch/per-mechanism repair cap. Telemetry guard semantics now distinguish
activation/evaluation/runtime/effect outcomes, so zero-millisecond runtime is
not by itself treated as missing activation. Generic `contract`/`proposal`
layers now ask provider hooks for active algorithm package paths and entrypoint
rules instead of hard-coding CVRP `baseline_algorithm`/`baseline_modules`
layout, and active solver map facts carry shared digest/provenance for
gate-prompt parity. Model-facing existing-file edits are strict typed edits
with source digests; full-file content remains allowed for creates and explicit
host-internal compatibility only. Full local regression after these changes:
`2237 passed, 1 skipped`.

The follow-up 4-round local `gpt-5.5` validation showed the repair-first path
working for telemetry, but exposed a broader branch-lifecycle policy gap:
`active_no_effect` branches could still accumulate unrelated new mechanisms.
The 2026-05-26 follow-up makes non-clean branches generic
same-mechanism-follow-up branches. Existing no-effect/runtime-regression or
telemetry-suspect branches may be tuned, repaired, or integrated further only
for their recorded mechanism ids; a different new mechanism now requires a
clean fork and is reported as a branch-lifecycle policy block rather than an
effective screened round. Prompt/status projections now expose
`branch_followup_policy`, `clean_fork_policy`, and `branch_mechanism_ids`.
Full local regression after this tightening: `2241 passed, 1 skipped`.

The 2026-05-26 branch-lifecycle reroute repair keeps that boundary strict while
preventing block-only campaign loops. A
`new_mechanism_requires_clean_fork`/branch-lifecycle policy block now marks the
selected non-clean research branch as temporarily ineligible for new-mechanism
proposal selection, records the last block and clean-fork reroute reason in
status/lineage state, and lets the scheduler choose a clean branch/fork when
the remaining research branches are only new-mechanism-ineligible follow-ups.
Same-mechanism follow-up policy remains allowed on non-clean branches; policy
blocks still do not consume ordinary proposal attempts or effective screened
rounds and are not counted as LLM circuit-breaker failures.

The same-day P1 post-reroute repair fixed two launch-blocking validation
explainability issues without changing the research-object algorithm. Default
proposal attempts again include bounded headroom
(`rounds + max(6, 2*rounds)`) unless `--proposal-attempt-limit` or
`SCION_PROPOSAL_ATTEMPT_LIMIT` is set explicitly; `--rounds` remains the
requested effective screened-round target, not the proposal-attempt target.
Generic proposal/runtime identity paths no longer hard-code CVRP solver phase,
module, or counter names for telemetry identity, retry activation refs,
mechanism-family broadness, plateau target examples, or runtime audit
classification. Those names are declared by the active CVRP provider/subject
taxonomy and consumed as provider facts by generic Scion.

The subsequent local `gpt-5.5` 8-round provider-taxonomy run completed with
`max_rounds_exhausted`, no P0/P1 findings, provider taxonomy and branch
lifecycle reroute behavior intact, and proposal-attempt headroom remaining.
It exposed one P2 accounting/reporting issue: a stale `reconcile` abort with
`missing hypothesis metadata for reconcile` was status-counted as an effective
round even though no formal protocol result or DB experiment row existed. The
repair classifies reconcile lifecycle aborts as non-counted
`reconcile_lifecycle` steps, keeps them out of proposal-attempt and effective
round counters, and mirrors `reconcile_lifecycle_steps` plus
`non_counted_lifecycle_steps` in status/summary. Summary now also exposes
`counted_experiment_steps` so report consumers can compare formal counted rows
against loop counters directly. Full local regression after this repair:
`2255 passed, 1 skipped`.

The 2026-05-24 LLM transport repair enables local Codex subscription-backed
experiments through `codex-proxy` without changing Scion's proposal/session
boundary. Current real-cost experiments should be launched with explicit local
environment variables: `SCION_MODEL=gpt-5.5`,
`SCION_BASE_URL=http://127.0.0.1:8080`, and the local `SCION_API_KEY`. Do not
set `SCION_REASONING_EFFORT` for routine short experiments; the current goal is
fast framework feedback, not maximum model deliberation. The transport still
supports explicit GPT/Codex reasoning efforts (`low`, `medium`, `high`,
`xhigh`) for targeted diagnostics, while DeepSeek keeps its existing
`xhigh -> max` normalization and `extra_body.thinking` behavior. Scion also
records codex-proxy/OpenAI-compatible usage fields from
`prompt_tokens_details.cached_tokens` and
`completion_tokens_details.reasoning_tokens`. The direct `/v1/responses` route
remains a future opt-in transport, not the default.

The 2026-05-24 P0 APS control repair addresses the latest gate/budget audit
without relaxing v3 boundary control. Default campaign proposal attempts now
include repair headroom (`rounds + max(6, 2*rounds)`) instead of equaling the
requested screened-round count, so pre-screen grounding or preview repairs no
longer starve a short campaign immediately. `status.json` now receives
best-effort pre-protocol progress for hypothesis generation, code generation,
patch contract, workspace setup, patch apply, verification, and evaluation
dispatch, and canary runs emit pair-level progress before formal screening.
Proposal-time algorithm smoke now treats activation/effect/activity/runtime
telemetry that is merely unobserved in the tiny smoke sample as a diagnostic
signal rather than a hard code-generation failure; real runtime errors,
runtime audit failures, protected telemetry failures, schema failures, and
contract failures still fail closed. The same repair adds protocol heartbeat
detail down to child process id, child phase, current case, and seed, and
records those fields in `status.json` while preserving public-ref redaction.
Heartbeat state is stage-scoped: canary/screening transitions refresh
`complete` and pair counts from the current metrics snapshot, clear prior
stage child-process fields, and remove `child_pid` once a protocol stage is
complete so `status.json` does not report a dead solver subprocess as live.
The solver-design planner loop now also stops or falls back when the model
reselects a required context tool already completed by the deterministic
preface; this prevents repeated `context.read_active_solver_design` tool
selection from consuming dozens of LLM calls without new observations.
Mechanism novelty/premise gates now enforce gate-prompt parity: if a gate would
reject using an adapter-owned active fact packet that was not included in the
API-visible hypothesis prompt with the same digest, Scion retries with that
packet visible instead of blaming the agent. Telemetry repair guidance now
explicitly directs code agents to record real branch-point activation and real
effect/runtime deltas, while forbidding fake activation counters, forced rare
branches, `max(..., 1)` counter padding, or telemetry-only fallback behavior.
Follow-up validation found two remaining over-control risks and they are now
covered by regression tests: CVRP random-removal premise checks must ignore
no-op/fallback prose that merely says a new mechanism falls back to existing
`_random_removal`, and CVRP acceptance/reheat broad-loop effect telemetry is
now adapter advisory guidance rather than a hypothesis-stage hard rejection.
Core schema/contract violations remain hard; this only downgrades the
problem-adapter warning that an indirect policy should prefer decision,
activation, or budget telemetry.
The telemetry-diagnostic branch lifecycle is also stricter about preserving
research continuity: branch-local activation/effect/activity diagnostics are
kept as same-branch repair signals even when the first screened attempt also
has poor win-rate, negative objective movement, or runtime slowdown. A branch
can still be soft-abandoned after repeated identical telemetry diagnostics, or
when the candidate has runtime/crash failures or non-repairable protected
telemetry failures.
The latest P0 follow-up closes the remaining static-smoke hard-block: static
telemetry preview now separates hard failures from diagnostics. Invalid context
telemetry helper signatures and literal zero/non-positive phase runtime records
still fail closed, but missing activation/effect/runtime wiring or missing
positive delta evidence is returned as `diagnostic` with precise required-call
feedback. Algorithm smoke now continues to runtime smoke after such diagnostics
so real crashes or illegal runtime behavior are still caught, while code
generation is no longer forced through repeated LLM repair attempts just to
manufacture telemetry.

The 2026-05-22 stopped-run analysis is
[`v0.4-v3-static-smoke-line-split-sonnet-3r-stopped-analysis-20260522.md`](../experiments/v0.4/v0.4-v3-static-smoke-line-split-sonnet-3r-stopped-analysis-20260522.md).
It found framework observability gaps rather than a v3 boundary breach: an
in-flight APS session could be interrupted by campaign SIGTERM after writing a
prompt manifest but before writing `output.json`, `transcript.json`, or an
index row; partial `hypothesis_awaiting_approval` sessions were summarized like
contract failures; failed session index rows hid the useful failure/hypothesis
summary fields; and generic telemetry guard wording collapsed present-but-zero
activity into "not observed." The current repair keeps these fixes generic:
APS now persists and indexes `campaign_abort` failed stubs before re-raising
`KeyboardInterrupt`, session index rows preserve failure detail plus compact
surface/action/target/mechanism summaries, awaiting approval no longer receives
`contract_boundary_failure`, and activity telemetry now distinguishes missing
fields from declared fields present in all candidate runs but all zero.

The follow-up 3-round run reached one formal screening round and then stopped
on upstream provider balance exhaustion; post-run trace analysis is
[`v0.4-v3-abort-telemetry-audit-sonnet-3r-postrun-20260522.md`](../experiments/v0.4/v0.4-v3-abort-telemetry-audit-sonnet-3r-postrun-20260522.md).
The repair keeps the v3 boundary generic: LLM transport now classifies 403
insufficient-balance errors before transient-provider retries, and balance
exhaustion now requests a campaign stop immediately instead of waiting for the
circuit breaker threshold; agentic
`primary_failure` attribution now preserves explicit runtime categories such
as `llm_transient_api_error` ahead of default self-check/schema fallbacks; and
telemetry guard mechanism diagnostics now mirror declared field-level
failures, so a mechanism cannot appear `passed=true` when an explicit
declared field for that mechanism failed formal guard validation. The same
pass split `ContractGate` hypothesis/mechanism-binding checks into
`contract/hypothesis_checks.py` and moved telemetry mechanism-diagnostic tests
into a focused test file. Full unit regression passes (`1016 passed`).
The immediate validation run is
[`v0.4-v3-balance-fatalstop-sonnet-3r-stopped-20260522.md`](../experiments/v0.4/v0.4-v3-balance-fatalstop-sonnet-3r-stopped-20260522.md):
the provider still returned 403 balance errors, but Scion stopped after one
proposal attempt with `circuit_breaker_tripped=false`, confirming the fatal-stop
behavior.

The former code-phase protocol gap is now closed for existing-file modifies:
model-facing code generation must submit typed `exact_replace` edits for
host-visible existing files while Scion canonicalizes to full after-content
before Contract, Verification, Protocol, Workspace, and Decision. Full-file
model output (`edit_intent=full_file`, `content_after`, or legacy
`code_content`) is rejected on final raw patch parsing for existing modifies,
and whole-file `exact_replace` is also rejected as an equivalent full-file
rewrite. `full_file` remains allowed for creates/deletes and host-internal
canonical `PatchProposal.code_content` remains valid after parsing. Unified
diff input remains deferred. This stays problem-agnostic in core; problem
packages may only validate problem-specific patch semantics through declared
hooks.

The 2026-05-23 APS context/tooling repair addresses the two deferred issues from
the current-resume Sonnet validation. The active-solver file-read guard is no
longer a fixed file-count cutoff: it now uses a target/role/call-graph-aware
policy where the selected target and direct integration context remain readable,
and inherited `already_observed` receipts do not consume the bulky-read budget.
Hypothesis and code remain separate APS requests for v3 boundary control, but
their handoff now includes an audit-safe observation ledger keyed by source
path, digest, coverage, evidence reference, active-facts digest, branch code
hash, and champion snapshot. The code phase can reuse unchanged hypothesis-stage
observations through compact read receipts and perform fresh reads only when it
needs more source coverage. The repair is generic Scion infrastructure; problem
packages still supply active object facts and manifests through adapter/provider
hooks. Full unit regression for this pass is `1022 passed`; live validation is
pending.

The 2026-05-23 branch-lifecycle/diagnostic pass changes formal telemetry guard
activation/effect misses and branch-local activity all-zero failures from
one-shot abandon triggers into diagnostic repair signals.
`SCREENING_TELEMETRY_FAILED` remains available for non-repairable guard
failures, but activation-missing, effect-zero/missing, and
`TELEMETRY_ACTIVITY_FIELD_ALL_ZERO` codes now route through
`CONTINUE_EXPLORE` or `VALIDATION_REPAIR_REQUIRED` with
telemetry-diagnostic lifecycle reasons. The lifecycle policy can still
soft-abandon after repeated identical diagnostics or when the candidate also
shows clear runtime/quality regression, candidate runtime failure,
frozen/protected telemetry failure, schema/contract failure, or other severe
constraint risk. Mixed guard failures are repairable only when every failing
detail is branch-local diagnostic, so protected/objective/budget telemetry still
fails closed. This keeps Scion core problem-agnostic: the guard only consumes
adapter/provider-declared telemetry roles and never reads CVRP solver semantics
directly. APS development budgets were also relaxed without removing audit
boundaries: default tool/observation/time/code-attempt caps are higher,
proposal-quality attempts now allow deeper pre-screen repair, and mandatory
target/surface reads can borrow observation reserve so read receipts or
necessary target inspection do not prematurely exhaust the code phase.

The 2026-05-23 APS integration repair closes the short-experiment P0 where
contract preview validated a follow-up branch patch against the original CVRP
package instead of the branch-current workspace. Problem preview hooks now
receive a generic `base_workspace`; the CVRP provider materializes a temporary
candidate policy workspace from the current branch, applies the primary patch
plus same-patch `additional_changes`, and imports through the runtime-style
top-level `policies.*` module graph. `proposal.algorithm_smoke` also prefers
the branch workspace before falling back to champion/root snapshots. Regression
tests cover a branch-local `_noise_greedy_repair` imported by a later
`scheduler.py` patch and a same-patch helper module import.

The same repair pass also turns prompt accounting from raw-context accounting
into provider-visible prompt accounting. Prompt manifests now record rendered
`system_blocks + user_prompt` character counts, section projection, and prompt
hash; raw `prompt_context` is retained only as an audit digest and is not
reported as API-visible text. `agentic_resume_context` is now rendered as a
bounded model-facing handoff with previous failure summary, active-fact digest,
read receipts, file digests, tool-step summary, and patch summary. Raw active
facts are deduplicated from tool observations so the model sees the full active
fact packet once, before lower-priority observations.

The 2026-05-23 validation run
`v04-v3-attempt-bound-telemetry-feedback-sonnet-3r-20260523T115407Z` was stopped
after confirming the typed-edit protocol had only partially landed: response
traces no longer used legacy `code_content`, but a later code session still
submitted `edit_intent=full_file` with 14k-18k `content_after` for an existing
`local_search.py` modify. The follow-up repair moves the rule from prompt
guidance into the host edit protocol, preserves actionable retry feedback, and
updates the test fixtures to use typed edits where they simulate raw LLM code
output. Full unit regression for this pass is `1062 passed`.

The fresh short validation run
`v04-v3-hard-edit-protocol-sonnet-3r-20260523T130427Z` confirmed the code-edit
protocol behavior but did not produce a screened candidate. Five proposal
attempts were consumed by quality gates (`algorithm_smoke_failure`,
`premise_contradicted`, and `duplicate_mechanism`), with zero screened
experiments. The edit-protocol acceptance criteria passed: every host-visible
existing-file modify in raw code traces used `edit_intent=exact_replace` with
`content_after=0` and `code_content=0`; `full_file` appeared only for
`action=create` on a new `elite_pool.py` module, and same-patch integration
changes to existing `scheduler.py` were typed `exact_replace`. Next work should
focus on agent hypothesis quality and smoke-repair feedback rather than the
full-file output protocol.

`06-code-edit-protocol-reference-claude-code.md` is now partially implemented
in the live code path. Code generation still normalizes into canonical
full-file `PatchProposal` content before Contract, Verification, Workspace, and
Decision, but the model-facing protocol can submit typed edits. The first
supported intents are `exact_replace` and `full_file`; `exact_replace` requires
the source digest and exact replacement strings, while Scion host derives the
`content_after` body and compact audit diff metadata. Full-file output remains
as a compatibility fallback for creates, deletes, and complex rewrites.
Unified diff input is still deferred; host-generated diffs remain the canonical
audit direction.

The 2026-05-23 APS code-edit host repair canonicalizes repeated file paths
inside one patch set before schema validation. Multiple same-file
`exact_replace` typed edits are applied in order against the evolving host
source and collapsed into one canonical file change with `repair_attribution`
composition metadata, including the case where the top-level target and
`additional_changes` touch the same file. Conflicting repeated `full_file`
entries, mixed create/delete sequences, or non-serializable `exact_replace`
edits now fail with a short structured protocol error instead of falling into
the old duplicate-file-path schema retry loop.

The follow-up 2026-05-23 P0 repair separates markdown display blocks from the
patch/edit raw-source map. `target_file_code`, `original_code`, integration
file blocks, and preview source reads now feed raw Python content into
`build_patch_edit_source_manifest`, `_parse_patch`, contract preview, and
algorithm smoke typed-edit expansion; markdown wrappers such as
`File: path` plus a Python code fence are no longer hashed or written to canonical
`code_content`. C6 syntax failures now include a compact `source_excerpt` so a
future wrapper regression is visible to the code agent without exposing large
file bodies.

The same-day APS prompt repair reduces solver-design full-file pressure without
changing the host normalizer. Solver-design code prompts no longer ask agents to
return complete target-module contents; existing `modify` actions now default to
typed `exact_replace`, while `full_file` is framed as create/delete or a
justified larger rewrite with `full_file_reason`. Retry prompts now render a
compact previous-patch summary: file/action/intent metadata, old/new snippets,
audit refs, and content digests/lengths, with host-normalized `code_content` and
`content_after` bodies omitted from the model-facing retry context.

The immediate typed-edit validation run
`v04-v3-typed-source-prompt-sonnet-3r-20260523T112046Z` was stopped manually
after it reached the configured short-run boundary. It confirmed the P0 C6
wrapper failure was gone and all observed code responses used typed
`exact_replace` rather than model-emitted full files. The run exposed three
follow-up framework issues now repaired generically: proposal attempts and
effective screened rounds are separately bounded and reported; solver-design
`context.read_algorithm_file` budgeting is active-object/target/role aware
instead of a fixed file-count cutoff, so scheduler/state/config and manifest
files are not blocked before the agent understands the algorithm object; and
algorithm-smoke telemetry failures now carry actionable repair payloads with
the failing mechanism id, exact `context.record_move(..., delta=..., best_improved=...)`
effect pattern, invalid-call summaries, and the alternative of correcting the
telemetry declaration when a mechanism only intends activity/activation.

As part of this repair, `scion.proposal.schemas` was split from a single
near-1000-line module into a package facade with focused hypothesis, patch,
tool, shared, and normalization modules. The public import path
`from scion.proposal.schemas import ...` remains compatible. Post-repair
validation passed `python -m compileall -q scion/scion`, full unit regression
`1039 passed in 208.79s`, and the proposal/CVRP preview non-unit suite
`105 passed in 0.95s`. Live short-experiment validation is still pending.

The 2026-05-20 active-algorithm-facts repair closes the P0 gap exposed by the
latest 4-round branch-lifecycle experiment. `active_solver_snapshot.py` is now
a generic facade over adapter-provided snapshots; the CVRP active solver facts
live in `problems/cvrp/active_solver_facts.py` and enter Scion through
`CvrpAdapter.active_solver_design_provider()`. APS now extracts the same
adapter fact packet into `agentic_active_algorithm_facts`, renders it as a
separate high-signal prompt block before raw tool observations, and records the
packet digest/provenance in the prompt manifest. Semantic novelty/premise
checks may reject only against that agent-visible fact packet and include fact
ids plus digest/provenance in the rejection. Proposal-smoke activation-missing
results are classified as `proposal_activation_diagnostic` so they can guide
repair and branch lifecycle without being counted as ordinary solver-quality
screening losses. Focused regressions for this repair pass (`151 passed`);
short live validation is pending.

The first 3-round live validation of that repair was stopped early after one
screened branch because proposal attempts repeatedly hit pre-screen novelty and
contract failures. Post-run trace analysis is
[`v0.4-active-facts-control-sonnet-3r-stopped-analysis-20260520.md`](../experiments/v0.4/v0.4-active-facts-control-sonnet-3r-stopped-analysis-20260520.md).
The follow-up repair keeps planner/tool-selection grounded with an active-facts
anchor, removes prompt-only `acceptance_strategy` fields from generic repeated
mechanism identity, expands CVRP adapter facts for `_or_opt_1`, route removal,
and regret repair, and fixes failure lifecycle routing so proposal/contract
quality failures do not escalate to infra and failure streaks are branch-local.
The full unit regression for this follow-up repair passes (`902 passed`).

The next 3-round validation attempt was stopped before code generation after
three proposal attempts. Trace analysis is
[`v0.4-grounding-routing-repair-sonnet-3r-stopped-analysis-20260520.md`](../experiments/v0.4/v0.4-grounding-routing-repair-sonnet-3r-stopped-analysis-20260520.md).
It showed the new active-facts anchor was present, but the CVRP fact packet
still missed `_two_opt_intra`; the CVRP Or-opt premise rule misclassified an
intra-2opt contrast as an Or-opt contradiction; generic repeated-history
matching used broad `ALNS+VNS` identity; and agent-quality-block feedback was
not hard enough as a branch-local next-hypothesis constraint. The current
repair keeps the fix split along v3 boundaries: generic proposal pipeline
persists quality blocks into the next hypothesis context, generic repeated
identity no longer blocks distinct concrete mechanism ids via broad families,
and CVRP-owned adapter/provider facts now expose `_two_opt_intra`, relocate,
swap, and the full VNS registry with corresponding duplicate/premise checks.
The full unit regression for this repair passes (`907 passed`).

The follow-up 3-round live validation is documented in
[`v0.4-quality-feedback-vns-facts-sonnet-3r-analysis-20260520.md`](../experiments/v0.4/v0.4-quality-feedback-vns-facts-sonnet-3r-analysis-20260520.md).
It reached three counted formal screening rounds and one repairable telemetry
screening, with `proposal_attempts=7` and no hidden-gate facts mismatch:
agent-visible active facts and novelty/provider gates used the same
digest/provenance. The remaining P0 gaps were control-quality issues rather
than CVRP semantics in Scion core: some code-phase tool-selection prompts still
lacked active-facts anchors, uncounted proposal failures were not compactly
promoted into later hypothesis context, smoke/telemetry failures lacked
path-level repair evidence, and CVRP-owned premise gates overmatched allowed
variants of existing mechanisms.

The first quality-feedback P0 repair kept those fixes on the v3 boundary.
Generic APS now
anchors every tool-selection prompt with the adapter-owned active-facts
digest/provenance, renders uncounted proposal failures as compact branch-local
negative memory, and preserves provider fields such as `variant_allowed`,
`contradicted_span`, `matched_span`, and `allowed_variant_guidance` in
agent-quality feedback. CVRP-specific span matching and allowed-variant
semantics remain inside `problems/cvrp/mechanism_novelty/*`; feasible
route-merge construction variants and destroy operators that use the existing
regret repair portfolio are no longer escalated to false premise
contradictions. Focused regressions pass (`110 passed`) and the full unit suite
passes (`914 passed`).

The follow-up 3-round validation is documented in
[`v0.4-provenance-quality-feedback-sonnet-3r-analysis-20260520.md`](../experiments/v0.4/v0.4-provenance-quality-feedback-sonnet-3r-analysis-20260520.md).
It confirmed provenance anchoring and uncounted negative memory were mostly
working, but exposed two remaining P0 gaps: provider-quality blocks could still
persist as `hypothesis_contract` / branch `CONTRACT`, and CVRP provider premise
checks still overmatched adaptive VNS neighborhood ordering and allowed
Shaw/related-removal variants.

The current P0 repair closes those gaps without moving CVRP semantics into
Scion core. Generic proposal pipeline code now keeps provider/diagnostic
quality rejections as agent-quality through StepRecord, branch failure codes,
and planner-facing experiment history. The same compact labels used by
negative memory, for example
`agent_quality_blocked:proposal_premise_contradicted`, are rendered in
experiment history, and activation diagnostics carry session, branch,
mechanism, digest, and provenance into later same-branch hypothesis context.
CVRP-owned novelty/premise providers now require exact `contradicted_span` or
`matched_span` for `premise_contradicted`; missing spans downgrade to
duplicate/novelty guidance. Adaptive neighborhood ordering is not classified as
missing intra-2opt unless the proposal explicitly claims 2-opt/reversal absence,
and Shaw/related-removal trigger, scoring, schedule, or filtering variants are
allowed variants rather than premise contradictions. Related regressions pass
(`134 passed`) and the full unit suite passes (`921 passed`). Next step: run a
4-round Sonnet validation focused on classification persistence, provider span
feedback, and branch-continuation behavior before considering a longer 6-round
run.

A 4-round validation launch after this repair stopped before any counted
screening because the upstream LLM provider returned 403 insufficient-balance
errors. That run is documented in
[`v0.4-provider-quality-classification-sonnet-4r-balance-stopped-20260520.md`](../experiments/v0.4/v0.4-provider-quality-classification-sonnet-4r-balance-stopped-20260520.md).
It confirms run-level provider/balance classification did not pollute
StepRecord or branch failure codes, but it does not validate the P0 repair.
After recharge, rerun the same 4-round validation before moving to 6 rounds.

The 2026-05-20 branch-lifecycle repair aligns the live scheduler with v3 §11.
Low-win screening no longer means immediate single-round T4 abandon. Generic
`core.branch_lifecycle_policy` classifies low-signal screening as weak-positive,
neutral, zero-streak exhausted, or clearly regressive using only structured
`DecisionFeatures` (`wins/losses/ties`, median delta, runtime summary, telemetry
guard state). Weak-positive and mostly-tie branches preserve their workspace and
patch for same-branch follow-up; clear losses, negative delta, major runtime
slowdown, or exhausted zero-win streaks still soft-abandon. Scheduler behavior
now supports an actual branch portfolio: protocol continuations and retries
remain higher priority, but established ordinary explore branches no longer
block sibling branch creation while capacity remains, and full research
portfolios rotate by oldest `updated_at`. This preserves Scion's deterministic
control boundary while letting the proposal agent iteratively improve weak
branches instead of restarting from champion every round.

The same repair removes a telemetry-noise source: runtime field container names
such as `solver_algorithm_phase_runtime_ms` are no longer normalized into fake
mechanism ids. Mechanism-specific runtime attribution such as
`solver_algorithm_phase_runtime_ms.<mechanism_id>` remains valid when attached
to a declared mechanism.

The 2026-05-19 large-file audit is
[`08-large-file-modularization-audit-20260519.md`](../reviews/scion-code-audit-20260517/08-large-file-modularization-audit-20260519.md).
Roughly 800 lines is a design warning, not a mechanical hard limit: files above
it need ownership and a split plan; files above 1000 lines are active
architecture debt; files above 3000 lines require stop-the-line attention or an
assigned migration owner. Test files follow the same rule.

The first P0 modularization repair is complete for APS. `agentic_session.py`
is now a 17-line compatibility facade; session orchestration, hypothesis and
planner phases, code tools, preview/repair, tool calls, budget/runtime,
observations, outputs, and persistence are in focused `agentic_session_*`
modules. The former 4k-line `test_agentic_proposal_tools_session.py` file is
split into focused `test_agentic_session_*.py` files. Focused APS session tests
pass, and the broader APS/tool focused regression passes (`143 passed`). This
closes the APS P0 blocker, but it does not lift the
broader experiment freeze. The first CVRP test-side cleanup is also complete:
the former 4.8k-line `tests/test_cvrp_solver_operator_runtime.py` aggregate is
now a placeholder, shared fixtures live in `cvrp_solver_runtime_support.py`,
and focused `test_cvrp_*_runtime.py` files pass (`72 passed`). Remaining P0/P1
blockers include `problems/cvrp/solver.py`, `problems/cvrp/adapter.py`,
`proposal/context_manager.py`, and the CVRP-owned solver-design integration
provider. The first production solver slices have started:
low-coupling policy-module loading, solution/objective helpers, timing helpers,
operator-registry runtime, and neighborhood-portfolio runtime now live under
the CVRP-owned `problems/cvrp/solver_runtime/` package while `solver.py`
remains the public facade. This is verified but not sufficient; `solver.py` is
still above 8000 lines and remains the main P0 production blocker.

The 2026-05-19 design-first modularization repair is now complete for two
framework hot spots. `proposal/tools/preview.py` is a small compatibility
facade backed by focused `proposal/tools/previews/*` modules for schema,
permission, contract, algorithm-smoke, telemetry-static, and smoke-feedback
payloads. `contract/gate.py` is back below the preferred threshold and now
orchestrates C1-C12 while target/path, security, static-risk, novelty,
telemetry, surface-access, patch-path, and result-payload logic live in focused
contract modules. This is responsibility split work, not just helper
extraction. It does not close all contract/provider debt:
the generic `contract/checks/solver_design_integration.py` is now a thin hook
dispatcher, but the migrated CVRP-owned provider remains large and needs
problem-package modularization.

The latest audit-driven repair moved candidate-flow CVRP semantics back behind
problem-owned hooks. `proposal.mechanism_novelty` is now a generic dispatch and
rejection-shape module; the CVRP checks for construction seed strategy,
adaptive weights, cross-route Or-opt, and Shaw related removal live under
`problems/cvrp/mechanism_novelty.py` and are exposed through
`CvrpAdapter.mechanism_novelty_provider()`. Campaign stagnation no longer
hard-codes CVRP object-model strings in `core/stagnation.py`; problem adapters
may provide `stagnation_object_model_markers()`. The CVRP solver runtime split
also now has a shared `solver_runtime/constants.py`, and `solver_runtime/*.py`
is explicitly frozen in both CVRP problem specs. This closes the highest-risk
candidate-flow leakage found in the post-split code audit, but the broader
provider migration remains open for `proposal/engine.py`,
`proposal/context_manager.py`, `proposal/solver_design_smoke.py`, the
CVRP-owned solver-design integration provider, and protocol/runtime telemetry
dispatch.

The context-manager split has completed two behavior-preserving slices. Generic
research-surface and adapter context construction lives under
`proposal/context_builders/`, and feedback/history/memory rendering lives in
`proposal/context_builders/feedback_memory.py`. `proposal/context_manager.py`
is still above 2700 lines and remains active architecture debt. The next slices
should move active-solver/code-read context, budget/compaction, and
problem-specific solver-design guidance behind focused builder/provider
modules without mixing CVRP terms into Scion framework code.

The broader test-side architecture cleanup is now complete. All previously
oversized aggregate test files have been converted to placeholders plus
focused sibling modules with shared `*_test_support.py` helpers. The largest
remaining test file is 728 lines, below the preferred 800-line threshold.
Focused split regressions passed (`643 passed`), and the CVRP
runtime/adapter/agentic-tool split regression passed (`192 passed`). Future
regressions should land in the focused owner file rather than recreating an
aggregate sprint/test bucket.

Before this P0 shift, the framework governance path was largely behaving, but
the previous CVRP optimization path was still too componentized: Scion could
select `solver_design`, yet generated candidates mostly filled a
`main_search_plan` lifecycle table and optimized exposed knobs rather than
studying the algorithm itself.

The 2026-05-17 v3-aligned design repair keeps that interpretation explicit:
Scion is the boundary/protocol/audit framework, while the proposal agent must
be able to study and modify the branch-owned algorithm body inside the declared
problem boundary. `proposal.tools` is now a package (`registry`, `context`,
`surface`, `feedback`, `preview`, `models`, `base`, `utils`) instead of a
single long module, so tool registration and future tool expansion have a
clear home while preserving `from scion.proposal.tools import ...`
compatibility. ContractGate is now the authoritative fail-closed layer for
solver-design boundary rules that previously lived only in prompts or APS
preview: dynamic sensitive API forms, reflective instance identity leaks, dead
helper references, and preferred `baseline_algorithm.py` calls to
`context.baseline(...)` are rejected statically. Code-phase APS now treats the
full selected-surface read as mandatory, filters feedback to the active
single-surface problem boundary, and provides branch-current integration files
for solver-design `additional_changes` so candidates wire the current branch
algorithm instead of rewriting scheduler from stale or missing context.

The follow-up control-closure repair addresses the remaining audit and
experiment-loop gaps before the next live run. Non-scheduler primary
solver-design patches may no longer use `additional_changes` to rewrite
`scheduler.py`'s `_ALNSVNSSolver.solve` loop; those edits are limited to
import/operator registration wiring unless `scheduler.py` is the approved
target. Pending code retries are now marked as retry attempts and do not
advance campaign `total_rounds`, idle-round accounting, or the outer
`max_rounds` budget. The `solver_algorithm` compatibility surface is
normalized to `solver_design` for runtime audit, protocol execution, and
algorithm smoke. Generic protocol runtime summaries now include
`solver_algorithm_*` telemetry, champion-side process/audit failures emit
progress updates, and smoke payloads record resolved case paths/data-root
provenance. The old intermediate APS split, where the session class remained a
large orchestrator with a few helper modules, is superseded by the 2026-05-19
facade/module split described above.

The 2026-05-18 P2 agentic-control repair closes the latest APS control-loop
regressions under the v3 boundary model. `expected_telemetry` now teaches and
enforces category keys (`activity`, `activation`, `effect`, `budget`) separately
from runtime field paths. APS session wall-time timeouts are recorded as
`session_timeout` / `agentic_budget_control` skip evidence rather than
`runtime_exception/tool_error`, and code repair checks wall-time reserve before
requesting another code LLM call. Core routing treats deterministic APS control
timeouts as framework-control fail-closed and treats `algorithm_smoke_failure`
as candidate-scoped `agent_quality_blocked`, not generic `PROPOSAL` or
`infra_suspected`.

The accepted follow-up Sonnet 3-round validation is
[`v0.4-p2-agentic-control-validation-sonnet-3r-20260518.md`](../experiments/v0.4/v0.4-p2-agentic-control-validation-sonnet-3r-20260518.md).
It produced one formal screening candidate and two healthy algorithm-smoke
quality blocks. No session-timeout misclassification, terminal-preview skip,
budget-control skip, `runtime_exception/tool_error`, or `infra_suspected`
regression appeared. This is framework-control evidence only; it is not solver
quality evidence and does not justify champion promotion.

The current repair changes the active CVRP research object. `solver_design`
now targets a branch-owned solver-design package: stable entrypoint
`policies/baseline_algorithm.py::solve(...)` plus focused algorithm modules
under `policies/baseline_modules/*.py`. When `solver_design` is the selected
surface, candidate and champion subprocesses run that copied branch entrypoint,
which imports the branch-owned modules. When another component surface is
selected, runtime skips this full-algorithm subject so legacy component tests
remain isolated. Candidates should study and modify the branch copy of the
algorithm modules; `policies/solver_algorithm.py` remains as a compatibility
hook only. APS `context.read_surface` now includes bounded support-module
previews for `solver_design`, so hypothesis and code phases can inspect the
actual algorithm internals rather than only the stable entrypoint. For module
targets, code-phase reads now keep the selected target narrow but also include
prioritized support artifacts for `state.py`, the stable entrypoint, and
sibling algorithm modules, with compact `python_api_summary` entries. This is
required because the branch-owned solver uses `_Solution.routes` as `_Route`
objects, not `list[list[int]]`; the code agent must see that object model
before editing scheduler or local-search logic. Algorithm-smoke retry feedback
now preserves concrete runtime/audit details such as failing case,
`solver_algorithm_errors`, and compact `solver_algorithm_events` instead of
only a generic failure code. Code-phase reads of a specific
`policies/baseline_modules/*.py` target are narrowed to a target-only preview
with a 6000-character code cap, preventing repeated module reads from
consuming the terminal Contract/smoke reserve. The adapter and solver keep
ownership of objective semantics,
feasibility, parsing, seeds, protocol splits, time limits, and Decision rules.
Runtime evidence for this boundary remains `solver_algorithm_*`, including
selected path, phase runtime, movement telemetry, and recomputed objective
fields.

The latest 2-round object-context smoke validated the new code-stage context:
LLM traces contained `support_artifacts` and `python_api_summary` for
`baseline_modules/state.py` when the target was `scheduler.py`. It also exposed
a Contract nuance: complete scheduler replacements inherited an existing
baseline exception message that referenced `instance.name`, and C9d treated it
as a new case-specific branch. Contract preview is now champion-snapshot aware
for C9d: exact inherited statement-level identity uses are not blockers, while
new `instance.name` branches remain forbidden. The follow-up smoke advanced
past that Contract blocker and failed in algorithm smoke; code-repair context
now carries the algorithm-smoke observation itself, with compact
`solver_algorithm_events`/stderr/run detail preferred over the generic
`solver_algorithm_errors=1` summary.

The follow-up 6-round module-object smoke showed the next control gap. APS
preview was champion-snapshot aware, but the main campaign `ContractGate` was
not, so completed scheduler candidates could still fail main `patch_contract`
on inherited `instance.name` text. That is now repaired with a dynamic champion
snapshot provider on the campaign gate. Solver-design code prompts now require
the primary JSON `file_path` to match the approved `target_file`, with
entrypoint/scheduler/module wiring in `additional_changes`; package-relative
imports inside `policies` are required. Contract also rejects inert
solver-design helper additions through `C9e_solver_design_integration`: new
module-level helper functions must be statically called from an existing
solver path in the same candidate patch.
The immediate 2-round validation after this repair produced two real screening
experiments, both normal algorithm-quality abandons rather than framework gate
failures: scheduler ensemble construction tied the champion with a small
runtime tie-speedup below the promotion threshold, while local-search
round-robin VNS worsened quality and slowed runtime.

The latest 6-round contract-integration validation showed that the framework
path is mostly healthy but C9e was too narrow for class-based solver modules.
Only three candidates entered screening because rounds 1 and 6 were falsely
rejected before screening: their new helpers were called from solver class
methods or a runtime `_ALNSVNSSolver = _PBIGSolver` alias, but C9e only
recognized module-level entrypoint/function reachability. Round 2 was a real
generated-code error with a repeated keyword argument that C6 should have
caught earlier. Repair: C6 now compiles parsed patch code, and C9e now treats
the runtime solver class `solve(...)` call chain as a valid integration root
while still rejecting helpers reachable only from detached classes. C9e was
also extracted from the monolithic `ContractGate` file into
`contract/checks/solver_design_integration.py`.

The follow-up Sonnet/Opus 6-round integration smokes confirmed a different
code-stage repairability gap. Screened candidates were correctly abandoned for
solver quality, including faster but objectively worse scheduler rewrites. The
pre-screen failures were mostly recoverable: `additional_changes` emitted as a
JSON string, inert helper-only local-search edits without scheduler/entrypoint
integration, and branch solver object-model mistakes such as `_Solution._instance`
or calling `.distance` on an integer. Current repair keeps the same
solver-design boundary but makes code-stage feedback deeper: schema parsing
tolerates JSON-string `additional_changes`, C9e reports inert helpers and
recognized roots, algorithm-smoke returns targeted repair guidance, and a
tainted non-promotional candidate-vs-champion canary micro-benchmark blocks
only candidates that lose every comparable smoke case before formal screening.
Repeated recent `solver_design` `win_rate=0` screening failures now produce
plateau guidance that demands a materially different algorithm-body hypothesis
instead of another shallow scheduler/budget/post-polish variant.

The first smoke after that repair showed the next code-repair control issue:
the model fixed an inert-helper C9e failure but introduced a fresh C9d
`instance.name` violation in the repair patch. C9d was correct; the APS loop
was too shallow. Code-stage preview repair now has two bounded attempts,
re-running Contract preview after each repair, and solver-design code prompts
explicitly forbid adding new `instance.name`/`getattr(instance, 'name')` uses
even in error messages.

The subsequent 2-round Sonnet smoke validated the framework repair. Round 1
passed Contract preview, algorithm smoke, Verification, and screening, then
was correctly abandoned for solver quality (`win_rate=0.0`, median delta
`0.0`, runtime ratio median `0.778`). Round 2 used round-1 feedback, hit an
algorithm-smoke runtime failure, then a C9c Contract failure, and the second
bounded repair produced a patch that passed Contract preview plus algorithm
smoke and reached formal screening. It was also correctly abandoned
(`win_rate=0.0`, median delta `0.0`, runtime ratio median `0.903`). This is
positive framework evidence: repair feedback is now sequential and auditable,
while promotion remains controlled by Contract, Verification, Protocol, and
Decision.

The latest target-diversity/C9e repair separates framework progress from
solver-quality failure. Hypothesis context now expands
`policies/baseline_modules/*.py` into concrete champion module paths and adds
plateau guidance after repeated win-rate-zero scheduler attempts, so the agent
is pushed toward the module that owns the mechanism instead of another
scheduler-only reshuffle. A 3-round Sonnet smoke first validated that target
diversity was live: round 1 targeted `destroy_repair.py` and reached
screening, while rounds 2 and 3 targeted `local_search.py`. Those later rounds
exposed a C9e false negative: new VNS move functions returned from
`_default_vns_operators()` were legitimate first-class operator references,
but the static integration check only recognized direct function calls. C9e
now treats loaded function-name references as reachability edges, and
solver-design code prompts explicitly tell local-search candidates to wire new
moves through `_default_vns_operators()` / `_vns(...)` rather than inventing
detached scheduler `_run`/`run` entrypoints. The follow-up 2-round Sonnet
smoke reached formal screening in both rounds. Round 2 modified
`local_search.py` and no longer failed C9e; it was correctly abandoned because
the algorithm was worse and slower (`win_rate=0.0`, median delta `-10.25`,
runtime ratio median `1.2055`). This is framework-positive but not
solver-quality evidence.

The follow-up 6-round Sonnet smoke exposed that the pre-screen algorithm
smoke was still too narrow. It used the tiny split copied into the branch
workspace, while formal screening used the active CVRP formal split. That let
some candidates pass smoke and then fail formal screening with larger-case
runtime errors. Algorithm smoke now receives the active campaign
`split_manifest` and `seed_ledger` through `ProposalToolContext`, runs canary
plus four evenly spaced screening cases, and resolves external formal cases
through `SCION_PROBLEM_DATA_ROOT`. CVRP preview also fails early for two
repeated interface mistakes: importing `solve`/`run`/`main` from
`baseline_modules.scheduler` in `baseline_algorithm.py`, and passing
arguments to `context.nearest_neighbor()`. After this repair, framework
validation smokes should use at least 3 rounds; 2-round runs are useful for
debugging only and are too weak to validate this class of control change. The
3-round validation smoke after the repair completed with exit code `0`; all
three candidates passed APS, Contract preview, algorithm smoke, Verification,
and formal screening before being correctly abandoned by
`SCREENING_FAIL_WIN_RATE`. Targets were `acceptance.py`, `local_search.py`,
and `construction.py`; each screened on 8 formal cases and 16 pairs with
seeds `11` and `29`. A deeper trace review shows that candidate quality is
still weak for framework reasons: the acceptance candidate added a reheat hook
without wiring it into the scheduler, and the construction candidate rewrote
the scheduler into a near-zero-search path that swallowed a bad `_vns` call.
The follow-up control repair now makes C9e treat new class methods as helpers
that must be reachable from the solver path, replaces line-count caps on
scheduler/entrypoint integration with stable runtime-contract checks, and makes
`proposal.algorithm_smoke` reject solver-design candidates that claim or touch
search-bearing code while recording zero search iterations and zero move
attempts on every successful smoke case, and now also rejects low-effort
search-bearing candidates that stop almost immediately with no smoke
micro-benchmark win and a `no_improvement`-style stop reason. Multi-module
solver-design patches may now integrate through `scheduler.py` /
`baseline_algorithm.py` when those files preserve the
`_ALNSVNSSolver(...).solve(instance, rng)` call chain, keep the current
explicit scheduler constructor keywords, keep
`_ALNSVNSSolver.solve(self, instance, rng)`, and avoid detached top-level
scheduler entrypoints. The 2026-05-16 low-effort-smoke follow-up exposed why
this must be static: generated construction/acceptance candidates tried to pass
custom seeds through `baseline_algorithm.py` or rewrote the scheduler
constructor API, so all 3 rounds failed before official screening.
The follow-up 3-round validation produced one formal screening candidate and
two acceptance-code failures. The first candidate proved the entrypoint API
repair works: it passed Contract, smoke, Verification, and screening before
being abandoned for `SCREENING_FAIL_WIN_RATE`. The remaining failures exposed
two narrower controls now repaired: C9e statically checks solver-design
cross-module imports against candidate/champion exports, and algorithm smoke
keeps actionable subprocess failure detail instead of collapsing to generic
`solver run failed`.
As part of the same maintainability pass, solver-design smoke helpers were
moved from `proposal/tools.py` into `proposal/solver_design_smoke.py`, and the
4k+ line `test_agentic_proposal_tools.py` file was split into topic-specific
test modules for context, schema, solver-design smoke, feedback, and session
behavior.
The post-split 3-round Sonnet smoke
`/home/clawd/research/scion-experiments/v04-smoke-diagnostics-sonnet-3r-20260516T144014Z`
completed normally at commit `1303f60`. It produced one official screening
candidate, which passed Contract/smoke/Verification/screening before the
Decision layer abandoned it for `win_rate < 0.3`. The other two attempts failed
in code-stage algorithm smoke with explicit branch object-model errors
(`_Solution.from_public` and `_Solution.from_cvrp_solution` do not exist) plus
repair guidance. This validates the framework repair and decomposition: failures
are now diagnosable before formal screening, while weak candidate algorithms are
still blocked by smoke or Decision rather than promoted.

The follow-up 6-round Sonnet diagnostic
`/home/clawd/research/scion-experiments/v04-smoke-diagnostics-sonnet-6r-20260516T150140Z`
showed that explicit smoke errors were not enough: five rounds failed before
screening, mostly because code-stage candidates repeatedly invented branch
state bridge APIs such as `_Solution.from_public(...)`,
`_Solution.from_routes(...)`, `_Solution.from_cvrp_solution(...)`, or
`solution.to_public()`. This is not solver-quality evidence; it is an APS
object-model control gap. The repair makes the internal `_Solution` / `_Route`
model explicit in solver-design prompts, CVRP interface text, and support
artifact summaries; C9e now statically rejects invented bridge calls and
bridge method definitions on `baseline_modules/state.py`. APS final failure
detail now reports the latest evaluative Contract/smoke preview instead of
stale or non-evaluative skipped preview observations, and stagnation classifies
repeated object-model/API failures as `object_model_loop` with
`inspect_agent_trace` guidance.

As part of the same maintainability repair, `agentic_session.py` has been
reduced from a 6k-line all-in-one module into a session orchestrator plus
focused helpers: `agentic_models.py`, `agentic_artifacts.py`,
`agentic_diagnostics.py`, `agentic_code_context.py`, `agentic_preview.py`, and
`agentic_utils.py`. Future APS work should keep new models, artifact logic,
preview logic, and prompt-shaping helpers in those focused modules.

The first 3-round monitored smoke after that repair
`/home/clawd/research/scion-experiments/v04-object-model-control-sonnet-3r-20260516T170823Z`
exited normally and produced one formal screening experiment. Rounds 1 and 2
failed in code-stage Contract preview, but trace review showed the important
control issue: after one or two code-repair generations, APS hit the 120 second
session wall-time limit before it could re-run the terminal Contract preview
on the latest repaired patch. Round 3 targeted `local_search.py`, passed
Contract preview, algorithm smoke, Verification, and screening, then was
correctly abandoned by Decision (`SCREENING_FAIL_WIN_RATE`, win rate `0.0`,
median delta `0.0`, runtime ratio median about `1.005`). This validates the
object-model repair path but exposes a budget mismatch. Code/fix LLM calls can
legitimately take up to 180 seconds, so the default APS session budget is now
240 seconds; CLI `--agentic-session-timeout-sec` still overrides it.

The immediate 3-round validation after the 240-second budget repair
`/home/clawd/research/scion-experiments/v04-aps-budget-sonnet-3r-20260516T172901Z`
also exited normally and produced one formal screening experiment. Round 1
targeted `scheduler.py`, passed APS, Contract preview, algorithm smoke,
Verification, and screening, then was correctly abandoned for
`SCREENING_FAIL_WIN_RATE` (`win_rate=0.0`, median delta `0.0`, runtime ratio
median about `1.001`). Rounds 2 and 3 targeted `destroy_repair.py`; both failed
before formal screening with auditable Contract/smoke findings, not framework
timeouts. Round 2 reached terminal algorithm smoke and failed on an invalid
`_vns(..., time_limit_sec=...)` call. Round 3 exhausted bounded Contract repair
on unresolved imports/inert helper integration. This is stable enough for a
6-round Sonnet background validation: failures are now either official
algorithm-quality abandonments or precise pre-screen boundary failures.

The follow-up 6-round Sonnet background validation
`/home/clawd/research/scion-experiments/v04-aps-budget-sonnet-6r-20260516T174845Z`
also exited normally. It produced two formal screening experiments and kept
champion v1. The budget repair remained valid: no APS session ended via
`session_timeout`, and the earlier `_Solution.from_*` / `to_public`
object-model loop did not recur. The new repeated failure pattern was
destroy/repair code-stage misadaptation: candidates targeting
`policies/baseline_modules/destroy_repair.py` repeatedly used `scheduler.py`
as the real research surface, invented construction imports such as
`_clarke_wright_solution`, `_nearest_neighbor_solution`, and
`_savings_construction`, or emitted uncapped `while` loops in scheduler
integration edits. Current repair makes code context branch-aware for
previously verified branches, injects an exact solver-design module API
manifest into code prompts, gives destroy/repair targets a stricter ownership
rule (destroy_repair owns the mechanism; scheduler only wires exact
destroy/repair symbols into operator pools), and makes C9e missing-import
feedback report `available_exports` from the imported sibling module. This is
still a framework/control repair, not solver-quality evidence.

The monitored 3-round Sonnet validation after the API-manifest repair
`/home/clawd/research/scion-experiments/v04-api-manifest-sonnet-3r-20260517T034512Z`
completed normally at commit `88e27aa`. It produced three official screening
experiments and kept champion v1. Targets were `scheduler.py`,
`destroy_repair.py`, and `local_search.py`; all three sessions completed APS,
Contract preview, algorithm smoke, Verification, and formal screening before
Decision abandoned them for `SCREENING_FAIL_WIN_RATE`. The destroy/repair
round is the important framework signal: it generated a pure
`destroy_repair.py` patch with no scheduler integration edit, no invented
construction imports, and no C9e/C9c loop. All three screened candidates had
16/16 valid pairs, zero candidate solver failures, nonzero search iterations
and move attempts on every pair, and slight median runtime speedups, but no
objective wins (`win_rate=0.0`, `median_delta=0.0`). This is stable enough to
run a 6-round background validation; it is not solver-quality progress.

The May 15 runtime-governance repair makes algorithm compute time a real
positive optimization signal under strict boundaries. A candidate that ties the
lexicographic objective, has no runtime failures, and beats champion median
runtime by `runtime.tie_speedup_ratio` may pass screening, validation, and
frozen via `*_PASS_RUNTIME_TIE_IMPROVEMENT`; it still cannot bypass the
three-layer protocol. `ExperimentProtocol` computes these gates after runtime
stats are attached to `EvalStats`, so protocol gate outcomes and Decision
reason codes now agree on runtime tie-speedup evidence. CVRP `solver_design`
context now exposes
`context.remaining_time()` explicitly as seconds and
`context.remaining_time_ms()` for millisecond comparisons. Contract preview
rejects preferred `policies/baseline_algorithm.py` patches that compare
second-valued `remaining_time()` to millisecond-derived variables.

The older `policies/main_search_strategy.py` path remains declared as the
legacy `main_search_strategy` config surface for compatibility and regression
tests. It is no longer the preferred solver-design research object.

Current branch: `v0.4-dev`

Current interpretation:

- Scion core remains problem-agnostic: proposal observations are tainted,
  Decision does not read proposal text, and problem semantics stay behind
  adapters/problem packages.
- Forced single-surface diagnostics have done their job for governance and
  runtime-audit validation. They should not continue as the main optimization
  path.
- CVRP now declares `solver_design` as the top-level research boundary backed
  by `policies/baseline_algorithm.py` and the
  `policies/baseline_modules/` package, with `policies/solver_algorithm.py`
  retained only for compatibility. Deep mechanism policies and the legacy
  `main_search_strategy` table remain useful implementation hooks or
  regression surfaces, but they are not standalone optimization goals.
- Solver subprocesses now receive the selected surface through
  `SCION_SELECTED_SURFACE`. This is the runtime switch that lets
  `solver_design` evaluate the branch-owned full algorithm while preventing
  that algorithm from swallowing unrelated component-surface experiments.
- The latest contract repair is a framework/problem-boundary repair, not a
  solver-quality improvement. `novelty_signature` is hypothesis metadata only;
  generated policy/config dictionaries must not copy it unless a surface
  explicitly declares that key. `problem_adaptation.component_roles` may now
  describe lifecycle targets such as construction, repo-local baseline,
  strict-improvement acceptance, restart, perturbation, and package-owned
  main-search components. `evidence_targets` may name the actual
  `main_search_*` audit fields that proposal feedback uses.
- The first free solver-design diagnostic did select `solver_design` in round
  1, but a `V5_solution_consistency` failure made later APS sessions reason
  from "`solver_design` is blacklisted" and return to component surfaces. This
  is a governance/proposal-feedback failure, not evidence that the surface is
  exhausted.
- Heavy Verification failures under declared `solver_design` surfaces now mark
  only the candidate implementation `rejected`; hypothesis context and APS
  feedback explicitly recommend retrying the problem-object boundary rather
  than falling back to component policies.
- The follow-up boundary-repair diagnostic selected `solver_design` twice and
  reached screening both times, but then drifted to `baseline_policy` after
  zero-movement screening failures. The latest code now makes `solver_design`
  an active problem boundary: proposal context, APS tools, target preview, and
  final hypothesis prompts reject component-policy `change_locus` values when
  no forced diagnostic surface is active.
- The latest active-boundary and semantic-identity diagnostics confirm boundary
  control in live free-surface runs: all completed or partial APS outputs stayed
  on `solver_design` after heavy Verification and zero/low-movement screening
  failures.
- Active-boundary APS tool guidance now distinguishes a problem-object boundary
  from `--force-surface`: traces render `active_problem_boundary_rule` with
  `allowed_surface_ids=["solver_design"]`, not a fake forced-surface rule with
  `[null]`.
- For semantic-signature solver-design hypotheses, declared algorithm identity
  fields such as `algorithm_family`, `construction_strategy`,
  `improvement_strategy`, `acceptance_strategy`, and
  `runtime_budget_strategy` are required. Free-text rationale is not novelty
  identity.
- APS self-check failures now fail closed for real sessions. Schema/target
  preview failures, skipped Contract previews, or failed Contract previews stop
  the completed output before the patch enters evaluation.
- The higher-ceiling v3 path is now a problem-object algorithm path:
  instance model, solution model, objective policy, safe helper API, and
  whole-solver evidence are rendered by the adapter as one coherent object for
  Scion to reason over.
- The earlier route-pool and `algorithm_body` repairs are retained as legacy
  mechanism evidence, but they are no longer the main research object. The
  current blocker is whether APS can use the direct `solve(...)` boundary to
  produce repeated solver-quality movement without modifying objective or
  constraint semantics.
- Solver-design target selection is now more concrete: wildcard module
  targets are expanded from the champion snapshot, and repeated scheduler-only
  win-rate-zero failures should steer the next hypothesis toward
  `construction.py`, `destroy_repair.py`, `local_search.py`, or
  `acceptance.py` when those modules own the mechanism. C9e recognizes
  first-class operator-list integration such as local-search functions returned
  by `_default_vns_operators()`, while still rejecting truly inert helpers.
- Solver-design smoke now samples the active campaign split rather than the
  branch workspace's tiny fallback split. It runs canary plus four evenly
  spaced screening cases and uses the active seeds, so larger-case API/runtime
  failures are caught before formal screening when possible.
- Scion's role is boundary/protocol/audit control, not replacing the research
  agent with prompt-only field exposure. The latest short run showed that
  hypothesis-stage tools were not enough: the code stage also needs bounded
  access to memory, branch state, screening/runtime feedback, and the full
  approved problem object while implementing the algorithm.
- The previous short lifecycle diagnostic showed why this had to be deeper
  than field exposure: candidates declared smaller baseline fractions but
  runtime silently used the legacy formal 0.75 floor, `phase_sequence` did not
  control component order, construction candidates were not passed into the
  route-pool, and cleanup/adaptive-budget controls were mostly descriptive.
  Those execution gaps are now repaired and unit-tested.
- The follow-up execution-semantics diagnostic remains important historical
  evidence: componentized route-pool recombination was too expensive relative
  to its sparse gain. Under the new boundary, runtime should be handled inside
  the candidate algorithm and audited through `solver_algorithm_elapsed_ms` and
  `solver_algorithm_phase_runtime_ms`.
- APS observation handling for CVRP deep-surface diagnostics now uses the 64k
  default, compact 800-character surface code previews, and an explicit
  terminal reserve for schema/target/interface/Contract previews after
  required diagnosis context has been gathered. Terminal Contract preview keeps
  compact deterministic pass/fail evidence if the full preview payload would
  exceed the remaining observation budget. This is now validated in live
  free-surface runs: completed code sessions passed Contract preview and no APS
  `output.json` in the latest run contained `result_too_large`.
- The latest free-surface post-optimization smoke selected two newly added
  deep mechanism surfaces: `alns_vns_policy` and
  `acceptance_restart_policy`. `destroy_repair_policy` and
  `route_pair_candidate_policy` still were not selected.
- ALNS/VNS attribution is now explainable: the selected `alns_vns_policy`
  candidate recorded nonzero `alns_vns_phase_delta_sum`, construction-start
  distance, returned baseline distance, and objective deltas. This validates
  attribution plumbing, not solver efficacy.
- APS self-check reservation now preserves tool calls and observation-char
  headroom for compact schema/target/interface/Contract previews. The latest
  forced diagnostics reached final self-checks without `result_too_large`; the
  enum-interface rerun's Contract preview passed for all 7 completed code
  sessions.
- Forced-surface controls fail closed, and the final hypothesis-generation task
  now narrows `change_locus`, `action`, and `target_file` to active forced
  values instead of presenting the full surface list. The latest forced
  `destroy_repair_policy` rerun validated this in real APS traces.
- The latest code also makes `destroy_repair_policy` selector levers real:
  `route_diverse_worst` changes destroy ranking and `cheapest` uses a
  low-budget cheapest repair path instead of all selectors flowing through the
  same worst-removal/regret-2 implementation.
- The CVRP adapter-rendered `destroy_repair_policy` interface now lists valid
  `destroy_selectors`, `repair_selectors`, and `subset_strategy` values
  explicitly, including a warning not to put `single_worst` or `route_diverse`
  in `destroy_selectors`.
- The latest enum-interface rerun validates that model-facing repair but also
  demonstrates the limit of policy-by-policy exposure: 7 valid screened
  `destroy_repair_policy` candidates made 7,168 destroy/repair attempts across
  112 pairs with zero accepted current/recovery/phase-best moves and
  `destroy_repair_phase_delta_sum=0.0`.

The balance-restored 2-round smoke from the slimmed code path completed
cleanly. Both candidates passed Contract/Verification and screened 16/16 valid
pairs. Round 1 was a fast low-quality replacement solver (`0` wins, `16`
losses, median pair delta `-119.5`, median runtime ratio about `0.029`).
Round 2 consumed that feedback and switched to a baseline-plus-ILS solver (`1`
win, `15` ties, `0` losses, median pair delta `0.0`, median runtime ratio
about `1.00045`). This is not promotion-quality, but it is a real
feedback-loop and whole-solver positive signal.

The follow-up 5-round exploratory run showed that this is still not ready for
long unattended solver-quality validation. It reached three screened
`solver_design` candidates with weak positive signal, then hung after a
successful code-generation trace. The likely failure point was post-code
Contract/CVRP synthetic preview executing a candidate with unbounded
improvement-flag loops. This is now repaired as a boundary-control issue:
static C9c rejects unbounded boolean-flag `while` loops, CVRP synthetic
preview times out `solve(...)`, and APS converts a hung
`proposal.contract_preview` into a controlled `tool_error`.

The 2026-05-14 code-self-check smoke from commit `06e9365` completed 2/2
rounds cleanly and validated the framework path: code-phase tool selection,
Contract-preview repair, `solver_algorithm` activation, runtime telemetry, and
fail-closed Decision all worked. Both candidates were abandoned by
`T4: win_rate < 0.3`. Round 1 had 3 wins, 1 loss, 12 ties, and median runtime
ratio about `1.234x`; round 2 had 1 win, 2 losses, 13 ties, and median runtime
ratio about `1.063x`. This is an algorithm-quality failure, not a boundary
failure.

The follow-up repair exposes adapter-rendered solver mechanics directly from
`context.read_problem`, so code phase sees the fixed objective/constraint
boundary and the direct `solve(...)` lifecycle without reconstructing it from
surface snippets. CVRP Contract preview now also runs `solver_design` on a
synthetic improvement-trap instance and fails baseline-seeded no-op wrappers
that do not improve the preview baseline. Screening feedback now prioritizes
`solver_algorithm_move_attempts`, `solver_algorithm_accepted_moves`,
`solver_algorithm_best_delta`, `solver_algorithm_search_iterations`, elapsed
time, and phase runtime fields, making "ran but did not move phase-best"
visible to the next agent turn.

The latest 2-round no-op-feedback smoke did not validate that micro-eval
repair because both rounds failed earlier in final `generate_patch` after
three provider timeout attempts. The important finding is framework control:
the code-phase tool loop reached the approved `solver_design` target and read
the full selected surface, but the approved hypotheses still invited broad
hybrid baseline/ILS/destroy-repair implementations that were too large for a
single static code response. Treat this as an APS code-generation scope
failure, not a reason to return to component-policy exposure.

Current repair: solver-design code generation now defaults to a compact
target-file change shape. The prompt asks for one construction or seeding path
plus one bounded improvement/search loop, discourages preserving or expanding
the branch-owned ALNS/VNS-style algorithm body unless the change is material,
and allows the target-file change to be much shorter than the current
implementation.
When final patch generation times out, APS performs one semantic retry inside
the same session with `code_generation_mode=compact_timeout_retry`, injects
`prior_code_failure=code_generation_timeout`, tightens problem/interface/
hypothesis caps, and records the retry in the transcript. This is separate
from Contract-preview or code-self-check repair attempts.

The 2026-05-14 2-round code-scope smoke from commit `2e6a888` passed the first
gate: final `generate_patch` returned in all three code traces, and round 1
reached Contract, Verification, and screening. It also exposed the next APS
control issue. Screening/runtime feedback consumed almost the entire 64k
session observation budget in round 2, leaving too little space for terminal
Contract-preview evidence; the session failed closed with
`contract preview did not pass (result_too_large, tool_error)`.

The follow-up 2-round feedback-budget smoke from commit `ff7ae66` validated
that APS repair: both code sessions completed, both retained terminal
Contract-preview evidence, and no session failed with `result_too_large`.
Round 2 also proved Contract-preview repair in-session by rejecting an initial
uncapped-loop patch and accepting the regenerated patch.

The deeper research-object repair now makes `policies/baseline_algorithm.py`
the preferred solver-design target and forbids `context.baseline(...)` calls
from that file in CVRP problem-owned preview. This changes the research loop
from "call baseline, then polish" to "modify the controlled algorithm body and
let the candidate become the next champion if it passes the gates." The
original `vrp/` implementation remains frozen; all candidate changes happen
inside Scion branch snapshots.

Code phase now has an explicit debug/effectiveness gate:
`proposal.algorithm_smoke`. After static Contract preview passes, APS runs a
tainted, non-promotional synthetic CVRP smoke by calling the candidate
`solve(...)`. For `solver_design` patches to `policies/baseline_algorithm.py`
or `policies/solver_algorithm.py`, APS now materializes a temporary tainted
workspace, applies the patch, and runs the configured canary case under the
selected `solver_design` runtime. A failed smoke can feed one bounded repair
attempt before the patch enters official evaluation. This smoke does not write
candidate/champion workspaces and does not count as promotion evidence; final
validation remains Contract, Verification, Protocol, and Decision.

The same smoke exposed the next direction-level blocker. `solver_design` is a
full-algorithm hook, but the agent is still being induced to treat the
repo-local baseline as an oracle/seed and then write small post-baseline local
search code. The first-round hypothesis was too shallow because it did not
study the ALNS+VNS baseline algorithm body before choosing the mechanism, and
the code phase effectively wrote a generic cleanup solver around
`context.baseline(...)`. This is not Scion's intended loop. Scion should let
the research agent study the algorithm under boundary/protocol/audit control,
modify a controlled candidate copy of that algorithm, and let successful
candidate branches become the next champion/baseline. The original `vrp/`
files remain frozen; candidate algorithm changes must happen inside
Scion-controlled branches.

Current repair target: improve the CVRP research-object adapter so hypothesis
and code phases can study and modify the algorithm body that actually matters,
instead of producing baseline-wrapper post-processing solvers. The budget and
Contract-preview control path is now healthy enough to support that deeper
repair.

Operational cost/control note: for this development phase, all new real-cost
short experiments should use local codex-proxy explicitly
(`SCION_MODEL=gpt-5.5`, `SCION_BASE_URL=http://127.0.0.1:8080`,
`SCION_API_KEY=...`) and should omit `SCION_REASONING_EFFORT` unless the run is
specifically testing reasoning behavior. External Sonnet/Opus/DeepSeek runs are
diagnostics, not the default path. Provider SDK retries are disabled by default
in `LLMClient` so Scion's own traced retry loop is the single audited retry
layer; tune with `SCION_LLM_MAX_RETRIES` and only opt into SDK retries with
`SCION_SDK_MAX_RETRIES` deliberately. Code/fix tool calls are now treated as
long non-streaming generation requests: by default they use
`timeout_sec=max(SCION_LLM_TIMEOUT_SEC, 180)` and `max_retries=0`, with
per-kind overrides through `SCION_LLM_CODE_TIMEOUT_SEC`,
`SCION_LLM_CODE_MAX_RETRIES`, `SCION_LLM_FIX_TIMEOUT_SEC`, and
`SCION_LLM_FIX_MAX_RETRIES`.

## Current Engineering State

### Framework Boundary

- Framework prompt assembly no longer hardcodes warehouse/VNS/CVRP mechanics.
- Problem-specific mechanics, objective semantics, feasibility, and runtime
  evidence interpretation live in problem adapters/packages.
- `ProblemSpecV1.research_surfaces` is the forward-compatible abstraction for
  optimization targets.
- Contract, Verification, Protocol, and Decision are surface-aware without
  embedding CVRP/warehouse-specific logic in core.
- Runtime env passthrough is generic for `SCION_*` variables.
- Legacy non-adapter paths remain compatibility-only; new problems should use
  `ProblemAdapter`.

### Campaign And APS

- `campaign.py` is now mostly a facade over extracted proposal, evaluation,
  promotion, evidence, failure-lifecycle, branch-stepping, workspace, and
  decision services.
- APS uses a two-phase proposal path for research/hypothesis and code
  implementation.
- Forced-surface controls are carried into APS tool context and fail closed
  before code generation.
- When declared and not overridden by `--force-surface`, `solver_design` is
  carried as an active problem-object boundary into proposal context, APS tool
  context, target previews, and output validation. Component policies are
  implementation hooks or attribution evidence, not top-level `change_locus`
  replacements.
- Real APS sessions fail closed when schema/target/Contract self-check
  previews fail or are skipped.
- APS feedback defaults to same-campaign or forced-surface history for forced
  diagnostics.
- Tool observations are rendered into final hypothesis/code prompts.
- Code phase is now agentic within the same boundary. After ContractGate
  approves a hypothesis, APS can run a bounded code-phase tool loop over
  exposure-controlled tools before final `PatchProposal` generation. The loop
  may read the selected surface at full code-preview budget, inspect branch
  state, query memory, and query screening/runtime feedback. It still cannot
  write candidate workspaces, read validation/frozen raw metrics, or make
  protocol/Decision calls.
- Failed Contract preview feedback is now fed into one bounded patch
  regeneration attempt before the session fails closed.
- Contract preview is also wall-time bounded before workspace materialization.
  A hung `proposal.contract_preview` now returns a controlled APS tool error
  instead of blocking the campaign.
- The first micro smoke after this repair confirmed code-phase tool selection
  and full `solver_design` surface read, but the final `generate_patch` call
  still timed out on a roughly 49k prompt. Prompt slimming now omits both the
  duplicate full champion policy bundle and duplicate surface-read
  `content_preview` code from final `solver_design` code prompts. The complete
  target file remains available once in the `Target File` section, while the
  audited full selected-surface read remains part of APS tool evidence.
- The balance-restored 2-round smoke showed the complete feedback loop working:
  `generate_patch` returned successfully, Contract-preview repair passed,
  Contract and Verification passed, screening feedback was stored, and the next
  hypothesis used that screening/runtime feedback to change algorithm strategy.
  Prompt slimming remains incomplete; the second-round code prompt still grew
  to roughly 55.6k characters.
- The latest preview-repair smoke still failed before preview because final
  code-generation prompts stayed too large and one planner prompt contained an
  empty tool name after holdout sanitization. Current repair compacts
  code-phase tool observations, filters holdout summary from model-facing
  planner specs, stops repeated code-phase surface reads, and normalizes
  timeout retry guidance.
- The compact-prompt smoke from commit `7f7ef04` reduced code prompt user text
  to roughly 35.5k-35.8k and reached screening in round 2, but round 1 still
  timed out at final `generate_patch`. Current prompt repair therefore filters
  final code observations to code-relevant feedback plus the latest full
  selected-surface read metadata, and caps solver-design static text fields
  before the target file is rendered.
- The no-op-feedback smoke from commit `a653388` reached the same code-phase
  tool path, but both final `generate_patch` calls timed out before Contract
  preview. APS now handles this as a controlled code-scope issue:
  solver-design prompts default to compact single-mechanism solver bodies, and
  timeout failures trigger one in-session semantic retry with a smaller
  compact-timeout mode instead of repeating the same broad request.
- Observation-budget pressure is mitigated by compact surface reads, compact
  preview payloads, and a self-check/static-preview reserve. Optional planner
  surface reads fail closed before consuming the reserve.
- Screening/runtime feedback is now compacted again at the APS observation
  boundary. The model still sees reason codes, recent screening stats,
  runtime-attribution highlights, and research diagnosis, but bulky case
  feedback and raw-sized value lists no longer crowd out terminal Contract
  preview evidence.
- Solver-design pre-screening and screening failures are rendered as
  boundary-control guidance: rejected or blacklisted solver-design entries are
  candidate failures, not retirement of the problem-level surface.
- Campaign-level forced-surface diagnostics now carry the forced
  surface/action/target into APS tools and the final CreativeLayer hypothesis
  task. APS still fails closed if a model produces an off-surface hypothesis.

### CVRP Runtime

- CVRP `.vrp` runs can use the repo-local `vrp/src` ALNS+VNS baseline when
  `SCION_PROBLEM_DATA_ROOT` points at the repo `vrp` directory.
- Required-baseline fallback or baseline errors are runtime audit failures, not
  objective ties.
- CVRPLIB internal node ids from `vrp/src` are mapped back into Scion's
  depot-first CVRP id space.
- Generated registry operators stop after a complete no-improvement round, so
  no-op post-baseline operators do not repeat for 20 rounds.
- Malformed, infeasible, exception-raising, or audit-incomplete outputs fail
  closed.

### CVRP Research Surfaces

CVRP currently exposes these declared surfaces:

- `route_local`
- `route_pair`
- `ruin_recreate`
- `search_policy`
- `baseline_policy`
- `construction_policy`
- `neighborhood_portfolio`
- `algorithm_blueprint`
- `solver_design`
- `main_search_strategy`
- `alns_vns_policy`
- `destroy_repair_policy`
- `route_pair_candidate_policy`
- `acceptance_restart_policy`

`solver_design` is the problem-owned full-algorithm surface. It is backed
first by the singleton execution file `policies/baseline_algorithm.py`, with
`policies/solver_algorithm.py` retained as an older compatibility hook:

- required function: `solve(instance, rng, time_limit_sec, context)`;
- allowed helpers: `context.make_solution`, `context.nearest_neighbor`,
  `context.objective`, `context.is_valid`, `context.remaining_time`,
  `context.elapsed_ms`, `context.record_phase`, `context.record_iteration`,
  `context.record_move`, and `context.set_stop_reason`;
- `context.nearest_neighbor()` takes no arguments and returns a
  `CvrpSolution`; use it directly as a candidate solution.
  `context.make_solution(...)` accepts route iterables and is idempotent for
  existing solution objects;
- compatibility helper: `context.baseline(...)` may exist for older
  `solver_algorithm.py` experiments, but preferred
  `baseline_algorithm.py` candidates must not call it;
- editable algorithm scope: construction, local search, destroy/repair,
  recombination, acceptance, restart/perturbation, and runtime scheduling;
- fixed boundary: objective, feasibility, parser, data, protocol splits,
  seeds, Decision, `solver.py`, `adapter.py`, `models.py`, and `cvrplib.py`;
- required evidence: `solver_algorithm_loaded`,
  `solver_algorithm_active`, `solver_algorithm_errors`,
  `solver_algorithm_elapsed_ms`, `solver_algorithm_phase_runtime_ms`,
  solution validity/routes/objective/distance/fleet violation,
  search-iteration/move-attempt/accepted-move counters, improving-vs-neutral
  accepted-move counters, phase delta telemetry, and stop reason.

Current repair: `policies/baseline_algorithm.py` is now the active
solver-design algorithm subject when `solver_design` is selected. It contains a
controlled ALNS/VNS-style algorithm body with construction, capped route-edit
neighborhoods, destroy/repair, perturbation, acceptance, runtime polling, and
solver-algorithm telemetry. Candidate branches should modify that branch copy
directly. Adapter preview rejects preferred-target `context.baseline(...)`
wrappers, so the candidate cannot reduce the research task to "call champion,
then polish." It also fails closed on synthetic preview timeout, so generated
`solver_design` code cannot hang Scion before workspace materialization. The
timeout sentinel is outside normal `Exception` handling so generated candidate
code cannot swallow it with a broad `except Exception`.

`main_search_strategy` is a legacy config surface backed by
`policies/main_search_strategy.py`. It preserves the earlier `main_search_plan`
and `algorithm_body` tests, but it is not the default optimization direction.

Current limitation: the direct full-algorithm boundary is now smoke-validated
for framework stability, but not solver quality. The first gate is satisfied:
candidates can target `baseline_algorithm.py`, pass Contract plus
`proposal.algorithm_smoke`, enter official Verification, and run 16/16 formal
screening pairs as controlled algorithm-body changes. Solver promotion quality
is still a later gate under the existing `solver_algorithm_*` evidence.

## Latest Experiment

Latest contract-integration gate validation and repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-contract-integration-gate-sonnet-6r-20260515T230605Z
model=claude-sonnet-4-6
rounds_requested=6
screened_experiments=3
champion_version=1
stopped_reason=max_rounds_exhausted
```

Interpretation: the three screened candidates were valid solver-design
algorithm edits and were correctly abandoned by `SCREENING_FAIL_WIN_RATE`.
The agent behavior was directionally reasonable: it stayed on branch-owned
solver modules, used screening/runtime feedback, pivoted from scheduler to
local search, and eventually attempted a larger PBIG-style solver
restructure. The non-screened rounds revealed framework gate issues rather
than research-object drift. Detailed analysis:
[`v0.4-contract-integration-gate-sonnet-6r-20260515.md`](../experiments/v0.4/v0.4-contract-integration-gate-sonnet-6r-20260515.md)

Latest solver-design module-subject smoke and repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-module-subject-sonnet-2r-20260515T142828Z
model=claude-sonnet-4-6
rounds_requested=2
screened_experiments=0
stopped_reason=max_rounds_exhausted
last_result=code generation failed
```

This smoke validated the new research-object direction but exposed a budget
control issue. APS selected `solver_design` and targeted
`policies/baseline_modules/local_search.py`, proving the agent can now choose
focused branch-owned algorithm modules instead of regenerating the stable
entrypoint. It then failed before official evaluation because post-repair
Contract preview was replaced by `result_too_large` after the session spent
too much of its observation budget.

Current repair: code-phase reads for solver-design support modules use
`section=target_preview`, cap code preview at 6000 chars, and count that
module-target read as sufficient so the deterministic fallback does not read
the same module again. The full Scion suite passes after this repair
(`1670 passed, 1 skipped`).

Follow-up smoke after this repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-module-budget-repair-sonnet-2r-20260515T144636Z
rounds_requested=2
screened_experiments=0
stopped_reason=max_rounds_exhausted
last_result=code generation failed
```

The previous `result_too_large` failure did not recur. Contract preview
retained concrete C4b/C9c failures, so the budget repair is validated. The new
blocker is patch protocol expressiveness: the agent proposed
`create_new/policies/baseline_modules/intensification.py`, but the intended
algorithm change also required modifying scheduler/entrypoint code to call the
new module. Current `PatchProposal` was single-file, so generated code either
created an inert module or switched to `baseline_algorithm.py` and violated
the approved action/target.

Current repair: `PatchProposal` remains backward-compatible but now supports
optional `additional_changes`. Contract validates the primary change against
the approved hypothesis and validates every additional file independently
inside the same selected research-surface boundary. Workspace materialization
and `proposal.algorithm_smoke` apply all file changes together, so a
`solver_design` candidate can create a module and wire it into
`baseline_algorithm.py` or `baseline_modules/scheduler.py` without bypassing
editable/frozen path checks, interface checks, import whitelist, C9/C9b/C9c,
tainted smoke, Verification, Protocol, or Decision. Agentic output artifacts
omit all additional code bodies while preserving path/action/body-size audit
metadata.

Focused validation after this repair: `310 passed` across APS proposal tools,
research-surface Contract tests, workspace materialization, base Contract
tests, and proposal validation. Full suite validation:
`1672 passed, 1 skipped`. The next step is a 2-round Sonnet smoke; if it passes
the framework gate, start a 6-round independent validation run.

First 2-round smoke after the multi-file repair reached Contract repair and
then failed in `proposal.algorithm_smoke` with a framework compatibility bug:
live campaign context carried a legacy `ProblemSpec` with
`spec_version=problem-v1`, and smoke attempted to bridge it as if it were a
`ProblemSpecV1` with `id`. Runtime-audit spec handling now bridges only real
v1 specs with an `id` and uses already-legacy specs directly. Focused
regression after this fix: `311 passed`. Full suite after the compatibility
fix: `1673 passed, 1 skipped`.

Second 2-round smoke:
`/home/clawd/research/scion-experiments/v04-multifile-smoke-repair-sonnet-2r-20260515T152117Z`
completed with exit code 0. It confirmed multi-file/code-phase framework
control is stable, but showed `proposal.algorithm_smoke` was too narrow:
round 1 passed Contract, Verification, and canary, then failed official
screening on `tiny_6` with `solver_algorithm_runtime_error` (`'_Route' object
is not subscriptable`). Round 2 was blocked by schema/target preview for
overlong semantic-signature fields. Repair: solver-design algorithm smoke now
runs canary plus up to two public screening cases using the first public
screening seed. It remains tainted/non-promotional and reads no
validation/frozen cases. Validation after this repair: targeted smoke
regression `5 passed`, focused subset `312 passed`, full suite
`1674 passed, 1 skipped`.

The follow-up 2-round smoke completed with exit code 0 and showed the previous
`tiny_6` runtime leak was fixed: screening had 4/4 valid pairs and zero
candidate runtime failures, then abandoned normally for
`SCREENING_FAIL_WIN_RATE`. It also exposed a budget-control issue in round 2:
after screening/runtime feedback and code context, required
`proposal.contract_preview` had too little remaining observation budget and
collapsed to `result_too_large`. Repair: default agentic observation budget is
now 96k, required self-check tools have a minimal preview fallback that
preserves pass/fail and compact failed-check/runtime summaries, and repeated
compaction retains failed-check names. Validation after this repair: targeted
budget regressions `3 passed`, focused subset `313 passed`, full suite
`1675 passed, 1 skipped`.

2-round smoke after the self-check budget repair:
`/home/clawd/research/scion-experiments/v04-selfcheck-budget-sonnet-2r-20260515T161843Z`
completed with exit code 0. No `result_too_large` recurred. Contract preview
retained concrete `C4b_patch_action_target` and
`C9d_surface_instance_identity` feedback, and another candidate passed Contract
but was stopped by expanded `proposal.algorithm_smoke` for
`solver_algorithm_errors=1` before official screening. This is acceptable for
the repair: bad candidate code is rejected inside tainted self-checks, with
auditable failure evidence.

Latest code-generation timeout-policy diagnosis and repair:

```text
analyzed_run_root=/home/clawd/research/scion-experiments/v04-sdk-retry-control-sonnet-8r-20260514T181734Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
time_limit_sec=60
agentic_session_timeout_sec=1800
status=max_rounds_exhausted
```

Trace analysis corrected the prior interpretation. The 8-round run had
57/57 successful tool-selection calls and 5/5 successful hypothesis calls, but
only 2/15 code-generation calls succeeded. The 13 failed code traces all
clustered around `125.1s`, matching `60s client timeout + 5s backoff + 60s
client timeout` under `SCION_LLM_MAX_RETRIES=1`. Successful code calls were
not materially smaller; one succeeded in about `50s` and one in about `114s`.
The primary issue was therefore a non-streaming client timeout policy mismatch,
not prompt size alone.

Repair: `LLMClient` now resolves request policy by request kind. `code` and
`fix` tool calls default to a longer `180s` timeout and zero same-prompt
LLMClient retries, while APS keeps its single semantic compact timeout retry.
`CreativeLayer` writes the effective request policy into each LLM trace for
auditability. Streaming remains a useful follow-up but is not required for the
first repair validation.

Validation smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-codegen-timeout-policy-sonnet-2r-20260515T011055Z
rounds=2
stopped_reason=max_rounds_exhausted
code_trace_durations=121.68s, 125.41s, 143.88s, 144.25s
code_trace_policy=timeout_sec=180.0, max_retries=0
```

All four code-generation traces returned successfully and would have been
prematurely killed by the old 60s non-streaming timeout. Round 1 reached
screening and was normally abandoned by `SCREENING_FAIL_WIN_RATE`; round 2
generated code successfully but failed closed at Contract preview on
`C9c_complexity_bound`, which is a generated-algorithm boundary/quality issue
rather than an LLM timeout issue.

Follow-up 5-round Sonnet validation confirmed the LLM timeout repair:
10/10 `code/generate_patch` traces succeeded, with code durations from
`45.60s` to `124.55s` and no old 60s/125s timeout-failure pattern. The new
blocking issue was APS observation-budget handling: several branches generated
code and passed or repaired Contract preview, but `proposal.algorithm_smoke`
was replaced by `result_too_large` because the remaining transcript budget was
too small. The smoke tool had effectively run; the error message implied
otherwise.

Current repair: APS now compacts `proposal.algorithm_smoke` observations the
same way it compacts Contract preview observations, preserving pass/fail,
issue summary, static contract summary, and tainted/non-promotional flags while
dropping large preview bodies. The self-check observation reserve now scales
for Contract + smoke previews, and residual budget failures are reported as
smoke observation-budget failures rather than code-generation failures.

Validation smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-algorithm-smoke-budget-repair-sonnet-3r-20260515T042430Z
rounds=3
stopped_reason=max_rounds_exhausted
code_traces=5/5 ok
algorithm_smoke=3/3 ok with compact smoke preview retained
screening=3/3 reached
decision=3/3 abandon by SCREENING_FAIL_WIN_RATE
```

This confirms the framework path is now past the LLM timeout and
algorithm-smoke observation-budget blockers at short-run scale. The remaining
negative signal is solver quality: generated solver-design candidates reach
screening but lose to the champion.

Latest runtime-smoke/C9c repair validation:

```text
run_root=/home/clawd/research/scion-experiments/v04-runtime-smoke-audit-repair-sonnet-2r-20260515T113941Z
rounds=2
stopped_reason=max_rounds_exhausted
screened_experiments=0
round_1=full baseline_algorithm.py rewrite; failed old C9c before smoke
round_2=provider 500 during code generation
post_repair_replay=round_1 repaired patch passed Contract C9c and proposal.algorithm_smoke runtime canary
```

The replay matters more than the noisy 2-round run: after C9c learned to
recognize local runtime-guard helpers such as `while within_budget():`, the
Round 1 repaired patch passed static Contract preview and the new tainted
runtime smoke. The canary run loaded
`policies/baseline_algorithm.py`, produced a valid solution, recorded
`solver_algorithm_errors=0`, and split activity into
`solver_algorithm_improving_moves=1` and
`solver_algorithm_neutral_accepted_moves=14679`.

Detailed analysis:
[`v0.4-runtime-smoke-audit-c9c-repair-20260515.md`](../experiments/v0.4/v0.4-runtime-smoke-audit-c9c-repair-20260515.md)

Claude Code comparison: the next deeper design step is a Scion-native
continuous tool-use loop. Scion should keep permission, taint, exposure,
transcript, and promotion gates, but expose controlled proposal tools as native
LLM tools throughout hypothesis/code work. `generate_patch` should become the
code-phase finalizer after the agent has had a bounded chance to inspect
surface/branch/memory/feedback, draft, run Contract preview and algorithm
smoke, and repair from returned observations.

Detailed analysis:
[`v0.4-codegen-timeout-policy-repair-20260515.md`](../experiments/v0.4/v0.4-codegen-timeout-policy-repair-20260515.md)

Earlier same-day notes:

- `/home/clawd/research/scion-experiments/v04-sdk-retry-control-sonnet-1r-20260514T174450Z`
  completed the full 1-round branch-owned algorithm-subject path. It targeted
  `policies/baseline_algorithm.py`, passed Contract, Verification, and 16/16
  formal screening pairs, then was normally abandoned by
  `SCREENING_FAIL_WIN_RATE`. This validated framework stability but not solver
  quality.
- `/home/clawd/research/scion-experiments/v04-bounded-while-repair-smoke-opus-1r-dataroot-20260514T172756Z`
  also completed the full chain with 16/16 valid pairs and 16/16
  `solver_algorithm_*` runtime observations after a compact timeout retry,
  but it used Opus and is retained only as a secondary framework sample.
- `/home/clawd/research/scion-experiments/v04-branch-algorithm-subject-smoke-opus-1r-20260514T164018Z`
  selected `modify/solver_design`, targeted
  `policies/baseline_algorithm.py`, and reasoned about the ALNS+VNS algorithm
  body, but failed before official experiment pairs on a static C9c
  `while`-loop boundary that is now repaired. That failure was a
  Contract-preview rejection, not research-object drift: generated code used
  `while True` inside route construction and failed `C9c_complexity_bound` for
  `uncapped while loop`.
- `/home/clawd/research/scion-experiments/v04-bounded-while-repair-smoke-opus-1r-20260514T171241Z`
  completed code generation and Contract preview, but was launched without
  `SCION_PROBLEM_DATA_ROOT`; all formal pairs failed on missing CVRPLIB files,
  so it is an invalid launch-environment sample rather than solver evidence.

Follow-up repair: C9c now still rejects true unbounded `while True` and
unbounded improvement-flag loops, but recognizes two statically bounded
algorithm-body patterns: `while True` with a visible counter-bound break, and
`while True` that directly shrinks a finite collection on each non-break
iteration. Contract detail now includes the offending loop line. CVRP
solver-design prompts also tell code agents to prefer `for range(max_*)` loops
and to make any `while` bound statically obvious.

Latest baseline-algorithm subject smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-baseline-algorithm-subject-smoke-opus-2r-20260514T154153Z
model=claude-opus-4-6
problem=cvrp
protocol=formal
rounds_requested=2
time_limit_sec=60
agentic_session_timeout_sec=1800
status=terminated_for_invalid_research_object_analysis at 2026-05-14T16:11:51Z
target_file=policies/baseline_algorithm.py
```

Post-run analysis:

- Round 1 selected `modify/solver_design` with target
  `policies/baseline_algorithm.py`.
- Code phase generated an activated algorithm-body patch in that file, passed
  static Contract preview, then passed `proposal.algorithm_smoke` on tainted
  synthetic CVRP preview before entering official evaluation.
- Screening confirmed why the previous adapter was still wrong. The first
  candidate was 0 wins, 4 ties, 12 losses, median pair delta `-6.0`, and
  abandoned by `SCREENING_FAIL_WIN_RATE`.
- The failure was not just weak code quality. The candidate rewrote a
  simplified, inactive Scion template instead of modifying a branch copy of
  the real algorithm body. The original CVRP algorithm was still effectively a
  reference object, so Scion was training the agent to become a postprocessor
  or replacement-template author.
- That invalid experiment was terminated and the repair now makes
  `baseline_algorithm.py` a branch-owned, active ALNS+VNS algorithm subject
  under selected `solver_design` runtime. Promotion still requires the normal
  Contract, Verification, Protocol, and Decision gates; only a promoted branch
  becomes champion.

Previous analyzed code-scope/feedback-budget smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-code-scope-control-smoke-opus-2r-20260514T122210Z
model=claude-opus-4-6
problem=cvrp
protocol=formal
rounds_requested=2
rounds_completed=2 APS rounds, 1 screened experiment
time_limit_sec=60
agentic_session_timeout_sec=1800
git_commit=2e6a888
exit_code=0
status=max_rounds_exhausted
terminal_reason=code_generation_failed
analysis_doc=scion/docs/experiments/v0.4/v0.4-code-scope-control-feedback-budget-opus-2r-20260514.md
```

Summary:

- The prior code-scope repair worked for final code generation: all three code
  traces returned successfully instead of timing out.
- Round 1 reached Contract, Verification, and screening under
  `modify/solver_design`. It had 16/16 valid pairs, `win_rate=0.125`,
  `median_delta=0.0`, and median runtime ratio about `0.771`.
- The screened candidate produced real solver telemetry
  (`solver_algorithm_accepted_moves` nonzero on 7/16 pairs and
  `solver_algorithm_best_delta` weighted sum `53`), but it was still abandoned
  by `SCREENING_FAIL_WIN_RATE`.
- Round 2 used the feedback correctly at the hypothesis level, identifying
  baseline bootstrap as consuming too much runtime and proposing a no-baseline
  construction/local-search solver.
- Round 2 then failed before useful preview evidence could be retained because
  screening/runtime observations had already consumed almost the entire 64k
  APS observation budget. Contract preview was recorded as
  `result_too_large`, not as a deterministic pass/fail preview.

Current repair compacts feedback observations at the APS boundary, reserves
self-check observation budget through code phase, skips late feedback pulls
when that reserve is at risk, and tightens solver-design code scope to one
compact algorithm slice. This is a framework-control repair; it does not
change CVRP objective, feasibility, parser, splits, seeds, or Decision rules.

Previous analyzed no-op-feedback smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-noop-feedback-smoke-sonnet-2r-20260514T112251Z
model=claude-opus-4-6
problem=cvrp
protocol=formal
rounds_requested=2
rounds_completed=2 APS attempts, 0 screened experiments
time_limit_sec=60
agentic_session_timeout_sec=1800
git_commit=a653388
exit_code=0
status=max_rounds_exhausted
terminal_reason=code_generation_failed
analysis_doc=scion/docs/experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md
```

Summary:

- The run did not validate no-op micro-eval or screening feedback priority
  because neither round generated a patch.
- Both rounds stayed on `modify/solver_design` and code phase read the full
  selected surface, so boundary/tool plumbing was not the blocker.
- Both final `generate_patch` calls timed out after three provider attempts,
  with roughly 30k user characters plus a 9k system block.
- The hypotheses were over-broad: hybrid construction, baseline-bootstrapped
  iterative local search, and destroy/repair all in one patch.
- Current repair therefore treats solver-design timeout as a scope-control
  failure: the first code prompt is compact by default, and a timeout triggers
  one in-session compact semantic retry.

This run is superseded by the code-scope/feedback-budget smoke above.

Previous analyzed code-phase exploratory run after the 2-round smoke:

```text
run_root=/home/clawd/research/scion-experiments/v04-code-phase-slim-exploratory-sonnet-5r-20260513T190909Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=5
rounds_observed_before_termination=4
screened_experiments=3
time_limit_sec=60
agentic_session_timeout_sec=1800
git_commit=febca19
exit_code=143
status=manually_terminated_for_preview_hang
analysis_doc=scion/docs/experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md
```

Summary:

- The run confirmed the repaired whole-solver path could repeatedly reach
  screening under `solver_design`, but solver quality remained weak: screened
  candidates had median deltas `-152`, `0`, and `0`.
- The second and third screened candidates showed small positive tails
  (`2` wins each) while mostly tying the champion, so there is some signal but
  still no promotion-quality movement.
- The campaign then stopped producing artifacts after a successful code trace.
  The process remained CPU-active for more than two hours, indicating a
  post-code preview hang rather than an LLM-provider timeout.
- Root cause: C9c allowed unbounded boolean-flag loops because reassignment of
  the loop condition variable was mistakenly counted as collection shrinkage;
  preview execution also had no hard wall-time guard.
- Repair: C9c now rejects unbounded improvement-flag loops, CVRP synthetic
  preview hard-times out `solve(...)`, and APS hard-times out
  `proposal.contract_preview` before workspace materialization.
- Next run: a 1-2 round independent smoke should validate fail-closed preview
  behavior before any 5-8 round validation.

Previous analyzed direct full-solver run after validation-feedback repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-full-solver-subject-validation-feedback-repair-sonnet-8r-20260513T160209Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_observed_before_repair=5
screened_experiments=3
time_limit_sec=60
agentic_session_timeout_sec=1800
force_surface=none
status=manually_terminated_for_code_phase_agentic_repair
analysis_doc=scion/docs/experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md
```

Summary:

- The run stayed on the direct `solver_design` subject and generated
  `policies/solver_algorithm.py` patches for the screened candidates.
- Three candidates passed Contract and Verification and reached screening with
  16/16 valid pairs, but all failed `SCREENING_FAIL_WIN_RATE`.
- Round 1 was fast but worse than champion (`win_rate=0.0`,
  `median_delta=-98.5`). Rounds 2 and 3 mostly tied the repo-local ALNS+VNS
  champion (`win_rate=0.0`, `median_delta=0.0`).
- The next distinct population/recombination hypothesis failed at code
  generation after static prompts reached roughly 58k characters.
- Interpretation: boundary control is working, but code generation was still a
  one-shot static `generate_patch` call. The repair now adds a bounded
  code-phase tool loop and preview-feedback regeneration. The solver-quality
  problem remains separate: future candidates must use runtime as an
  optimization objective and produce a genuinely different algorithmic search,
  not just baseline warm-start plus small polish.
- Follow-up micro smoke from commit `f77b263` confirmed `code_phase=true`
  tool-selection traces and full selected-surface reads before patch
  generation, but final patch generation timed out and the retry ended on API
  balance exhaustion before Contract or screening. Do not start the planned
  5-8 round validation until a 1-2 round smoke reaches at least
  Contract/Verification with restored API balance.

Detailed analysis:
[`v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md`](../experiments/v0.4/v0.4-full-solver-subject-code-phase-agentic-repair-20260513.md)

Latest completed experiment before the direct solver-algorithm boundary repair:

```text
run_root=/home/clawd/research/scion-experiments/v04-algorithm-body-execution-semantics-sonnet-8r-20260512T173014Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed=8
screened_experiments=1
time_limit_sec=60
agentic_proposal=true
agentic_session_timeout_sec=1200
force_surface=none
exit_code=0
stopped_reason=circuit_breaker
finished_utc=2026-05-12T18:14:35Z
analysis_doc=scion/docs/experiments/v0.4/v0.4-algorithm-body-execution-semantics-repair-20260512.md
```

Summary:

- The run stayed on `solver_design` for all eight rounds
  (`action_locus_coverage.modify/solver_design=8`).
- Round 1 passed Contract and Verification and reached screening. It had
  16 attempted pairs, 15 valid pairs, one candidate timeout,
  `runtime_ratio_median=1.2115`, `runtime_delta_median_ms=10231`,
  and `runtime_regression_rate=1.0`; Decision abandoned it with
  `CANDIDATE_RUNTIME_FAILURE`.
- Runtime evidence confirmed the previous execution-semantics repair:
  `baseline_budget_policy="declared"` produced an effective baseline fraction
  of 0.7 with no hidden 0.75 guard; phase/component order followed the
  declared body; construction pool size was 2; route-pool source solutions
  were 14-20; and route-pool telemetry was present.
- Solver efficacy was still sparse. Only one observed pair recorded
  route-pool phase-best improvement
  (`main_search_component_phase_delta_sum.route_pool_recombination=3.0`,
  `main_search_route_pool_recombined_routes=8`), while
  `route_pool_recombination` consumed roughly 16s per observed pair.
- Rounds 2-8 failed before patch application because Contract preview failed
  with only generic failure text in campaign logs. The circuit breaker then
  ended the run after repeated proposal failures.

Interpretation: this run showed that the componentized `algorithm_body` path
was not enough. Runtime is already part of framework governance, but asking
Scion to optimize lifecycle-table knobs still kept the research object too
indirect.

Current repair: `solver_design` now targets the direct
`policies/solver_algorithm.py` full-algorithm hook and records
`solver_algorithm_*` evidence. The next short experiment should validate that
APS edits this algorithm subject directly and does not fall back to
component-policy or lifecycle-table optimization.

Detailed analysis:
[`v0.4-direct-solver-subject-adapter-repair-20260513.md`](../experiments/v0.4/v0.4-direct-solver-subject-adapter-repair-20260513.md)

Previous repair:
[`v0.4-algorithm-body-execution-semantics-repair-20260512.md`](../experiments/v0.4/v0.4-algorithm-body-execution-semantics-repair-20260512.md)

Previous analyzed/stopped run:

```text
run_root=/home/clawd/research/scion-experiments/v04-algorithm-body-lifecycle-sonnet-8r-20260512T145345Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed_before_termination=7_plus_partial_round_8
screened_experiments=4_complete_plus_partial_round_8
time_limit_sec=60
agentic_proposal=true
agentic_session_timeout_sec=1200
force_surface=none
stop_reason=manual_termination_for_execution_semantics_repair
analysis_doc=scion/docs/experiments/v0.4/v0.4-algorithm-body-execution-semantics-repair-20260512.md
```

Summary:

- The run validated that APS/codegen could declare `algorithm_body`, but the
  live semantics were still too shallow. Completed screenings had low sparse
  movement (`win_rate` values of 0.125, 0.0, 0.125, and 0.125 with
  `median_delta=0.0`), and the partial round-8 screening was again all ties
  with runtime regression.
- The decisive finding was an execution-layer mismatch: generated candidates
  could declare `baseline.time_fraction` around 0.55-0.60, but formal runtime
  silently applied the legacy 0.75 baseline floor. `phase_sequence`,
  `local_cleanup_after_recombination`, and `adaptive_component_budget` also
  did not sufficiently control the actual main-search schedule, and the
  bounded construction pool was not fed into route-pool recombination.
- The run was stopped before completion so the validation path could test a
  real algorithm-body execution contract rather than another audit-only
  exposure slice.

Interpretation: Scion had enough object-level context to stay on
`solver_design`, but it still did not have meaningful control over the full
CVRP solver body. The repair now makes declared baseline budget policy,
phase/component order, construction-pool route-pool input, cleanup coupling,
and adaptive component top-k visible in runtime behavior and required audit
evidence.

Detailed analysis:
[`v0.4-algorithm-body-execution-semantics-repair-20260512.md`](../experiments/v0.4/v0.4-algorithm-body-execution-semantics-repair-20260512.md)

## Current Repair Validation

The May 13 direct solver-algorithm boundary repair has passed focused and
boundary regression tests:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/test_cvrp_solver_operator_runtime.py \
  scion/scion/tests/test_cvrp_protocol_smoke.py \
  scion/scion/tests/test_protocol.py \
  scion/scion/tests/test_problem_bridge.py \
  scion/scion/tests/unit/core/test_proposal_pipeline.py \
  scion/scion/tests/unit/test_sprint_m.py \
  scion/scion/tests/test_contract.py -q

466 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1610 passed, 1 skipped
```

The first direct-solver-algorithm validation launch did not reach screening.
It selected free `solver_design` and generated direct
`policies/solver_algorithm.py` patches, which is the important positive
boundary signal, but then blocked before experiments after three proposal/code
failures:

- two candidates failed Contract on `time` imports plus bounded algorithm
  `while` patterns that the old complexity heuristic treated as uncapped;
- one candidate failed synthetic preview because preview/runtime
  `context.baseline` signatures disagreed on seed solution and
  `time_limit_sec` alias handling;
- the campaign marked both active branches `blocked_infra`, with
  `n_experiments=0`.

Follow-up repair: the direct solver context now accepts
`context.baseline(initial_solution=None, time_budget_sec=None,
time_limit_sec=None, params=None)`, `context.objective` remains a mapping but
supports lexicographic `(fleet_violation, total_distance)` comparison and
indexing, `context.objective_key`/`context.is_better` are exposed, `time` is
whitelisted for monotonic timing, `instance.depot` is documented, and C9c now
recognizes finite algorithm-body while loops with shrinking collections,
incrementing counters, or bounded-break/time guards. Replaying all five
rejected code traces from the blocked run now passes C8, C9c, and CVRP
synthetic preview locally.

Blocked diagnostic:

```text
run_root=/home/clawd/research/scion-experiments/v04-direct-solver-algorithm-boundary-sonnet-8r-20260513T084740Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed_before_block=0
screened_experiments=0
time_limit_sec=60
agentic_session_timeout_sec=1200
force_surface=none
launcher=nohup+setsid
pid=2618289
started_utc=2026-05-13T08:47:40Z
status=blocked_infra_after_proposal_failures
```

Follow-up validation is running from commit `8d8f01f`:

```text
run_root=/home/clawd/research/scion-experiments/v04-direct-solver-algorithm-api-repair-sonnet-8r-20260513T092116Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
time_limit_sec=60
agentic_session_timeout_sec=1200
force_surface=none
launcher=nohup+setsid
pid=2621512
started_utc=2026-05-13T09:21:16Z
git_commit=8d8f01f4efaabe6d7c2ac7d425caf354e47a9ae2
```

Initial status check: the run reached `stage=screening` on round 1 with
`target_file=policies/solver_algorithm.py`, so the previous C8/C9c/preview
blocker is cleared at least for the first generated direct-algorithm
candidate.

Completed status check:

- `total_rounds=8`, `n_experiments=3`, `stopped_reason=max_rounds_exhausted`;
- all 8 hypotheses stayed on `modify/solver_design` and targeted
  `policies/solver_algorithm.py`;
- 3 candidates reached screening with 16/16 valid pairs and non-empty
  `solver_algorithm_*` evidence;
- all 3 screened candidates failed `SCREENING_FAIL_WIN_RATE` with median
  total-distance delta 0.0;
- one screened candidate had runtime regression
  (`runtime_ratio_median=1.236`, `runtime_regression_rate=0.75`), while two
  were faster (`runtime_ratio_median=0.902` and `0.939`) but still lacked win
  rate;
- 2 verification failures were `V5_solution_consistency`;
- 3 code-generation attempts still failed C9c on runtime-guarded full
  algorithm `while` loops.

Important framework issue found during this check: runtime evidence reported
`solver_algorithm_active=true`, `solver_algorithm_solution_valid=true`, and
`solver_algorithm_errors=0`, but still left
`solver_algorithm_stop_reason="inactive"`. This was a default-audit overwrite
bug, not inactive solve behavior, and it visibly polluted later hypotheses
that tried to solve a nonexistent "still inactive" problem. Follow-up code now
sets active successful direct algorithms to
`solver_algorithm_stop_reason="completed"`, accepts `context.remaining_time()`
guarded C9c loops, and makes synthetic preview decrement remaining time so
preview cannot hang on the same runtime guards. Replaying the previously
C9c-rejected runtime-guarded code traces now passes C9c and CVRP preview
locally.

Validation after this follow-up repair:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/test_cvrp_solver_operator_runtime.py \
  scion/scion/tests/test_cvrp_protocol_smoke.py \
  scion/scion/tests/test_protocol.py \
  scion/scion/tests/test_problem_bridge.py \
  scion/scion/tests/unit/core/test_proposal_pipeline.py \
  scion/scion/tests/unit/test_sprint_m.py \
  scion/scion/tests/test_contract.py -q

468 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1612 passed, 1 skipped
```

Current preview-timeout repair validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m py_compile \
  scion/scion/contract/gate.py \
  scion/scion/problems/cvrp/adapter.py \
  scion/scion/proposal/agentic_session.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/test_contract.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/unit/test_agentic_proposal_tools.py \
  scion/scion/tests/unit/core/test_proposal_pipeline.py -q

329 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1618 passed, 1 skipped
```

Current prompt/tool-loop repair validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_proposal_tools.py -q

102 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/test_contract.py -q

198 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_g4_plumbing.py \
  scion/scion/tests/unit/test_sprint_j3_prompt_plumbing.py -q

29 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1619 passed, 1 skipped
```

Current aggressive compact-prompt repair validation:

```text
/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_agentic_proposal_tools.py -q

102 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_research_surfaces.py \
  scion/scion/tests/test_cvrp_adapter.py \
  scion/scion/tests/test_contract.py -q

198 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest \
  scion/scion/tests/unit/test_g4_plumbing.py \
  scion/scion/tests/unit/test_sprint_j3_prompt_plumbing.py -q

29 passed

/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q

1619 passed, 1 skipped
```

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-route-pool-recombination-telemetry-sonnet-8r-20260512T121501Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed_before_termination=1
screened_experiments=1
time_limit_sec=45
agentic_proposal=true
agentic_session_timeout_sec=900
force_surface=none
stop_reason=manual_termination_after_first_complete_screening_route_pool_telemetry_valid_but_zero_recombination_phase
analysis_doc=scion/docs/experiments/v0.4/v0.4-route-pool-recombination-telemetry-sonnet-terminated-20260512.md
```

Summary: validated route-pool execution/telemetry on 16/16 pairs, but
`main_search_route_pool_recombined_routes=0` and
`main_search_component_phase_delta_sum.route_pool_recombination=0.0` on all
pairs.

Detailed analysis:
[`v0.4-route-pool-recombination-telemetry-sonnet-terminated-20260512.md`](../experiments/v0.4/v0.4-route-pool-recombination-telemetry-sonnet-terminated-20260512.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-semantic-identity-guidance-sonnet-4r-20260512T020020Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=4
rounds_completed=4
screened_experiments=3
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=600
force_surface=none
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-solver-design-semantic-identity-guidance-sonnet-4r-20260512.md
```

Summary:

- The run launched from clean commit `8618917` and completed with
  `EXIT_CODE:0`.
- All persisted hypotheses and completed/partial APS outputs stayed on
  `solver_design` targeting `policies/main_search_strategy.py`. No
  component-policy fallback occurred.
- The repaired active-boundary trace used `active_problem_boundary_rule` with
  `allowed_surface_ids=["solver_design"]`; the invalid pre-run bug
  (`forced_surface_rule`, `allowed_surface_ids=[null]`) did not recur.
- All four persisted hypotheses supplied non-empty `selected_components` and
  `deep_components_selected`.
- Four code sessions completed with `schema_valid=true` and
  `contract_preview_passed=true`; no APS `output.json` contained
  `result_too_large`.
- Three candidates passed Contract and Verification, then failed screening with
  `win_rate` values `0.0`, `0.125`, and `0.0`; all had `median_delta=0.0`.
- The fourth candidate passed Contract but failed heavy Verification
  `V5_solution_consistency` because selected-surface runtime evidence had empty
  `main_search_deep_components_selected`.
- Candidate diversity improved: the run tried different baseline fractions,
  component sets, restart/perturbation patterns, rounds, and top-k values.

Interpretation: active boundary control, active-boundary tool guidance,
Contract-preview budget retention, and non-empty semantic identity are
live-validated. Solver-design quality remains the blocker: screened candidates
still had zero main-search phase-best movement, and the only nonzero win-rate
signal came with runtime regression.

Detailed analysis:
[`v0.4-solver-design-semantic-identity-guidance-sonnet-4r-20260512.md`](../experiments/v0.4/v0.4-solver-design-semantic-identity-guidance-sonnet-4r-20260512.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-active-boundary-contract-preview-budget-sonnet-4r-20260512T003103Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=4
rounds_completed=4
screened_experiments=2
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=600
force_surface=none
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-active-boundary-contract-preview-budget-sonnet-4r-20260512.md
```

Summary:

- The run launched from clean commit `4e88a2d` and completed with
  `EXIT_CODE:0`.
- All persisted hypotheses and completed/partial APS outputs stayed on
  `solver_design` targeting `policies/main_search_strategy.py`.
- Three code sessions completed with `schema_valid=true` and
  `contract_preview_passed=true`; no APS `output.json` contained
  `result_too_large`.
- Two candidates passed Contract and Verification, then failed screening with
  `win_rate=0.0` and `median_delta=0.0`; one candidate passed Contract but
  failed heavy Verification.
- The final hypothesis session failed closed before approval because schema
  preview found `novelty_signature.deep_components_selected=[]`.

Interpretation: active boundary control and Contract-preview budget retention
were live-validated. The next repair tightened semantic identity and
active-boundary tool guidance.

Detailed analysis:
[`v0.4-active-boundary-contract-preview-budget-sonnet-4r-20260512.md`](../experiments/v0.4/v0.4-active-boundary-contract-preview-budget-sonnet-4r-20260512.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-active-solver-design-boundary-sonnet-4r-20260511T180413Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=4
rounds_completed=4
screened_experiments=1
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=600
force_surface=none
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-active-solver-design-boundary-sonnet-4r-20260511.md
```

Summary:

- The run launched from clean commit `1c79c1e` and completed with
  `EXIT_CODE:0`.
- All persisted hypotheses and APS outputs stayed on `solver_design` targeting
  `policies/main_search_strategy.py`. No component-policy fallback occurred.
- The first candidate failed heavy Verification `V5_solution_consistency`.
- The second candidate passed Contract and Verification, then failed screening
  with `win_rate=0.0` and `median_delta=0.0`.
- The third hypothesis stayed on `solver_design`, but two code sessions failed
  closed because Contract preview was replaced by `result_too_large,
  tool_error` after APS had consumed about `44.3k/48k` observation chars.

Interpretation: active boundary control was validated. The remaining blocker
was APS preview-budget handling; this has since been repaired and validated in
the 2026-05-12 short diagnostic.

Detailed analysis:
[`v0.4-active-solver-design-boundary-sonnet-4r-20260511.md`](../experiments/v0.4/v0.4-active-solver-design-boundary-sonnet-4r-20260511.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-boundary-repair-sonnet-4r-20260511T164524Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=4
rounds_completed_before_termination=3
screened_experiments=2
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=600
force_surface=none
stop_reason=manual_termination_invalid_active_boundary
analysis_doc=scion/docs/experiments/v0.4/v0.4-solver-design-boundary-repair-sonnet-4r-terminated-20260511.md
```

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-solver-design-problem-object-sonnet-12r-20260511T140118Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=12
rounds_completed_before_termination=11
screened_experiments=9
time_limit_sec=30
agentic_proposal=true
agentic_session_timeout_sec=720
force_surface=none
stop_reason=manual_termination_invalid_control_loop
analysis_doc=scion/docs/experiments/v0.4/v0.4-solver-design-problem-object-sonnet-12r-terminated-20260511.md
```

Summary:

- The run was launched from clean commit `7d78f2f` and manually terminated with
  `EXIT_CODE:143` during round 12.
- Round 1 selected `solver_design` and targeted
  `policies/main_search_strategy.py`; APS Contract preview passed with
  `main_search_problem_object_evidence_alignment`.
- The first solver-design implementation failed heavy Verification
  `V5_solution_consistency`.
- After that, `solver_design` was treated as blacklisted. Subsequent hypotheses
  repeatedly stated that premise and selected component surfaces instead:
  `baseline_policy`, `route_local`, `algorithm_blueprint`,
  `destroy_repair_policy`, `acceptance_restart_policy`, `alns_vns_policy`,
  `route_pair_candidate_policy`, `construction_policy`,
  `neighborhood_portfolio`, and active `search_policy` when terminated.
- All 9 screened non-`solver_design` candidates passed Contract and
  Verification but failed screening with `win_rate=0.0` and `median_delta=0.0`.

Interpretation: this is not solver-efficacy evidence. It is a control-loop
failure: a single candidate verification failure must not globally blacklist
the top-level problem-object surface. APS should retry `solver_design` with a
different lifecycle implementation and keep component policies as
implementation/attribution hooks, not fallback research goals.

Detailed analysis:
[`v0.4-solver-design-problem-object-sonnet-12r-terminated-20260511.md`](../experiments/v0.4/v0.4-solver-design-problem-object-sonnet-12r-terminated-20260511.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-forced-destroy-repair-policy-enum-interface-sonnet-8r-20260511T114551Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds_requested=8
rounds_completed=8
time_limit_sec=20
agentic_proposal=true
agentic_session_timeout_sec=480
force_surface=destroy_repair_policy
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-forced-destroy-repair-policy-enum-interface-sonnet-8r-20260511.md
```

Summary:

- The run completed all 8 requested rounds and stopped by
  `max_rounds_exhausted`; `circuit_breaker_tripped=false`.
- All 8 hypotheses targeted `modify/destroy_repair_policy` and
  `policies/destroy_repair_policy.py`. No forced-surface violation appeared in
  `campaign_summary.json`.
- The forced task line remains validated in real traces: all 8 hypothesis
  traces contained the forced `destroy_repair_policy` task line, and 0
  contained the old generic "Choose a research surface from ..." task line.
- The enum-interface repair is validated: all 7 completed code sessions passed
  `proposal.contract_preview`, and `verification_failure_breakdown={}`.
- Solver efficacy still failed: 7 candidates reached screening and all failed
  `SCREENING_FAIL_WIN_RATE`; all had `win_rate=0.125` and `median_delta=0.0`.
- One round failed at hypothesis Contract with `C10_novelty` because the
  structured novelty signature omitted required destroy/repair identity fields.
- Destroy/repair attribution was complete but non-beneficial across 112
  screened pairs: 7,168 attempts, 7,168 repair-budget units used, zero accepted
  current/recovery/phase-best moves, and
  `destroy_repair_phase_delta_sum=0.0`.
- The valid policies exercised both `regret_2` and `cheapest`, both allowed
  destroy selectors, and max-destroy/budget patterns from 2..10 and 6..16. The
  mechanism still produced only `repair_budget_exhausted` or
  `repair_produced_no_improvement`.

Interpretation: `destroy_repair_policy` is no longer blocked by prompt routing,
selector implementation, or selector enum clarity. It is exhausted as a forced
diagnostic target for the current solver-owned mechanism. More importantly,
this run confirms that continuing to force one policy hook at a time is the
wrong optimization strategy. The next step is the problem-object adaptation
pivot, not another forced policy run.

Detailed analysis:
[`v0.4-forced-destroy-repair-policy-enum-interface-sonnet-8r-20260511.md`](../experiments/v0.4/v0.4-forced-destroy-repair-policy-enum-interface-sonnet-8r-20260511.md)

Previous analyzed run:

```text
run_root=/home/clawd/research/scion-experiments/v04-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511T092047Z
model=claude-sonnet-4-6
problem=cvrp
protocol=formal
rounds=8/8
time_limit_sec=20
agentic_proposal=true
agentic_session_timeout_sec=360
force_surface=destroy_repair_policy
stop_reason=max_rounds_exhausted
analysis_doc=scion/docs/experiments/v0.4/v0.4-forced-destroy-repair-policy-selector-repair-sonnet-8r-20260511.md
```

## Validation

Latest solver-design problem-adaptation contract validation:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_adapter.py::test_cvrp_main_search_strategy_preview_accepts_lifecycle_roles_and_runtime_targets scion/scion/tests/test_cvrp_adapter.py::test_cvrp_main_search_strategy_preview_rejects_novelty_signature_in_plan scion/scion/tests/unit/test_research_surfaces.py::test_cvrp_main_search_strategy_problem_adaptation_drives_order_and_thresholds scion/scion/tests/unit/test_research_surfaces.py::test_context_exposes_search_policy_surface_and_modify_when_no_operator_pool scion/scion/tests/test_proposal_validation.py::test_hypothesis_runtime_intent_fields_parse_and_format
```

```text
5 passed in 0.42s
```

Latest algorithm-body execution-semantics focused validation:

```bash
cd scion && /home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests/test_cvrp_adapter.py scion/tests/test_cvrp_solver_operator_runtime.py -q
```

```text
109 passed in 15.27s
```

Latest boundary/protocol regression subset:

```bash
cd scion && /home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests/unit/test_research_surfaces.py scion/tests/unit/test_agentic_proposal_tools.py scion/tests/test_protocol.py -q
```

```text
217 passed in 3.91s
```

Latest full Scion test suite:

```bash
cd scion && /home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/tests -q
```

```text
1601 passed, 1 skipped in 69.52s
```

Previous related proposal/CVRP subset:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/test_proposal_validation.py
```

```text
133 passed in 4.66s
```

Previous full Scion test suite:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests
```

```text
1593 passed, 1 skipped in 67.54s
```

Latest route-pool quality/boundary validation:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_solver_operator_runtime.py -k 'route_pool'
```

```text
7 passed, 51 deselected in 0.51s
```

Latest main-search route-pool telemetry contract validation:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/unit/test_research_surfaces.py
```

```text
182 passed in 29.81s
```

Previous main-search route-pool/execution validation:

```bash
PYTHONPATH=scion /home/clawd/miniconda3/envs/claw/bin/python -m pytest -q scion/scion/tests/test_cvrp_solver_operator_runtime.py
```

```text
53 passed in 12.49s
```

Latest focused phase-benefit / forced-surface validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/test_research_surfaces.py -q
```

```text
189 passed in 12.30s
```

Latest selected-surface/proposal boundary validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_protocol.py::test_run_experiment_preserves_selected_surface_required_runtime_metrics scion/scion/tests/test_cvrp_protocol_smoke.py scion/scion/tests/test_cvrp_solver_vrp_smoke.py scion/scion/tests/unit/core/test_proposal_pipeline.py -q
```

```text
39 passed in 12.58s
```

Broader CVRP/protocol subset:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_*.py scion/scion/tests/unit/evidence/test_cvrp_*.py scion/scion/tests/test_protocol.py scion/scion/tests/unit/test_agentic_proposal_tools.py -q
```

```text
227 passed in 34.29s
```

Latest APS/CVRP optimization validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/test_problem_bridge.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_adapter.py -q
```

```text
252 passed in 18.19s
```

Latest focused APS preview-budget validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py -q
```

```text
86 passed in 1.97s
```

Latest forced-prompt narrowing validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_sprint_j3_prompt_plumbing.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py -q
```

```text
198 passed in 3.03s
```

Latest CVRP destroy/repair selector/proposal validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/unit/test_sprint_j3_prompt_plumbing.py scion/scion/tests/unit/test_research_surfaces.py scion/scion/tests/unit/test_agentic_proposal_tools.py scion/scion/tests/unit/core/test_proposal_pipeline.py -q
```

```text
285 passed in 18.53s
```

Latest direct solver-design smoke and repair:

- Independent smoke:
  `/home/clawd/research/scion-experiments/v04-code-phase-aggressive-compact-smoke-sonnet-2r-20260514T061603Z`
  completed 2/2 rounds on commit `14f7f29`.
- Code-generation prompt compaction worked: both code calls completed with
  roughly 30k-33k user-prompt characters and no raw `content_preview` payloads.
- Round 1 passed Contract/Verification and reached screening, but had
  `win_rate=0.0`, `median_delta=0.0`, and `runtime_ratio_median=0.343`.
- Round 2 failed heavy Verification at `V5_solution_consistency`; replaying the
  generated solver in the correct workspace exposed the underlying candidate
  error `solve failed: list index out of range`.
- Runtime audit now reports `solver_algorithm_errors` as a dedicated
  `solver_algorithm_runtime_error` instead of burying full-solver hook failures
  behind generic surface evidence failures.
- CVRP solver-design preview now runs the hook on a controlled-canary-shaped
  synthetic instance and uses a 5s synthetic time window under the existing 2s
  wall-clock timeout. The exact failed round-2 solver is now rejected during
  Contract preview with `synthetic_preview_canary_5: solve raised during
  synthetic preview: list index out of range`.

Latest validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/test_cvrp_adapter.py scion/scion/tests/test_cvrp_solver_operator_runtime.py scion/scion/tests/test_verification.py -q
```

```text
209 passed in 21.75s
```

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py -q
```

```text
102 passed in 2.99s
```

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
```

```text
1621 passed, 1 skipped in 73.91s
```

Latest code self-check repair:

- Independent smoke:
  `/home/clawd/research/scion-experiments/v04-solver-preview-repair-smoke-sonnet-2r-20260514T073717Z`
  completed 2/2 rounds on commit `c011ac2` with `n_experiments=0`.
- Round 1 failed after three code-generation provider timeouts.
- Round 2 failed closed in Contract preview: first on
  `C9c_complexity_bound` for an uncapped `while` loop, then on
  `C6_ast_syntax` at line 341 after repair.
- The repair response's own `test_hint` said the generated
  `_destroy_repair_regret` code still had a syntax error needing a fix, yet APS
  still passed it to Contract preview.
- APS now treats such self-reported unresolved code issues as code self-check
  failures before Contract preview. It may spend the one configured code-repair
  attempt with explicit `agentic_code_self_check_feedback`; if the repaired
  patch still self-reports unresolved syntax/compile/incomplete/TODO issues,
  the session fails closed as `code_generation_failed`.
- Code self-check repair and Contract-preview repair now share
  `max_code_repair_attempts`.

Latest focused validation:

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests/unit/test_agentic_proposal_tools.py -q
```

```text
104 passed in 2.88s
```

```bash
/home/clawd/miniconda3/envs/claw/bin/python -m pytest scion/scion/tests -q
```

```text
1623 passed, 1 skipped in 74.48s
```

Latest solver-design module-subject repair validation:

- `policies/baseline_algorithm.py` is now a stable entrypoint backed by the
  branch-owned `policies/baseline_modules/` package.
- `context.read_surface("solver_design")` includes bounded support-module
  previews for the default entrypoint read; target-specific module reads stay
  under tool result budgets.
- Focused CVRP/APS/Contract subset:
  `404 passed in 49.03s`.
- Full Scion suite:
  `1669 passed, 1 skipped in 89.96s`.
- Direct CVRP canary with `SCION_SELECTED_SURFACE=solver_design` loaded
  `policies/baseline_algorithm.py`, returned active solver-design telemetry,
  and had `solver_algorithm_errors=0`.

Latest solver-design no-op feedback repair:

- Independent smoke:
  `/home/clawd/research/scion-experiments/v04-code-self-check-smoke-sonnet-2r-20260514T091556Z`
  completed 2/2 rounds on commit `06e9365` with `n_experiments=2`,
  `champion_version=1`, `stopped_reason=max_rounds_exhausted`, and exit code
  `0`.
- Both candidates were valid and active under `solver_algorithm`, but both
  were abandoned by `T4: win_rate < 0.3`.
- Round 1: 3 wins, 1 loss, 12 ties; median runtime ratio about `1.234x`;
  several formal cases hit `time_limit`.
- Round 2: 1 win, 2 losses, 13 ties; median runtime ratio about `1.063x`;
  `solver_algorithm_move_attempts` was positive but
  `solver_algorithm_accepted_moves` and `solver_algorithm_best_delta` were
  zero on nearly all pairs.
- The repair adds a CVRP synthetic improvement-trap micro-eval to Contract
  preview for baseline-seeded `solver_design` patches and improves runtime
  feedback ordering so solver move/no-op telemetry reaches the next code and
  hypothesis prompts.

## Next Actions

P1:

- Run a 1-2 round smoke after the latest C9c/smoke permission repair. The
  first gate is that the 6-round failure modes no longer recur: bounded
  `while len(collection) < cap/q` loops should pass Contract preview, true
  unbounded `while improved` loops should still fail, and
  `proposal.algorithm_smoke` should apply patches inside copied read-only
  champion snapshots without `PermissionError`.
- Run a 1-2 round smoke after the solver-design module-subject repair. The
  first gate is that APS can legally choose a focused
  `policies/baseline_modules/*.py` target, static preview defers module
  interface checks to workspace smoke, and `proposal.algorithm_smoke` runs the
  stable `baseline_algorithm.py::solve(...)` entrypoint after applying a module
  patch.
- Run and analyze the repaired algorithm-body execution diagnostic. The first
  gate is not promotion; it is whether APS-generated `solver_design`
  candidates use the full CVRP lifecycle semantics now that baseline budget,
  phase order, construction-pool reuse, cleanup coupling, and adaptive
  component budgets have real runtime effect.
- Run a short independent smoke after the solver-design preview/audit repair.
  The first gate is that bad full-solver candidates fail in Contract preview
  with concrete synthetic runtime diagnostics instead of reaching heavy
  Verification with opaque V5/no-output symptoms.
- Re-run the short smoke after the code self-check repair. The first gate is
  that generated patches whose own `test_hint` admits unresolved syntax or
  implementation issues fail before Contract preview or are repaired once with
  explicit self-check feedback.
- Re-run a 1-2 round smoke after the no-op feedback repair. The first gate is
  that the next hypothesis/code phase explicitly reasons from
  `solver_algorithm_accepted_moves`, `solver_algorithm_best_delta`, and runtime
  regression instead of proposing another baseline-heavy wrapper.
- Keep route-pool telemetry as evidence inside that lifecycle:
  `main_search_route_pool_sample_count`,
  `main_search_route_pool_recombined_routes`, and
  `main_search_component_phase_delta_sum.route_pool_recombination` should
  remain first-class feedback fields.
- If the short diagnostic still produces only shallow knob reshuffles, the
  next repair should expose a more direct package-owned algorithm-body subject
  for Scion to study, not another singleton mechanism policy.
- Do not add another forced singleton mechanism-policy diagnostic to work
  around solver-design quality.
- Stop forced single-policy diagnostics for now, including
  `route_pair_candidate_policy`.

P2:

- Persist actual `DecisionFeatures` lineage and improve soft-abandon decision
  provenance.
- Move remaining problem-specific runtime-field heuristics out of proposal
  context.
- Consider a typed-collaborator pass for campaign composition to reduce
  callback coupling.
- Add a dedicated CLI/readiness command for formal campaign closeout.
- Fix model-facing tool-selection prompt sanitization that can render
  `feedback.query_holdout_summary` as an empty allowed tool name.

## Remaining Risks

2026-05-31 update: the P1/P2 observability validation run at
`/home/clawd/research/scion-experiments/v04-v3-p1p2-observability-gpt55-4r-20260531T080550Z-claw`
completed 4/4 effective rounds with no infrastructure failures and verified the
low-win/loss-heavy branch lifecycle repair: a `1W/3L/8T` non-positive-CI branch
was soft-abandoned instead of retained as weak-positive. The run also exposed a
stricter policy need for balanced mixed evidence: `3W/3L/6T` with CI crossing
zero should be preserved only as marginal follow-up evidence, not as an
`active_weak_positive` exploit target. Scion core now has a generic marginal
screening tier/reason, retained hypothesis statuses are clearer, and code retry
failure artifacts include explicit attempt/session indexing for audit joins.
The follow-up 6-round branch-lifecycle run verified that mixed/no-effect
branches are no longer promoted to weak-positive status. Remaining P2 audit
wording has now been tightened: retained branch reasons distinguish
weak-positive, marginal mixed, neutral no-effect, and telemetry/runtime
diagnostic signals, and summary/lineage/screening feedback expose separate
gate-observation and lifecycle-action reason-code groups while preserving the
backward-compatible `decision_reason_codes`. Future experiment reviews should
be branch-centric: reconstruct branch lineage, current-head health, and
explore/exploit trajectory before deciding whether to expand rounds.

2026-05-22 update: the construction/Shaw validation run is documented in
[`v0.4-v3-construction-shaw-sonnet-3r-postrun-20260522.md`](../experiments/v0.4/v0.4-v3-construction-shaw-sonnet-3r-postrun-20260522.md).
It completed 3 effective screening rounds with no construction/Shaw false
positive recurrence and no P0 findings. The remaining P1 provider noise was
kept inside the CVRP problem package: the random-removal matcher now allows
geographic/spatial cluster variants that explicitly contrast existing uniform
random removal, and regret-repair premise feedback now describes semantic
mischaracterization rather than only "missing" repair. A design-first cleanup
also split CVRP `solver_design` manifest/smoke-effort interpretation into the
problem-owned `solver_design/` package, and split retry-round accounting tests
by explore-pipeline versus campaign-loop responsibility. The full unit suite
passes at `1007 passed`.

The follow-up solver-design provider P1 validation is documented in
[`v0.4-v3-solver-design-provider-p1-sonnet-3r-postrun-20260522.md`](../experiments/v0.4/v0.4-v3-solver-design-provider-p1-sonnet-3r-postrun-20260522.md).
It completed 3/3 effective screening rounds with `qblocks=0`; the first
screened branch was a geographic/spatial cluster destroy variant and was no
longer misclassified as missing random/Shaw removal. The remaining P1 repairs
add a generic provider hook for static algorithm-smoke quality checks while
keeping domain semantics in CVRP: CVRP now rejects approved-hypothesis/code
semantic drift for cross-route double-bridge claims, rejects non-causal destroy
effect telemetry recorded inside destroy helpers, and separates regret repair
semantic mischaracterization from true missing-regret claims. The active solver
fact packet now states the regret score/tie-break semantics used by
`_regret_insertion`.

- CVRP `solver_design` is now validly routed, self-checked, and contract-valid
  as a direct full-algorithm hook. It has not yet shown experiment-level solver
  efficacy under the new boundary.
- CVRP's current research-surface set still contains many component hooks. It
  risks optimizing whatever hook is exposed unless APS keeps prioritizing the
  problem-object solver-design boundary.
- APS can still produce shallow solver-design hypotheses that wrap old helper
  behavior. The next validation must check whether Scion actually edits and
  reasons about the full algorithm subject while respecting the fixed
  objective/constraint boundary.
- Deep-surface runtime attribution is improved for `alns_vns_policy` and
  mechanically complete for `destroy_repair_policy`, but still thin for
  `acceptance_restart_policy` and `route_pair_candidate_policy`.
- `destroy_repair_policy` now has validated prompt routing, selector semantics,
  enum clarity, and complete runtime attribution, but no useful movement in the
  current solver-owned mechanism.
- Proposal preview and runtime audit can still disagree for strategies that
  are syntactically valid but semantically incompatible with diagnostic
  expectations.
- APS prompt projection still needs a low-risk follow-up to label or suppress
  repeated low-value read receipts more explicitly without hiding full target
  or branch-current source from code-generation prompts.
- Runtime isolation is resource-limited and env-sanitized, but not yet a full
  read-only mount sandbox.
- Stale/reconcile semantics still need a dedicated v3-aligned review.
- Legacy/no-adapter V8 objective-only comparison remains compatibility-only.

## History

- Full historical status log:
  [`v0.4-history.md`](v0.4-history.md)
- Experiment index:
  [`../experiments/v0.4/README.md`](../experiments/v0.4/README.md)
- Current audit guide:
  [`../../reports/v04-audit-agent-experiment-guide-20260609.md`](../../reports/v04-audit-agent-experiment-guide-20260609.md)
- Latest framework reviews:
  [`../../reports/v04-core-framework-review-20260611.md`](../../reports/v04-core-framework-review-20260611.md),
  [`../../reports/v04-core-framework-code-review-20260611.md`](../../reports/v04-core-framework-code-review-20260611.md)
- Current forward roadmap:
  [`../../design/v0.5-evidence-uplift-roadmap.md`](../../design/v0.5-evidence-uplift-roadmap.md)
- Problem-object adaptation pivot:
  [`problem-object-adaptation-pivot.md`](../engineering/problem-object-adaptation-pivot.md)

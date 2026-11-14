# Staged Evaluation And Runtime Telemetry

Date: 2026-06-02

This note records the generic Scion changes derived from the 16R no-effect
parking run, the external APS control, and the direct VRP research control.
The implementation keeps Scion core problem-agnostic: protocol code carries
stage names, evidence freshness, and summary schemas; problem adapters own
phase bucket names and runtime field meanings.

## Goals

- Support a quick pre-screen followed by broad screening or validation without
  hard-coding a problem family.
- Prevent runtime-tie promotion from using cached champion runtime evidence.
- Carry phase-level runtime telemetry summaries through protocol results and
  reports.
- Provide a generic hook for cheap smoke/pre-screen diagnostics of expensive
  candidate mechanisms without treating noisy smoke timing as a hard failure.

## Protocol Schema

`ProtocolConfig.evaluation_pipeline` can now describe named staged evaluation
steps. Each `EvaluationStageConfig` declares:

- `name`: stable report/scheduler identifier.
- `role`: `quick_prescreen`, `broad_screening`, `screening`, `validation`,
  `frozen_holdout`, or `diagnostic`.
- `split`, `n_cases`, `n_seeds`, `expose`, and `gate`.
- `hard_failure`: whether the stage may fail the candidate.
- `smoke_runtime_policy`: `diagnostic_only` by default.

If no staged pipeline is configured, `ProtocolConfig.evaluation_stage_summary()`
projects the legacy screening/validation/frozen shape. This gives reports and
future schedulers a single summary surface before formal quick-stage execution
is wired in.

## Runtime Freshness

`ProtocolConfig.runtime.champion_runtime_policy` supports:

- `allow_cached`: current cache behavior.
- `fresh_required_for_runtime_tie`: cache may be used, but a tie-preserving
  runtime candidate with cached champion samples and insufficient fresh runtime
  pairs is marked `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`.
- `fresh_always`: disables champion cache for the protocol run.

Protocol results now carry `runtime_evidence_status` in addition to
`runtime_confidence`. `runtime_confidence=low_cached_champion` describes source
quality; `runtime_evidence_status=fresh_champion_required` describes the gate
action needed before runtime-tie promotion can be interpreted.

## Phase Telemetry

Problem adapters may declare `phase_runtime_fields` and
`phase_telemetry_buckets` on `ResearchSurfaceEvidenceSpec`. The protocol layer
summarizes candidate runtime mappings from those fields into
`candidate_phase_telemetry_summary`:

- declared runtime fields and buckets,
- candidate/runtime observed pair counts,
- per-bucket observed count, total ms, min/max ms, and zero/nonzero counts,
- whether each observed bucket was adapter-declared.

Core does not interpret bucket names. A CVRP adapter may choose buckets such as
construction or local search; another problem can use different names.

## Expensive Smoke Hook

`ProtocolConfig.smoke_prescreen` is the configuration entry point for cheap
diagnostics before formal screening. Its default `runtime_noise_policy` is
`diagnostic_only`. A future runner should record smoke results as branch-local
proposal feedback and protocol-stage diagnostics, not as formal validation
evidence unless the adapter explicitly declares a hard-failure policy.

## Remaining Implementation

- Wire `evaluation_pipeline` into the campaign evaluation scheduler so a
  configured quick stage can run before broad screening/validation.
- Add an orchestration hook that reruns champion fresh when protocol returns
  `RUNTIME_TIE_FRESH_CHAMPION_REQUIRED`.
- Add an adapter-owned expensive-mechanism classifier or candidate tag source
  for smoke pre-screen selection.
- Render `evaluation_stage_summary()` in the operator-facing run reports once
  the reporting layout is selected.

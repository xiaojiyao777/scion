# 05 - Runtime Smoke And Experiments

## Reviewed Runtime Path

- `proposal.algorithm_smoke` materializes temporary candidate and champion workspaces for declared `solver_design` patches.
- Smoke uses the configured canary and selected screening cases.
- Formal Protocol runs candidate and champion solvers with the selected surface.
- Runtime audit enforces required runtime fields for the exact selected surface.

## Findings

### F-04 - `solver_algorithm` alias skips solver-design smoke and required runtime fields

- Severity: High
- Files:
  - `scion/scion/proposal/solver_design_smoke.py:63`
  - `scion/scion/problems/cvrp/solver.py:8472`
  - `scion/scion/runtime/audit.py:247`
  - `scion/scion/problems/cvrp/problem-v1.yaml:851`
- Problem: Runtime smoke is exact-name gated on `solver_design`; runtime preferred entrypoint loading is exact-name gated on `SCION_SELECTED_SURFACE == "solver_design"`; runtime audit required fields are exact-name looked up. ContractGate accepts `solver_algorithm` as solver-design compatibility, but the runtime layers do not.
- Trigger path: A selected-surface alias of `solver_algorithm` causes `_runtime_algorithm_smoke_preview` to return `None`, `_solver_design_runtime_enabled()` to return false unless the env flag is manually set, and `declared_surface_required_runtime_fields` to return an empty tuple because `problem-v1.yaml` has no surface named `solver_algorithm`.
- Impact: This can produce a candidate that is statically treated as solver-design but runtime-audited as no declared surface. It is a consistency bug even if the current CLI normally uses `solver_design`.
- Suggested fix: Centralize selected-surface normalization. Add smoke and runtime audit tests for alias normalization, or delete the alias from ContractGate and force all compatibility file edits through `change_locus="solver_design"`.

### F-10 - Smoke instance resolution trusts absolute paths and ambient data root

- Severity: Medium
- Files:
  - `scion/scion/proposal/solver_design_smoke.py:557`
  - `scion/scion/proposal/solver_design_smoke.py:565`
  - `scion/scion/proposal/solver_design_smoke.py:570`
  - inspected launch script: `/home/clawd/research/scion-experiments/v04-api-manifest-sonnet-6r-20260517T042338Z/launch.sh`
- Problem: `_resolve_smoke_instance_path` accepts absolute paths and falls back to `SCION_PROBLEM_DATA_ROOT` when the case is not found in workspace/base workspace. The 6-round launch script sets `SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp`.
- Trigger path: If a split manifest or seed ledger contains an absolute path, smoke uses it directly. If relative data is missing locally, smoke reads from ambient `SCION_PROBLEM_DATA_ROOT`.
- Impact: This is probably intentional for formal CVRPLIB data, but it weakens reproducibility and sandbox reasoning. A smoke result depends on an environment variable outside the campaign artifact, and absolute paths are not bound to a declared problem data root.
- Suggested fix: Resolve all smoke cases through a declared, recorded data-root manifest. Reject absolute paths unless they are under the audited problem data root. Record the resolved root and a case-file digest in the smoke payload.

### F-08 - Champion failure branches do not emit progress

- Severity: Medium
- Files:
  - `scion/scion/protocol/experiment.py:627`
  - `scion/scion/protocol/experiment.py:658`
  - `scion/scion/protocol/experiment.py:761`
  - `scion/scion/protocol/experiment.py:793`
  - `scion/scion/core/evidence_recorder.py:163`
- Problem: Champion process failure and champion audit failure append raw failure metrics and write a metrics snapshot, but do not emit progress. Candidate failure branches do emit progress.
- Trigger path: A champion-side failure during a long run will update metrics JSON but not refresh `status.json` progress until later.
- Impact: Background status can look stale exactly during exceptional conditions. This does not explain the inspected 6-round status by itself, but it is a reproducible branch-level observability gap.
- Suggested fix: Refactor failure recording into one helper that writes metrics and emits progress for all candidate and champion failure branches.

### F-09 - Solver-design telemetry is not first-class in generic protocol observations

- Severity: Medium
- Files:
  - `scion/scion/protocol/experiment.py:995`
  - `scion/scion/protocol/experiment.py:1000`
  - `scion/scion/protocol/experiment.py:1035`
  - `scion/scion/protocol/experiment.py:1194`
- Problem: Protocol feedback remains operator/policy oriented in generic observation structures. It does not count solver-design stop reasons, search iterations, move attempts, accepted/improving moves, or baseline helper calls unless selected-surface required fields are threaded into the runtime summary.
- Trigger path: Solver-design candidates that execute successfully but do little work can have important telemetry in raw runtime output while generic `candidate_runtime_stop_reasons` and failure categories remain sparse.
- Impact: Decision uses statistical gates, but follow-up APS feedback and campaign summaries can under-explain why a solver-design candidate was abandoned or weak.
- Suggested fix: Add solver-design counters and stop reasons to `_candidate_runtime_observation`, and include bounded solver algorithm events in runtime summaries.

## Experiment Evidence

### 3-round experiment

Path: `/home/clawd/research/scion-experiments/v04-api-manifest-sonnet-3r-20260517T034512Z/campaign`

Observed:

- `status.json` exists and reports `n_steps: 3`, `stopped_reason: max_rounds_exhausted`.
- `campaign_summary.json` exists with 3 steps.
- All 3 steps had `decision: abandon`.
- All 3 decision reason codes were `SCREENING_FAIL_WIN_RATE`.
- Protocol summaries included `selected_surface: solver_design`.
- APS session refs include `schema_version: agentic-proposal-session.v1`, `tainted: true`, `artifact_ref`, and `transcript_digest`.

### 6-round background experiment

Path: `/home/clawd/research/scion-experiments/v04-api-manifest-sonnet-6r-20260517T042338Z/campaign`

Observed at inspection time:

- `status.json` exists and reports `n_steps: 4`.
- `campaign_summary.json` did not exist yet.
- SQLite WAL files were present (`scion.db-wal`, `scion.db-shm`), consistent with an active or recently active run.
- The run root had `pid.txt`, `command.txt`, `launch.sh`, and `run.log`.
- `run.log` showed a candidate rejected before code generation due to APS contract preview failing C9c on an uncapped while loop.

## Positive Evidence

- `proposal.algorithm_smoke` uses temporary materialized workspaces and does not mutate champion/campaign code.
- Recent formal runs used `selected_surface: solver_design`.
- C9c actively rejected an unbounded while loop in the inspected 6-round background log.


# Evidence Lineage

## Scope / Sources

Sources read: `scion/scion/core/evidence_recorder.py`, `models.py`, `campaign.py`, `decision_finalizer.py`, `promotion_lifecycle.py`, `promotion_service.py`, `scion/scion/lineage/registry.py`, `champion_store.py`, `branch_store.py`, `scion/scion/evidence/final_evidence_refs.py`, `formal_readiness.py`, `final_quality.py`, and CVRP evidence helpers under `scion/scion/evidence/`.

## Evidence Objects

The main in-memory evidence object is `StepRecord` in `scion/scion/core/models.py`. It records one completed proposal/evaluation cycle or early failure:

- round number and branch id;
- hypothesis and optional patch;
- contract/verification pass booleans;
- optional `ProtocolResult`;
- optional deterministic `Decision`;
- failure stage/detail for early exits;
- verification detail and archive ref;
- optional cache stats;
- hypothesis id;
- decision reason codes.

`decision=None` is meaningful: the step did not reach the decision engine. Contract/proposal/code/workspace/verification failures should keep `decision=None`.

`ProtocolResult` contains stage, stats, gate outcome, reason codes, exposed
summary, raw metrics ref, case ids, seed set, selected surface, screening-only
feedback, and an optional bounded candidate surface runtime summary derived
from problem-declared required runtime fields.

## EvidenceRecorder Flow

`EvidenceRecorder` is the artifact boundary in `scion/scion/core/evidence_recorder.py`.

Runtime flow:

1. `CampaignManager._record_step()` calls `EvidenceRecorder.record_step()`.
2. `record_step()` appends the `StepRecord` to `CampaignManager._step_history`.
3. If search memory is present, it updates `CampaignSearchMemory` from that step.
4. Progress/status updates are written through `StatusReporter`.
5. `record_step_lineage()` builds and writes experiment/decision rows into `LineageRegistry`.
6. `write_campaign_summary()` serializes campaign-level summary and per-step details.

The recorder intentionally preserves existing artifact shapes while moving artifact logic out of `CampaignManager`.

## Lineage Registry

`LineageRegistry` in `scion/scion/lineage/registry.py` owns SQLite persistence. It creates and migrates tables:

- `experiment_events`
- `branches`
- `hypotheses`
- `champions`
- `weight_optimizations`

`record_event()` inserts experiment-like events. `record_decision()` inserts a separate decision row. The design is append-only for experiment and decision events.

`EvidenceRecorder.build_step_lineage_event()` writes event fields such as branch/champion versions, code hash, patch file/action, hypothesis text, contract/verification/canary result, stage, case ids, seeds, raw metrics ref, screening stats, model/protocol ids, and serialized decision metadata. Runtime guard evidence and protocol runtime stats are nested inside `decision_features_json`.
The selected surface is included as bounded evidence metadata; selected-surface
runtime field values remain reporting evidence and are not DecisionFeatures.

## ChampionStore and Promotion Evidence

`ChampionStore` persists current and historical champion state in the shared SQLite DB. Each champion row is keyed by `(version, weight_revision)` and includes operator pool JSON, solver config hash, snapshot path/hash, promotion experiment id, promoted timestamp, and weight revision.

Promotion flow:

1. `DecisionFinalizer` sees `Decision.PROMOTE`.
2. It asks `PromotionLifecycleService` to prepare a `PromotionPlan`.
3. `PromotionService.prepare()` copies/freezes the candidate workspace into a champion snapshot and reads `registry.yaml`.
4. `PromotionService.commit()` persists champion, updates in-memory champion, transitions branch, marks other active branches stale, persists branch state, and records champion evolution.
5. `DecisionFinalizer` records promotion lineage with a promotion event id.
6. Optional weight optimization runs sync or async and records weight optimization lineage.

This means champion state is not just a branch decision; it is a persisted snapshot plus DB anchor.

## Status and Summary Artifacts

`status.json` is a live snapshot written by `EvidenceRecorder.write_status()`. It combines campaign state, last `StepResult`, stopped reason, and current protocol progress.

`campaign_summary.json` is written by `EvidenceRecorder.write_campaign_summary()`. It includes:

- campaign id, rounds, champion version/revision, stopped reason;
- cache stats;
- verification failure breakdown;
- action/locus coverage;
- family coverage;
- budget utilization;
- stagnation signals and diagnostics;
- frozen budget snapshot;
- formal readiness status;
- optional final evidence refs;
- active branch snapshot;
- per-step summaries.

Per-step summaries include protocol stats, runtime stats, reason codes, raw
metrics refs, selected surface, bounded selected-surface runtime field
summaries, and screening case feedback summaries when present.

## Final Evidence Refs and Readiness

`final_evidence_refs.py` lets callers attach final quality package references to an `EvidenceRecorder` without changing `StepRecord`. The helper reads package/result metadata already in memory and records stable artifact refs. If a campaign ends normally without an attached final-quality package, the summary records a public non-formal closure refs payload with a machine-readable status and reason code instead of leaving final evidence refs absent.

`formal_readiness.py` validates only the refs structure. It checks for required package metadata and artifact keys such as manifest, final quality JSON/CSV, per-case quality CSV, runtime summary, and failure summary. Non-formal closure refs keep `formal_ready=false` but do not report a missing package. The validator does not open artifact files.

Final quality artifact writing is generic in `scion/scion/evidence/final_quality.py`. CVRP-specific final evidence builders under `scion/scion/evidence/cvrp_*` adapt CVRP result rows or runner-backed evaluations into the generic final-quality package.

## Data Flow Summary

Framework evidence flow:

`StepRecord` -> in-memory `step_history` -> search memory -> status/summary JSON

`contract/verification/canary/protocol/decision facts` -> `EvidenceRecorder.build_step_lineage_event()` -> `LineageRegistry.experiment_events`

`DecisionFeatures and reason codes` -> `LineageRegistry.record_decision()`

`PromotionPlan/ChampionState` -> `ChampionStore` and champion snapshot directory

`FinalQualityPackage result` -> final evidence refs -> formal readiness fields in `campaign_summary.json`

The main architectural principle is to keep raw metrics and final quality artifacts as refs, while summaries expose bounded, structured facts.

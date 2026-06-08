# EvidenceRecorder / Status / Summary / Run Validity

## Scope

Current source reviewed:

- `scion/scion/core/evidence_recorder.py`
- `scion/scion/core/evidence_recording/recorder.py`
- `scion/scion/core/evidence_recording/lineage.py`
- `scion/scion/core/evidence_recording/status.py`
- `scion/scion/core/evidence_recording/summary.py`
- `scion/scion/core/evidence_recording/accounting.py`
- `scion/scion/core/run_validity.py`
- `scion/scion/core/status_reporter.py`
- campaign call sites in `campaign.py`, `campaign_loop.py`, and
  `cli/commands/init_run.py`
- selected tests in:
  - `scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py`
  - `scion/scion/tests/test_campaign_finalization_status_reconcile.py`
  - `scion/scion/tests/test_campaign_basics_continue.py`
  - `scion/scion/tests/test_cli_run_options.py`

## Current Understanding

`EvidenceRecorder` is a facade over three evidence surfaces:

```text
EvidenceRecorder
  -> record completed StepRecord into in-memory step_history
  -> write status.json from current campaign state + last completed result
  -> write campaign_summary.json from full step_history + final refs
  -> write experiment/decision/scheduler lineage when registry is present
```

`status.json` and `campaign_summary.json` intentionally have different
evidence scopes:

```text
status.json
  -> state_provider snapshot
  -> campaign_loop accounting
  -> last completed StepResult only
  -> current_progress / in_flight_protocol while running

campaign_summary.json
  -> full step_history
  -> branch snapshot from state_provider
  -> campaign_loop accounting
  -> final_evidence_refs / formal readiness
```

Run validity is a shared projection used by both status and summary. It is about
scientific usefulness, not process exit success: a provider failure after useful
rounds can be `valid_partial_interrupted`, while an infra-only invocation with
no effective experiments is invalid.

## Positive Boundary Observations

- The facade is thin. `EvidenceRecorder` owns evidence shape and artifact
  writing, while `CampaignManager` still owns branch state and orchestration.
- Status explicitly declares that it does not contain full step history. Its
  `evidence_scope_reconciliation` records `step_history_scope =
  "not_available"` and `last_result_scope = "last_completed_result_only"`.
- Summary explicitly declares `step_history_scope = "full_step_history"` and
  counts failed and non-counted steps separately.
- Terminal status clears incomplete progress for normal terminal stops, but can
  preserve partial in-flight protocol state for signal/external/keyboard stops.
- `StatusReporter.write(...)` and summary writing both use atomic replace
  patterns for JSON artifact writes.
- Tests cover the main run-validity states: valid complete, valid partial
  interrupted, invalid infra-only, no-experiment invalid, and status/summary
  consistency for those paths.

## Risks And Findings

### F-EVIDENCE-001 [P1] Lineage write failures are invisible to run validity and formal readiness

`record_step_lineage(...)` builds an experiment event and decision payload, but
both registry writes are best-effort. Failures are logged at debug level and do
not propagate to the caller. Summary `formal_readiness` validates final refs,
not lineage DB completeness. Run validity only considers requested rounds,
effective rounds, experiments, proposal attempts, stop reason, and failure
categories.

Evidence:

- `EvidenceRecorder.record_step(...)` only appends to in-memory history:
  - `scion/scion/core/evidence_recording/recorder.py:48`
  - `scion/scion/core/evidence_recording/recorder.py:59`
- Registry experiment event write is swallowed:
  - `scion/scion/core/evidence_recording/lineage.py:318`
  - `scion/scion/core/evidence_recording/lineage.py:322`
- Registry decision write is swallowed:
  - `scion/scion/core/evidence_recording/lineage.py:323`
  - `scion/scion/core/evidence_recording/lineage.py:335`
- Summary readiness only validates refs:
  - `scion/scion/core/evidence_recording/summary.py:574`
  - `scion/scion/core/evidence_recording/summary.py:589`
- Summary run validity is derived from counts/failures, not lineage integrity:
  - `scion/scion/core/evidence_recording/summary.py:497`
  - `scion/scion/core/evidence_recording/summary.py:513`
- Status run validity follows the same count-based model:
  - `scion/scion/core/evidence_recording/status.py:592`
  - `scion/scion/core/evidence_recording/status.py:620`
- Status scope says full step history is unavailable:
  - `scion/scion/core/evidence_recording/status.py:312`
  - `scion/scion/core/evidence_recording/status.py:347`

Why this matters:

- A campaign can produce a valid summary while `experiment_events` or decision
  rows are missing from the lineage registry.
- This generalizes the promotion-lineage risk from the previous module:
  structural evidence can be visible in memory/summary but absent from the DB
  surface that later reports or joins may trust.
- Because lineage failure is not represented in status or summary, wrapper
  consumers cannot distinguish "valid and lineage complete" from "valid but
  lineage degraded".

Suggested fix direction:

- Track lineage write outcome per step, for example `lineage_event_recorded`,
  `decision_lineage_recorded`, and a redacted `lineage_recording_error`.
- Add a summary/status integrity section that reconciles expected step events
  from `step_history` against registry rows when a registry is configured.
- Keep ordinary lineage best-effort if needed, but require or explicitly mark
  degraded lineage for structural decisions such as promotion.
- Add a fault-injection test with a registry that raises on `record_event(...)`
  and/or `record_decision(...)`, then assert the desired status/summary signal.

### F-EVIDENCE-002 [P1] Unexpected exceptions can bypass final campaign status and summary finalization

`CampaignLoop.run(...)` writes final summary/status only after the loop exits
normally through its own stop conditions. The main loop calls
`run_one_step()` directly, without an outer `try/finally` that records a
terminal status on unexpected exceptions. `CampaignManager.run(...)` also calls
runtime preflight and then campaign loop directly. The CLI signal path calls
`finalize_requested_stop(...)`, but the generic exception path only writes the
wrapper run audit and re-raises.

Evidence:

- Runtime preflight and loop are called directly:
  - `scion/scion/core/campaign.py:261`
  - `scion/scion/core/campaign.py:264`
- The loop writes running status, then calls `run_one_step()` directly:
  - `scion/scion/core/campaign_loop.py:217`
  - `scion/scion/core/campaign_loop.py:218`
- Final summary/status writes only occur after loop exit:
  - `scion/scion/core/campaign_loop.py:347`
  - `scion/scion/core/campaign_loop.py:364`
- CLI signal stops finalize campaign artifacts:
  - `scion/scion/cli/commands/init_run.py:728`
  - `scion/scion/cli/commands/init_run.py:739`
- CLI generic exceptions finish only the wrapper audit:
  - `scion/scion/cli/commands/init_run.py:740`
  - `scion/scion/cli/commands/init_run.py:745`

Why this matters:

- If an unexpected exception escapes preflight or `run_one_step()`, a campaign
  can end with a stale running `status.json`, no final `campaign_summary.json`,
  or no `run_validity` classification for the partial evidence that already
  exists.
- The wrapper `run_status.json` can record that the CLI crashed, but it does
  not replace campaign-level summary/status artifacts that downstream evidence
  consumers inspect.
- This is most visible when a campaign has already completed useful rounds and
  then crashes in a later step: the scientific evidence may exist, but the
  final validity projection can be missing.

Suggested fix direction:

- Add a campaign-level finalization guard around preflight + loop, or around
  the loop body, that writes terminal status/summary for unhandled exceptions.
- Use a specific stopped reason such as `unhandled_exception` or
  `preflight_exception`, and let run-validity classify whether any useful
  evidence exists.
- Preserve the original exception after writing artifacts so CLI/process
  semantics do not hide failures.
- Add tests for a preflight exception and a synthetic `run_one_step()` exception
  after one completed step.

### F-EVIDENCE-003 [P2] `partial_in_flight` conflates incomplete campaign evidence with an actual in-flight protocol

Status passes `partial_in_flight=bool(payload.get("in_flight_protocol"))` into
`build_run_validity(...)`. However, when validity is
`valid_partial_interrupted`, `build_run_validity(...)` sets
`partial_in_flight` to `True` even if there is no preserved in-flight protocol
snapshot. Summary does not pass `partial_in_flight` at all, and for stopped
runs it drops incomplete `current_progress`.

Evidence:

- Summary drops incomplete progress when stopped:
  - `scion/scion/core/evidence_recording/summary.py:124`
  - `scion/scion/core/evidence_recording/summary.py:134`
- Summary run-validity call does not pass `partial_in_flight`:
  - `scion/scion/core/evidence_recording/summary.py:497`
  - `scion/scion/core/evidence_recording/summary.py:513`
- Status passes a boolean based on `in_flight_protocol`:
  - `scion/scion/core/evidence_recording/status.py:598`
  - `scion/scion/core/evidence_recording/status.py:619`
- Run-validity overrides the field for interrupted partial runs:
  - `scion/scion/core/run_validity.py:173`
  - `scion/scion/core/run_validity.py:217`
- Tests currently encode this behavior:
  - `scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py:1648`
  - `scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py:1710`

Why this matters:

- A consumer may read `partial_in_flight=True` as "a formal protocol was
  interrupted mid-flight and partial metrics may exist", when the actual state
  can simply be "the campaign was interrupted before requested rounds
  completed".
- Status and summary can agree on the field while not preserving the same
  progress surface. That makes the field a campaign-completeness signal rather
  than a protocol-state signal.

Suggested fix direction:

- Split the semantics into two fields:
  - `partial_campaign`: requested campaign rounds were not completed but useful
    evidence exists.
  - `protocol_in_flight`: a protocol snapshot was actually in flight and
    preserved.
- Keep `partial_in_flight` as a deprecated compatibility alias if existing
  wrapper consumers require it.
- Add tests that distinguish signal stop between completed rounds and signal
  stop during a protocol run.

### F-EVIDENCE-004 [P2] Evidence snapshot generation can mutate campaign state

`write_status(...)` and `write_campaign_summary(...)` call the configured
`state_provider`. In production that state provider is `CampaignManager.get_state()`.
`get_state()` reconciles active-slot overflow and persists parked branch states
when reconciliation changes the branch set.

Evidence:

- Status reads `state_provider()` at write time:
  - `scion/scion/core/evidence_recording/status.py:431`
  - `scion/scion/core/evidence_recording/status.py:442`
- Summary reads `state_provider()` for run validity and again for branch
  snapshots:
  - `scion/scion/core/evidence_recording/summary.py:489`
  - `scion/scion/core/evidence_recording/summary.py:493`
  - `scion/scion/core/evidence_recording/summary.py:590`
  - `scion/scion/core/evidence_recording/summary.py:628`
- `CampaignManager.get_state()` can reconcile overflow and persist branch
  state:
  - `scion/scion/core/campaign.py:307`
  - `scion/scion/core/campaign.py:319`

Why this matters:

- A status or summary write is not purely observational. It can park branches
  and persist those transitions as a side effect of evidence generation.
- If that reconciliation is intentional, it should be documented as part of the
  status/summary contract. If it is not, branch lifecycle mutation should move
  back into scheduling/finalization code and `get_state()` should become a
  read-only projection.

Suggested fix direction:

- Rename/document this behavior as reconciliation-on-snapshot, or split
  `get_state(read_only=True)` from a separate lifecycle reconciliation method.
- Add a test that calls status/summary generation on an overflow state and
  asserts the intended branch persistence behavior.

## Open Questions

- Should lineage DB completeness be part of `formal_readiness`, or should it be
  a separate `lineage_integrity` block?
- Should summary write failures remain best-effort, or should final artifact
  write failure affect wrapper exit status?
- Should `status.json` ever expose more than the last completed result, or is
  the current "latest operational heartbeat" boundary intentional?

## Suggested Next Audit Target

Review `ProblemSpecV1 / ProblemAdapter boundary` next. It is the best follow-up
because the evidence layer depends heavily on generic counts and adapter-owned
runtime semantics; this boundary decides whether status/summary fields remain
problem-neutral or start leaking CVRP-specific meaning into core.

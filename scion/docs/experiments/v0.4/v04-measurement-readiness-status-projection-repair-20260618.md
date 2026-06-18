# v0.4 Measurement Readiness Status Projection Repair - 2026-06-18

## Conclusion

Measurement readiness was already computed from problem-owned calibration
declarations and stored on `ProtocolConfig`, but campaign artifacts only
projected `measurement_governance`. `status.json` and `campaign_summary.json`
now expose the same reduced `measurement_readiness` payload, so missing, stale,
incompatible, incomplete, or low-power calibration states are visible to
operators and postrun analysis.

## Repair

- Added a shared sanitizer for measurement readiness payloads in
  `scion/scion/core/evidence_recording/common.py`.
- `CampaignManager.get_state()` now projects
  `ProtocolConfig.measurement_readiness` into status state.
- `CampaignManager._write_campaign_summary()` now passes the reduced readiness
  payload to the summary writer.
- `StatusWriterMixin.write_status()` and
  `CampaignSummaryMixin.write_campaign_summary()` sanitize readiness fields
  before writing artifacts.
- Recorder and CLI tests assert that status/summary expose readiness and do not
  leak `calibration_ref`.

## Boundary Check

This is artifact/status projection only. It does not change Decision,
`DecisionFeatures`, Protocol gates, scheduling, lifecycle policy, runtime
governance, budgets, proposal prompting, or problem-owned calibration
semantics. Raw calibration refs and raw A/A pair evidence remain excluded from
status readiness payloads and from `DecisionFeatures`.

## Acceptance

Commands run from `/home/clawd/research/or-autoresearch-agent`:

```bash
PYTHONPATH=scion pytest -q scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py::test_summary_and_status_expose_measurement_governance_consistently scion/scion/tests/test_cli_run_options.py::test_run_measurement_governance_visible_in_summary_and_status
python -m py_compile scion/scion/core/evidence_recording/common.py scion/scion/core/evidence_recording/status.py scion/scion/core/evidence_recording/summary.py scion/scion/core/campaign.py scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py scion/scion/tests/test_cli_run_options.py
PYTHONPATH=scion pytest -q scion/scion/tests/unit/test_measurement_readiness.py scion/scion/tests/test_config.py scion/scion/tests/test_problem_bridge.py
PYTHONPATH=scion pytest -q scion/scion/tests/unit/core/test_evidence_recorder_summary_status.py scion/scion/tests/test_cli_run_options.py
```

Results:

- Focused readiness projection tests: `4 passed`
- py_compile: passed
- Measurement/config/problem bridge regression: `29 passed`
- Summary/status and CLI option regression: `73 passed`

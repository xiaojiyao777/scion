# Warehouse Promoted-Patch Fixed-Candidate Replay

*Date:* 2026-06-13
*Status:* valid promoted-only fixed-candidate screening replay; one promoted
patch is robust at screening, one exposes incomplete replay materialization

## Scope

This follow-up audits the two warehouse promotions produced by the
`no-measurement-diagnostics` arm in the Phase 5 explicit-control-pair run:

- Source run:
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-controlpair-full-vs-nomeas-4x2-8r-20260613T011820Z-claw`
- Promoted-only replay root:
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-promoted-only-fixed-replay-20260613T075754Z-claw`

The replay answers a narrow posthoc question: given a recorded candidate patch,
does screening change between `measurement_governance=on` and `record_only`?
It does not reproduce LLM trajectories, validation, frozen evaluation,
scheduler behavior, lifecycle behavior, or promotion correctness.

## Tool Repair

The initial all-candidate replay was aborted after it became clear that the
existing manifest builder could only replay all five formal candidates from a
campaign. That run root was:

`/home/clawd/research/scion-experiments/v04-phase5-warehouse-promoted-patch-fixed-replay-20260613T074315Z-claw`

It is not used as evidence. The repair adds promoted-only filtering to the
manifest builder:

- `scion report fixed-candidate-replay-manifest --candidate-id ...`
- `scion report fixed-candidate-replay-manifest --hypothesis-id ...`
- Manifest metadata now records `candidate_filter` and
  `filtered_out_row_count`.

Acceptance:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  pytest -q scion/scion/tests/test_fixed_candidate_replay.py
```

Result: `7 passed`.

## Replay Commands

The promoted-only manifests were built with the source campaigns and a single
candidate filter each:

- rep01: `--candidate-id e509f96296bd33d2`
- rep04: `--candidate-id d27b539b2b540a74`

Both replays used:

- problem: `scion/problems/warehouse_delivery/problem-v1.yaml`
- protocol: `scion/problems/warehouse_delivery/protocol_prod.yaml`
- split: `scion/problems/warehouse_delivery/split_manifest_prod.yaml`
- seeds: `scion/problems/warehouse_delivery/seed_ledger.yaml`
- `--time-limit-sec 30`

Each manifest had `candidate_count=1`, `filtered_out_row_count=4`,
`omitted_rows=[]`, `causal_candidate_pairing=true`, and replay arms
`["on", "record_only"]`.

## Results

### rep01 promotion

- Hypothesis: `a74d5a4e-5ad9-4349-b54d-98ec39645bd1`
- Candidate: `e509f96296bd33d2`
- Target: `operators/merge_vehicles.py`
- Source decision: `expand_screening`
- Comparison:
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-promoted-only-fixed-replay-20260613T075754Z-claw/rep01_no_measurement/fixed_candidate_replay_comparison.v1.json`

Replay completed with `row_count=2` and no error rows. ON and `record_only`
matched exactly:

- `gate_outcome=expand`
- `reason_codes=["SCREENING_EXPAND"]`
- case W/L/T: `3/0/3`
- `win_rate=0.5`
- `median_delta=875.0`
- CI: `[0.0, 9300.0]`
- canary passed in both arms

This is valid fixed-candidate screening evidence that the promoted
`merge_vehicles.py` patch remains a screening-expand candidate and that the
screening outcome is not changed by record-only measurement governance.

### rep04 promotion

- Hypothesis: `2b7a3f7e-b899-4a5b-894b-d624fe2570c1`
- Candidate: `d27b539b2b540a74`
- Target: `operators/split_safe_cost_repack.py`
- Source decision: `expand_screening`
- Comparison:
  `/home/clawd/research/scion-experiments/v04-phase5-warehouse-promoted-only-fixed-replay-20260613T075754Z-claw/rep04_no_measurement/fixed_candidate_replay_comparison.v1.json`

Replay completed with `row_count=2` and no error rows. ON and `record_only`
matched exactly, but both failed screening:

- `gate_outcome=fail`
- `reason_codes=["SCREENING_FAIL_WIN_RATE"]`
- case W/L/T: `0/0/10`
- `win_rate=0.0`
- `median_delta=0.0`
- CI: `[0.0, 0.0]`
- canary passed in both arms

This does not reproduce the source screening result, which had pair W/L/T
`12/2/6` and case W/L/T `7/1/2`.

Root cause found during audit: the formal candidate artifact records only the
new operator file `operators/split_safe_cost_repack.py`. The source campaign
workspace also changed `registry.yaml` to register `SplitSafeCostRepack` and
rebalance operator weights, but `candidate.patch.json` did not capture that
auxiliary change. Replay materialized the new file on top of `champion_v1`,
kept the original registry, and therefore never loaded the new operator. The
replayed candidate tied the champion on every pair.

This is valid negative fixed-candidate evidence for the recorded patch artifact
and a framework bug in formal candidate artifact completeness for `create_new`
operator proposals. It should not be counted as robust promotion evidence.

## Boundary Checks

Both comparisons preserve the v3 report-only boundary:

- `comparison_is_decision_input=false`
- `decision_features_excluded=true`
- `campaign_state_mutated=false`
- `scheduler_state_mutated=false`
- `promotion_state_mutated=false`
- `raw_paired_rows_excluded=true`
- `measurement_diagnostics_excluded=true`

Forbidden-field scans over both comparison artifacts found no hits for
`code_content`, `TAINTED`, `problem_measurement_diagnostics`, `bks_gap`,
`aa_rows`, `raw_prompt`, `raw_response`, `prompt_text`, or `llm_response`.

Read-only subagent Avicenna independently confirmed the row counts, flags,
redaction checks, ON/record-only agreement, and the caveat that these artifacts
are screening-only replay evidence, not promotion or governance-value evidence.

## Implications

1. The `no-measurement-diagnostics` arm produced one robust promoted patch at
   fixed-candidate screening replay: `merge_vehicles.py`.
2. The second promotion remains useful as a framework finding, not as robust
   patch evidence: `create_new` operator artifacts must include activation
   surfaces such as `registry.yaml` or be marked non-replayable.
3. The replay result continues to show no ON vs `record_only` screening
   difference for fixed candidates; it does not prove or disprove broader
   measurement-governance value.
4. Next repair: make formal candidate replay identity include auxiliary
   activation files for warehouse `create_new` operators, then rerun the rep04
   promoted candidate replay.


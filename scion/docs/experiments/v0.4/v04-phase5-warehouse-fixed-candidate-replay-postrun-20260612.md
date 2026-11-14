# v0.4 Warehouse Fixed-Candidate Replay Postrun

*Date: 2026-06-12*
*Branch: `codex/v04-evidence-repair-plan`*
*Executor commit: `a8f7e97`*
*Status: valid fixed-candidate control; no ON/OFF screening difference*

## Summary

The warehouse fixed-candidate replay completed cleanly. It replayed the five
formal screening candidates from the warehouse ON shakedown under both
`measurement_governance=on` and `record_only`, producing ten comparison rows
with zero row errors.

All five candidates produced identical screening outcomes in the two replay
arms. This validates the fixed-candidate replay control and the
measurement-only OFF contract, but it is not a governance-value conclusion. The
artifact evaluates identical recorded patches after proposal generation; it
does not replay LLM proposal, scheduler, lifecycle, Decision, validation,
frozen, or promotion trajectories.

## Artifacts

- Manifest:
  `/tmp/warehouse-fixed-candidate-replay-manifest.v1.json`
- Comparison artifact:
  `/home/clawd/research/scion-experiments/v04-phase5-fixed-candidate-replay-warehouse-5c-20260612T0525Z-claw/fixed_candidate_replay_comparison.v1.json`
- Source campaign:
  `/home/clawd/research/scion-experiments/v04-phase5-governance-warehouse-on-pilot-8r-gpt55-20260612T013119Z-claw/campaign`
- Prior ON/OFF shakedown report:
  [`v04-phase5-warehouse-governance-onoff-8r-postrun-20260612.md`](v04-phase5-warehouse-governance-onoff-8r-postrun-20260612.md)

Run command:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
python -m scion.cli.main report fixed-candidate-replay \
  --manifest /tmp/warehouse-fixed-candidate-replay-manifest.v1.json \
  --problem /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/problem-v1.yaml \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/protocol_prod.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/split_manifest_prod.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/seed_ledger.yaml \
  --output-dir /home/clawd/research/scion-experiments/v04-phase5-fixed-candidate-replay-warehouse-5c-20260612T0525Z-claw \
  --time-limit-sec 30
```

CLI summary:

```json
{
  "candidate_count": 5,
  "comparison_path": "/home/clawd/research/scion-experiments/v04-phase5-fixed-candidate-replay-warehouse-5c-20260612T0525Z-claw/fixed_candidate_replay_comparison.v1.json",
  "error_count": 0,
  "row_count": 10,
  "schema_version": "scion.fixed_candidate_replay_comparison.v1"
}
```

## Manifest And Guardrails

The manifest was `scion.fixed_candidate_replay_manifest.v1` with
`candidate_count=5`, `omitted_rows=[]`, replay arms `on` and `record_only`, and
`causal_candidate_pairing=true`. Each candidate kept the same patch identity in
both replay arms.

The comparison artifact preserved the intended v3 boundary:

- `comparison_is_decision_input=false`
- `decision_features_excluded=true`
- `campaign_state_mutated=false`
- `scheduler_state_mutated=false`
- `promotion_state_mutated=false`
- `raw_paired_rows_excluded=true`
- `measurement_diagnostics_excluded=true`

Forbidden-field scan found no `code_content`, `prompt_text`, `rationale_text`,
`raw_measurement_diagnostics`, `bks_gap`, `aa_rows`, or `hypothesis_text` in
the comparison artifact.

## Row Results

| Candidate | Action | Surface | ON result | Record-only result |
| --- | --- | --- | --- | --- |
| `08268e17f34b889d` | `create_new` | `vehicle_level` | completed, fail, `SCREENING_FAIL_WIN_RATE`, n=10, W/L/T=0/0/10, median=0, CI=[0,0] | same |
| `3cd91b78ac03996e` | `modify` | `vehicle_level` | completed, fail, `SCREENING_FAIL_WIN_RATE`, n=6, W/L/T=0/0/6, median=0, CI=[0,0] | same |
| `a0de6c72359801f6` | `modify` | `vehicle_level` | completed, fail, `SCREENING_FAIL_WIN_RATE`, n=6, W/L/T=0/0/6, median=0, CI=[0,0] | same |
| `dd62e8096c7aca93` | `create_new` | `order_level` | completed, fail, `SCREENING_FAIL_WIN_RATE`, n=10, W/L/T=0/0/10, median=0, CI=[0,0] | same |
| `f40dd9b672cf6cc2` | `modify` | `vehicle_level` | completed, expand, `SCREENING_EXPAND`, n=6, W/L/T=3/0/3, median=950, CI=[0,9775] | same |

Every row had `canary.passed=true`.

## Interpretation

The fixed-candidate control answers a narrow question: if the exact same
candidate patch is evaluated under ON and record-only measurement governance,
does the screening result change? For this warehouse artifact set, the answer
is no. Four candidates remain all-tie screening failures, and the promoted ON
candidate's initial screening result remains `SCREENING_EXPAND` in both arms.

This result is useful because it removes one possible explanation for the prior
warehouse ON/OFF shakedown divergence: the observed difference was not caused
by posthoc protocol evaluation of the same patch. The remaining plausible
governance effects live earlier in the research loop: prompt/context content,
proposal selection, branch memory, scheduler trajectory, candidate generation,
and lifecycle pressure.

This artifact must not be used as promotion evidence. If `f40dd9b672cf6cc2`
should be promoted or compared formally, that must happen through a
pre-registered campaign path that generates valid `DecisionFeatures`,
validation rows, and frozen rows. The comparison artifact is posthoc audit
evidence only.

## Independent Check

Read-only subagent Tesla independently inspected the manifest and comparison
artifact after first reading the v3 architecture blueprint. Its conclusion
matched the main-thread check:

- schema and mutation guardrails passed;
- five candidates and ten rows were present;
- patch identities were paired across arms;
- no forbidden code, prompt, raw diagnostic, BKS/gap, or A/A row material
  leaked into the comparison artifact;
- all ON and record-only row outcomes were identical;
- the result is fixed-candidate screening evidence, not LLM trajectory
  governance-value evidence.

## Next Gate

The next governance-value design should move up one level from fixed-candidate
screening replay to trajectory-aware controls. Two practical options remain:

- pre-register a stored-proposal or trace-level replay contract that can
  compare prompt/context governance without pretending to reproduce free-running
  LLM trajectories;
- run a bounded prompt/context audit that samples the ON and record-only
  shakedown traces, measures research-signal density and branch-signal use, and
  identifies which governance blocks plausibly influenced candidate generation.

CVRP should remain a diagnostic/runtime/research-mechanics target until another
pre-registered measurement change lowers its MDE near the accepted effect
scale. Warehouse remains the better immediate candidate for governance
trajectory controls because its effect size is measurable under current
production protocol.

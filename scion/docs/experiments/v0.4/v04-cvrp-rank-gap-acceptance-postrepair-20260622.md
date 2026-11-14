# CVRP Rank-Gap Acceptance Post-Repair Run

Date: 2026-06-22

## Scope

This report records the first post-repair CVRP current-run-ready solver-design
campaign after the prompt/source, launch-readiness, APS retry, quality-loop,
protected-case, and runtime-drain repairs.

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-2e1bc5ae-postrepair-4r-gpt55-20260622T021910Z-claw`
- Local mirror:
  `/home/clawd/research/scion-experiments/v04-cvrp-twoopt-2e1bc5ae-postrepair-4r-gpt55-20260622T021910Z-claw`
- WSL repo commit: `2e1bc5ae`
- Model: `gpt-5.5`
- Python: `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- Resume source:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z/campaign`

## Acceptance

The run finished naturally and passed WSL postrun acceptance.

- Root `run_status.json`: `status=finished`, `wrapper_exit_status=0`,
  `campaign_wrapper_exit_status=0`, `postrun_readiness_exit_status=0`,
  `postrun_acceptance_status=ready`, `run_validity_status=valid`,
  `run_completeness_status=complete`,
  `last_stop_reason=max_rounds_exhausted`.
- Campaign counters: 4 effective rounds, 4 consumed proposal attempts, 4
  protocol-evaluated candidates, 4 formal screened candidates, 4 screening
  rows, 0 quality blocks, 0 promotions, champion version `v1`.
- Postrun acceptance command on WSL:

```bash
PY=/home/xjy-ubuntu/miniconda3/envs/scion/bin/python
ROOT=/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-twoopt-2e1bc5ae-postrepair-4r-gpt55-20260622T021910Z-claw
PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion \
  "$PY" scion/tools/check_postrun_acceptance.py "$ROOT" \
  --require-current-run-ready --format json
```

The local mirror was synced with `scripts/sync_wsl_run_root.py --execute
--skip-postrun-check`. WSL postrun acceptance is authoritative for this root:
the postrun artifacts intentionally contain WSL absolute paths, so local
mirror-only identity checks are path-sensitive and not used as acceptance.

## Research Behavior

The run demonstrates that the repaired framework can support CVRP
evidence-backed continuation and rejection.

- Mechanism family: `rank_gap_annealing_acceptance`.
- Branch depth: 4.
- Same-mechanism opportunities observed: 4.
- Same-branch refinements selected: 3.
- Same-mechanism missed: 1.
- Prompt/source visibility: accepted on WSL; hypothesis target source was
  visible in all 3 required target-source traces, and code protected/target
  source visibility was present in all 3 code traces.
- Prompt density interpretation:
  `research_and_source_signal_at_least_governance`.
- Remaining actionability gap:
  `same_mechanism_opportunities_not_selected`; branch lessons were present but
  had 3 semantic gaps.

## Screening Results

All rows were screening rows; no validation or frozen rows were reached. CVRP
measurement readiness was `ready`, with `mde_at_power_80=9.9`. All four rows
had CI high below MDE, median delta `0.0`, and no positive effect at or above
MDE.

| Metric | Pairs | W/T/L | Net delta | CMT2 | CMT3 | CMT4 | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| `c4991b87-23fc-4003-96a3-60c585c15f14.json` | 32 | 11/15/6 | +142 | +11 | n/a | +2 | expand screening |
| `cb95461f-2e24-4a2c-8536-dc86ce558618.json` | 48 | 12/25/11 | -16 | +11 | -15 | +2 | continue explore |
| `b48a3abd-584b-4d85-83c2-a60789b55dcd.json` | 32 | 12/13/7 | +90 | -34 | n/a | +2 | expand screening |
| `364d0d08-27c6-4b0c-b7da-2173d3856550.json` | 48 | 13/22/13 | -72 | -30 | -15 | +2 | continue explore / park lineage |

Interpretation:

- The two 32-pair screens both had aggregate positive-looking signals.
- Both corresponding 48-pair expansions weakened or reversed those signals.
- The final expanded row failed closed with negative CMT2 and CMT3 behavior,
  CMT4 only slightly positive, and no MDE-supported objective effect.
- Mechanism activation was observed, but objective-effect telemetry was
  classified as zero/no-effect.

## Conclusion

This run is valid, complete, current-run-ready CVRP evidence that the repaired
framework can carry a solver-design hypothesis through same-mechanism
refinement, expanded screening, MDE-aware interpretation, and fail-closed
rejection without provider, source-visibility, quality-loop, or runtime-drain
breakage.

It is not a solver improvement and not a promotion result. The next CVRP run
should avoid repeating unchanged rank-gap acceptance gates and should select a
materially different problem-owned solver mechanism or a new causal path with
direct objective-effect telemetry and explicit CMT2/CMT4 protection.

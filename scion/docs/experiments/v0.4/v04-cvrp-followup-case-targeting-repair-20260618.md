# CVRP Follow-Up Case Targeting Repair - 2026-06-18

## Purpose

The copied-campaign `demand_slack_regret_insertion` follow-up was valid but
expanded screening did not retest prior-negative `CMT2`, even though the branch
evidence summary recorded earlier CMT2/CMT4 losses. This made same-branch
follow-up less diagnostic than intended.

## Repair

- Added deterministic priority case retention to protocol case selection.
- Priority case ids come from branch evidence on expand stages only.
- Matching is generic: exact manifest id first, then unique basename match
  such as `CMT2.vrp` to `cvrplib/CMT/CMT2.vrp`; ambiguous basenames are skipped.
- Raw metrics now record `requested_priority_case_ids`.
- The repair stays outside `DecisionFeatures`; it changes protocol coverage,
  not deterministic promotion/abandon decision inputs.

## Acceptance

Local focused checks:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion pytest -q \
  scion/scion/tests/unit/protocol/test_protocol_correctness.py \
  scion/scion/tests/unit/core/test_evaluation_pipeline.py \
  scion/scion/tests/unit/core/test_evaluation_orchestrator_telemetry.py
```

Result: `56 passed`.

Local compile check:

```bash
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion python -m py_compile \
  scion/scion/protocol/experiment/selection.py \
  scion/scion/protocol/experiment/facade.py \
  scion/scion/protocol/experiment/stages.py \
  scion/scion/core/evaluation_pipeline.py \
  scion/scion/core/evaluation_orchestrator.py
```

Result: passed.

WSL focused checks used the synchronized checkout and WSL Python environment:
`56 passed`; compile check passed.

Formal CVRP selection smoke:

- Default expanded screening did not include `cvrplib/CMT/CMT2.vrp`.
- Priority selection with `("CMT2.vrp", "CMT4.vrp", "A-n64-k9.vrp")` included
  `CMT2`, `CMT4`, and `A-n64-k9` while preserving the configured `12` case
  count.

## Remaining Work

This is a framework/protocol repair, not new CVRP solver evidence. The next
agentic CVRP run should either pivot to a materially different problem-owned
solver mechanism, or use this repaired targeting for a genuine branch follow-up;
raw metrics should show the requested priority cases when expand screening is
used.

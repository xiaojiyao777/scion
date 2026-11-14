# CVRP Cadence-2 Provider-Ref Agentic 1R Postrun

Date: 2026-06-17
Branch: `codex/v04-evidence-repair-plan`
Commit: `6c842f6`

## Purpose

Verify the post-repair CVRP solver-design prompt path after the provider-ref
repair. The specific acceptance question was whether live agentic prompts could
see the problem-owned cadence-2 opportunity text after agentic context
sanitization removed the provider object.

This run was not intended to prove a CVRP improvement. It was a short targeted
field check for prompt plumbing, framework accounting, and the next steering
fault.

## Run

- WSL root:
  `/home/xjy-ubuntu/research/scion-experiments/v04-cvrp-cadence2-providerref-agentic-1r-6c842f6-20260617T191056Z`
- Server sync root:
  `/home/clawd/research/scion-experiments/v04-cvrp-cadence2-providerref-agentic-1r-6c842f6-20260617T191056Z`
- Model: `gpt-5.5`
- Command shape: `scion.cli.main run`, CVRP formal protocol, `--rounds 1`,
  `--time-limit-sec 30`, `--agentic-session-timeout-sec 900`,
  `--measurement-governance on`,
  `--proposal-context-ablation compact-measurement-diagnostics`,
  `--disable-early-stop`, `--agentic-proposal`
- Wrapper exit: `0`
- Campaign: `9d26861d-8c15-4323-a329-60f7897bd65d`

## Outcome

- Run completeness: `complete`
- Run validity: `valid`
- Effective rounds: `1`
- Formal candidate artifacts: `1`
- Protocol rows: `1`
- LLM traces: `9` (`hypothesis_target_intent=1`, `hypothesis=1`,
  `tool_selection=6`, `code=1`)
- Formal screening metric:
  `campaign/metrics/edf5b96e-eec4-4735-8cc7-4bf2d7a34af2.json`
- Screening pairs: `32/32`, failures `0`
- Evidence status: `screening_evidence_status=complete`,
  `runtime_evidence_status=sufficient`, `runtime_confidence=high`
- Candidate branch: `9735d929-9e16-4810-bc67-fb6cca254c8e`
- Candidate status: `active_marginal`, retained as an active branch

The candidate implemented `route_merge_savings_vns` in
`policies/baseline_modules/local_search.py`. It did not implement or refine the
intended adaptive embedded-VNS cadence-2 trigger.

Authoritative branch-card evidence classified the candidate as marginal:
case-level W/L/T `1/1/6`, median delta `0.0`, with a positive case-level signal
on `A-n64-k9.vrp` and a loss on `CMT2.vrp`. Runtime evidence was sufficient and
high confidence; the runtime-budget saturation diagnostic was proposal-visible
only and excluded from `DecisionFeatures`.

## Prompt Evidence

The provider-ref repair worked for the final hypothesis prompt. The live
`hypothesis` trace contains:

- `Current CVRP no-LLM opportunity`
- `adaptive embedded-VNS cadence-2`
- `current exception is the adaptive embedded-VNS cadence-2 opportunity`
- `remaining-budget, recent best-update`
- `repaired-candidate-improvement signals`

The `hypothesis_target_intent` trace did not contain those cadence-2 strings.
It selected the target intent before the final hypothesis call:

- `target_file=policies/baseline_modules/local_search.py`
- `mechanism_id=route_merge_savings_vns`
- `mechanism_family=vns_local_search`

The final hypothesis then stayed bound to that preflight intent, as designed.
Therefore the repair fixed final hypothesis guidance visibility but not target
selection. Cadence-specific guidance arrived too late in the proposal sequence.

## Interpretation

Accepted:

- Framework execution was stable for this short CVRP run: wrapper exit `0`,
  valid campaign, complete formal screening, complete lineage/evidence
  integrity, no failed pairs, and retained formal candidate artifact.
- The provider-ref repair is field-verified for final hypothesis rendering.
- Runtime diagnostics remained advisory/proposal-visible and did not become
  promotion evidence.

Rejected:

- This is not evidence that the agent refined cadence-2.
- This is not evidence of a CVRP solver improvement.
- The current steering path is still insufficient because target-intent
  selection does not receive problem-owned solver-design opportunity guidance.

## Follow-Up Repair

The next repair should expose problem-owned solver-design guidance to
`hypothesis_target_intent` whenever solver-design is the active targetable
surface. This belongs in proposal/problem-owned prompt rendering only; it must
remain outside `DecisionFeatures`, Protocol decisions, and promotion gates.

After that repair, rerun a short CVRP agentic check and inspect the first live
`hypothesis_target_intent` trace before interpreting the candidate mechanism.
The acceptance check is simple: the target-intent trace itself must contain the
cadence-2 opportunity text, not just the final hypothesis trace.

# Warehouse Post-Repair Short Debug Design - 2026-06-15

## Purpose

Define the next warehouse empirical gate after the targeted repair accepted in
`scion/docs/experiments/v0.4/v04-warehouse-targeted-repair-20260615.md`.

This is a short compact ON-arm debug, not a governance on/off comparison and
not a full warehouse `3 x 24R` longrun. Its purpose is to verify that the
accepted repair changes actual agent behavior before spending longrun budget.

Do not launch this run while the CVRP size70 Tier 1 Large-X solver replay is
still using WSL solver capacity.

## Required Starting State

- Branch: `codex/v04-evidence-repair-plan`
- Required commit or descendant:
  `1144239` (`fix: tighten warehouse branch lesson and replay gating`)
- WSL repo:
  `/home/xjy-ubuntu/research/or-autoresearch-agent`
- Python:
  `/home/xjy-ubuntu/miniconda3/envs/scion/bin/python`
- Model:
  local `gpt-5.5`
- API base:
  `http://127.0.0.1:8080`
- Warehouse safe data root:
  `/home/xjy-ubuntu/research/scion-data`

Before launch, the WSL repo must be fast-forwarded to the required commit or a
descendant and any experiment-local `problem.yaml`, `problem-v1.yaml`,
protocol, split, and seed artifacts must use WSL absolute paths.

## Run Shape

- Problem: warehouse production package
- Protocol:
  `scion/problems/warehouse_delivery/protocol_prod.yaml`
- Split:
  production `split_manifest_prod.yaml`, copied into the experiment root with
  WSL absolute safe roots
- Rounds:
  `4` minimum, `6` preferred if solver/APS capacity is clear
- Cells:
  `1`
- Measurement governance:
  `on`
- Proposal context:
  `compact-measurement-diagnostics`
- Time limit:
  `30s`
- Early stop:
  disabled
- Agentic proposal:
  enabled
- Agentic session timeout:
  `900s`
- Wrapper timeout:
  `5h` for `4R`, `7h` for `6R`

## Acceptance

Accept as a valid post-repair short debug only if:

- wrapper exits `0`;
- `run_validity.status=valid`;
- requested rounds, proposal attempts, Protocol rows, fresh-runtime replay rows,
  and formal candidate artifacts reconcile;
- no pre-Protocol Verification/canary/environment failure occurs;
- no no-effect budget-exhausting fresh-runtime replay row is created from bare
  runtime-tie evidence;
- strict clean-fork or sibling-nearby branch-lesson requirements either satisfy
  semantic projection or are blocked before code generation;
- no more than one extra no-effect same-mechanism follow-up is spent before
  parking, clean-forking, or producing measurable causal-path change;
- code-stage target/current source visibility remains intact;
- `compact_research_signals` truncation is measured and reported even if still
  unresolved.

## Expected Outcomes

Pass:

- The run reaches Protocol for all requested rounds or explains non-counted
  proposal blocks as intentional strict branch-lesson enforcement.
- Clean forks show semantic branch-lesson contrast.
- Fresh-runtime replay rows, if any, have pair-win/no-loss or actionable
  diagnostic basis.

Fail:

- The run repeats the old pattern of same-mechanism no-effect attempts followed
  by a no-effect fresh-runtime replay.
- Strict branch-lesson blocks dominate because the context is too noisy for the
  agent to satisfy them.
- Prompt truncation still hides compact research signals in hypothesis contexts
  and blocks useful research behavior.

## Next Decision

If this short debug passes execution and research-quality gates, the next step
is a bounded warehouse longrun design. If it fails, repair prompt economy before
another warehouse campaign.

# Independent VRP Research Agent E Launch - 2026-06-15

## Purpose

This is a sixth independent VRP-only external control. The goal is to test
whether a plain Codex research subject can improve the standalone `vrp/`
baseline while recording its research process, without seeing Scion
architecture, Scion task context, Scion audits, Scion status, or Scion
experiment results.

This is not a Scion subagent assignment. It is intentionally exempt from the
usual v3-first brief because contamination by Scion research history would
defeat the control.

## Agent

- Agent: `Lovelace`
- Agent id: `019ecce4-4806-7581-b033-d33911f8b276`
- Context: fresh non-forked subagent
- Allowed source: standalone `vrp/`
- Forbidden source: `scion/`, `TASK.md`, Scion design docs, Scion audit
  reports, Scion status docs, and Scion experiment artifacts
- Artifact root:
  `/home/clawd/research/scion-experiments/v04-independent-vrp-baseline-research-longrun-20260615`

## Required Outputs

The agent brief requires the following artifacts under the artifact root:

- `research_log.md`
- `status.md`
- `experiments.csv` or `experiments.jsonl`
- candidate patches or variant files under the artifact root only
- `candidate.patch` if a positive candidate survives
- `final_summary.md` when a phase completes

The agent may run standalone VRP cases and propose baseline algorithm changes,
but it must not modify tracked main-worktree files, commit, push, or read Scion
materials.

## Acceptance

Any result from this agent is external-control evidence only. A positive
candidate may become a human-approved mechanism seed for a separate no-LLM
Scion CVRP replay, but it is not Scion Protocol evidence and cannot support
promotion by itself.

# Independent VRP Research Agent Phase G Launch - 2026-06-15

## Purpose

Launch an eighth independent VRP-only control agent as a standalone Codex
research subject. This is an external-control lane for comparing plain Codex
algorithm research against Scion-guided research behavior.

The question is not whether another random VRP tweak can be found. The question
is whether an uncontaminated Codex researcher, without Scion prompts, governance,
branch maps, or measurement diagnostics, can form stable VRP baseline
hypotheses, test them reproducibly, and produce a candidate whose evidence is
strong enough to seed later no-LLM Scion replay.

## Agent

- Agent: `Tesla`
- Agent id: `019ecd11-665c-7c32-b30a-0e023f0f29ef`
- Spawn mode: fresh, non-forked context
- Role: independent external VRP researcher
- Workspace scope: repository `vrp/` package plus the artifact root below
- Artifact root:
  `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615`

## Boundary

This agent is explicitly not a Scion subagent and is exempt from the normal
v3-first Scion subagent reading rule.

It must not read or use:

- `scion/`
- `scion/TASK.md`
- Scion design, audit, status, prompt, or experiment artifacts
- Scion campaign outputs or branch maps

It may read and modify only standalone VRP research material:

- `vrp/`
- standard Python tooling needed to run VRP cases
- `/home/clawd/research/vrp-independent-codex-research/phase-g-20260615`

Any positive result is external-control hypothesis material only. It is not
Scion Protocol evidence and must go through a later no-LLM Scion replay before
it can influence Scion experiments.

## Required Artifacts

The agent must maintain:

- `research_log.md`: timestamped hypothesis, code/read context, experiment,
  and decision log.
- `status.md`: current phase, active hypothesis, running commands, current
  result summary, and next step.
- `experiments.jsonl`: one row per experiment with timestamp, candidate id,
  hypothesis, command, case set, budget, seeds, baseline metric, candidate
  metric, delta, runtime, verdict, and notes.
- `candidate.patch` and `candidate_summary.md` only if a viable candidate
  survives.
- `final_summary.md` if no candidate survives.

## First-Milestone Guardrail

The first milestone is a bounded autonomous pilot:

- Start with small and medium representative cases.
- Use short budgets sufficient for signal hunting.
- Do not launch a broad WSL/server-heavy sweep without returning a proposed
  matrix for main-thread approval.
- Do not launch a single command expected to run longer than 2 hours without
  approval.
- Prefer reproducible scripts and logged commands.

## Acceptance Questions

The postrun analysis must answer:

- Which hypotheses were tried, and what evidence killed or retained each one?
- Did any candidate improve quality without unsafe runtime or case-family
  regressions?
- Did the agent demonstrate deeper research iteration, or only shallow
  mechanism switching?
- Did the independent research trace produce ideas that Scion failed to
  surface, or did it repeat the same weak/unstable patterns?
- If a candidate survives, what exact no-LLM replay tier is required before
  any Scion adoption?

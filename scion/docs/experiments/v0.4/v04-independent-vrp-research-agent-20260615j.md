# Independent VRP Research Agent J Launch - 2026-06-15

## Purpose

Launch an eleventh independent VRP-only Codex control as a long-running external
research subject. This is intentionally not a Scion subagent and not Scion
Protocol evidence. The control tests whether a plain Codex researcher, isolated
from Scion's architecture, status, audit reports, prompts, and experiment
history, can improve the standalone `vrp/` baseline and leave a process trace
that can be compared with Scion-guided branch research.

## Agent

- Subagent: `Russell`
- Agent id: `019ecd64-52d1-75b3-8b39-45ca1a78b7eb`
- Launch time: `2026-06-15T22:26:16Z`
- Context mode: fresh, non-forked

## Boundary

Hard constraints in the brief:

- Do not read, search, summarize, or open Scion files or artifacts: no `scion/`,
  no `TASK.md`, no Scion design/status/audit/planning/experiment docs, and no
  Scion experiment results.
- Treat `/home/clawd/research/or-autoresearch-agent/vrp/` as the only research
  subject, along with standard Python tooling and any problem data discoverable
  without reading Scion artifacts.
- Do not modify the main repository in place. Work in copied/scratch workspaces
  under the assigned artifact root.
- Do not run a single command expected to exceed two hours without first writing
  a proposed matrix and stopping for main-thread approval.

## Artifact Root

`/home/clawd/research/vrp-independent-codex-research/phase-j-20260615`

Expected artifacts:

- `status.md`
- `research_log.md`
- `experiments.jsonl`
- `candidate_summary.md`
- optional `candidate.patch`

## Acceptance

The result is accepted only as external-control process evidence unless the
agent returns a cleanly applying `candidate.patch` plus paired baseline/candidate
results. Even then, a positive candidate is only hypothesis material. It must
pass a later no-LLM replay before it can influence Scion experiments, Protocol
evidence, or any default solver setting.

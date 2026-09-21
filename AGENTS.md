# Scion Agent Entry

This file is the single entry point for a new agent working in this repository.
It is a routing document, not another project-state or authority record.

## Read in this order

Before changing code, documentation, or experiments, read these files in full:

1. `scion/docs/AGENT_ONBOARDING.md` — stable Scion model, boundaries, and source map.
2. `scion/docs/status/current-state.md` — replaceable current implementation and experiment snapshot.
3. `scion/TASK.md` — accepted objective, active work, and next falsifiable rung.
4. `scion/docs/READING_PROFILES.md` — choose one task-specific reading profile and load only what it names.

If the task changes Scion core or a control boundary, also read, in order:

1. `scion/design/scion-architecture-v3.md`
2. `scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md`

For experiment work, use `scion/docs/operations/experiment-runbook.zh.md` and the
specific preregistration, postrun, or terminal artifact named by current state.
Do not start from historical planning, archived reports, raw run directories, the
product-oriented root `README.md`, or `CLAUDE.md`; the latter is only a
compatibility pointer back to this entry path.

## Verify the live checkout

Documentation records a snapshot, not live process state. Before acting, run the
ordinary read-only checks below and reconcile any difference with the user:

```bash
git status --short --branch
git log -5 --oneline --decorate
tmux list-panes -a -F '#{session_name}\tdead=#{pane_dead}\tstatus=#{pane_dead_status}\tpid=#{pane_pid}' 2>/dev/null || true
```

Read only the exact experiment paths linked from `current-state.md`; do not scan or
load all historical experiment roots by default. A dead tmux pane is operational
evidence only. Scientific status comes from the corresponding terminal and metric
artifacts.

## Scope guard

Scion core must remain problem-neutral and gives the research agent a complete
ordinary algorithm source workspace that can remain a branch's verified research
head across successive attempts. Problem algorithms, objectives, feasibility
rules, and telemetry meanings stay problem-owned. Current operator-shaped generic
schema debt is named in `current-state.md`; do not extend it.

Do not add Trust/Hash authority, object identity, leases, signing, registration,
receipts, duplicate closure, distribution, deployment, packaging, build, or service
work. Do not replace long-lived algorithm research with host-selected mechanisms or
incidental quality gates. Preserve necessary Contract, Verification, Protocol,
held-out, feasibility, and deterministic Decision boundaries.

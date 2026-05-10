# Scion Documentation Index

*Last updated: 2026-05-10*

This directory is the active documentation entry point for Scion. It is
organized by document purpose, so a new development session can find the current
state, engineering map, experiment analysis, and operational references without
scanning every historical note.

## Read First

For a new agent session, read only the base pack first:

1. [Agent onboarding](AGENT_ONBOARDING.md) - project model, Scion invariants, and hard rules.
2. [v0.4 current state](status/current-state.md) - latest operating truth.
3. [Reading profiles](READING_PROFILES.md) - choose the smallest additional context pack for the task.

Do not automatically read all design docs, engineering docs, historical status
logs, old experiments, or source trees. Load them through the relevant profile.

## Directory Contract

- `../design/`: architecture and design-source documents. v3 stays at the design root; active v0.4 design sources live under `../design/v0.4/`.
- `status/`: current project state. Keep this small and current.
- `engineering/`: code maps and agentic-proposal engineering references.
- `planning/`: task manifests, worklogs, closeouts, and readiness plans.
- `experiments/`: post-run analysis and campaign interpretation documents.
- `audits/`: architecture, artifact, and evidence audits.
- `evidence/`: claim-to-artifact maps and evidence manifests.
- `operations/`: commands and operating procedures for campaigns.
- `reference/`: stable terminology, metrics, and modeling references.
- `roadmap/`: future-version planning.
- `archive/`: historical documents that are not the current operating source.

## Active Sources

### Status

- [Agent onboarding](AGENT_ONBOARDING.md)
- [Reading profiles](READING_PROFILES.md)
- [v0.4 current state](status/current-state.md)
- [v0.4 status history archive](status/v0.4-history.md)

### Design Sources

- [Architecture v3](../design/scion-architecture-v3.md)
- [v0.4 design index](../design/v0.4/README.md)
- [v0.4 design baseline](../design/v0.4/v0.4-design.md)
- [Algorithm design-space upgrade](../design/v0.4/v0.4-algorithm-design-space-upgrade.md)
- [Agentic proposal session design](../design/v0.4/v0.4-agentic-proposal-session-design.md)
- [CVRP research-surface design](../design/v0.4/v0.4-cvrp-research-surface-design.md)

### Engineering

- [Framework code map](engineering/framework-code-map/README.md)
- [Agentic proposal reference](engineering/agentic-proposal-reference/README.md)

### Planning

- [v0.4 planning index](planning/v0.4/README.md)
- [P4-05 matrix readiness](planning/v0.4/v0.4-p4-05-matrix-readiness.md)
- [P0 postrun repair task](planning/v0.4/v0.4-p0-postrun-repair-task.md)

### Experiments And Audits

- [v0.4 experiments index](experiments/v0.4/README.md)
- [v0.4 audits index](audits/v0.4/README.md)

### Evidence, Operations, Reference

- [Evidence manifest](evidence/manifest.md)
- [Scion v0.4 本地实验运行、回溯与复现手册](operations/experiment-runbook.zh.md)
- [Experiment quick reference](operations/experiment-quickref.md)
- [Experiment baseline management](operations/experiment-baseline-management.md)
- [Metrics guide](reference/metrics-guide.md)
- [Glossary](reference/glossary.md)
- [MILP model](reference/milp-model.md)
- [MILP usage strategy](reference/milp-usage-strategy.md)
- [v1.0 roadmap](roadmap/v1.0-roadmap.md)

## Maintenance Rule

Keep `docs/` root small. New current-state updates go under `status/`; new
design sources go under `design/`; run interpretation goes under
`experiments/`; audits go under `audits/`; task execution notes go under
`planning/`. When a document stops being an operating source, move it into the
matching `archive/vX.Y/` directory or leave it in the dated experiment/audit
folder with a clear index entry.

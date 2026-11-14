# Scion Design Index

*Last updated: 2026-11-15*

This directory contains design-source documents. Operational docs, experiment
analysis, engineering maps, and current status live under `../docs/`.

## Foundation

- [Scion architecture v3](scion-architecture-v3.md) - foundational architecture blueprint. Treat this as the controlling design source for governance boundaries.
- [Direct-runtime addendum](scion-architecture-v3-v0.4-direct-runtime-addendum.md) - current v0.4 implementation boundaries.

## Active Version Design

- [v0.5 continuous algorithm research](v0.5/README.md) - detailed mechanism and acceptance drafts following accepted v0.4 stage closeout; not yet implemented or empirically accepted.
- [v0.4 design index](v0.4/README.md) - historical/problem design context for the current runtime. The mechanism stage is closed; the CVRP retained-improvement objective remains open.
- [June Evidence Uplift roadmap](v0.5-evidence-uplift-roadmap.md) - superseded historical proposal, not the current v0.5 scope or a closure prerequisite.

## Archive

- `archive/v0.1/` - early MVP design documents.
- `archive/v0.2/` - v0.2 design and remediation documents.
- `archive/v0.3/` - v0.3 design documents preserved for historical reference.

## Maintenance Rule

Design documents belong here when they define architecture, version scope,
problem-surface contracts, or framework invariants. Task manifests, worklogs,
post-run analysis, and audits should stay in `../docs/` under their purpose
directories.

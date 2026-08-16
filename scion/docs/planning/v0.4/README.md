# Scion v0.4 Planning Index

*Last updated: 2026-08-16*

[`../../../design/scion-architecture-v3.md`](../../../design/scion-architecture-v3.md)
is the sole architecture authority. Current work lives only in
[`../../../TASK.md`](../../../TASK.md); current accepted state lives in
[`../../status/current-state.md`](../../status/current-state.md).

Files in this directory are historical planning records unless `TASK.md`
explicitly adopts one current item. An old status such as `active`, `accepted`,
`frozen`, `authorized` or `pending` does not survive a later V3/TASK
supersession.

## Current planning guidance

- [CVRP mechanism continuation criteria](v0.4-cvrp-mechanism-reopen-criteria-20260815.md)
  is human research-planning guidance only. It is non-production and non-gating;
  it cannot reject an H, allocate a budget, authorize a run or become a
  mechanism identity system.
- The ordered implementation and research modules are in `TASK.md`; no second
  planning checklist is current.

## Superseded authority and platform plans

The following historical families are explicitly retired. They must not be
implemented, completed, repaired or used as acceptance prerequisites:

- D2/D2b durable-owner, paired-evaluation ownership and activation plans;
- fresh-activation and historical migration/reopen plans;
- W3 generic spawn, systemd/cgroup, native-build, H11 authority/watch and
  closure plans and their review/acceptance records;
- R6/K2/K4 identity, artifact-owner and source-ledger plans;
- the July runtime-simplification plan's prompt/manifest/trace hash and resume
  identity work;
- Warehouse W2 fixed-hash/receipt proof machinery. Its domain-level locked-group
  semantics may survive only where represented by current ProblemSpec, Oracle
  and behavioral tests.

They are retained in place temporarily as historical engineering records, each
with a superseded banner, while module-scoped source reachability and deletion
work proceeds. Experiment science and terminal results remain under
[`../../experiments/v0.4/`](../../experiments/v0.4/).

## Older phase records

Phase manifests, worklogs, closeouts, readiness plans and June/July repair
designs document earlier implementation states. Read them only for a specific
historical question. They cannot override V3, `TASK.md`, current ProblemSpecs,
Protocol or current source.

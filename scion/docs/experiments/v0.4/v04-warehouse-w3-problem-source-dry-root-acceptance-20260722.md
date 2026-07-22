# Warehouse W3 problem layer and source/dry-root acceptance

*Date: 2026-07-22*
*Status: dormant problem layer and source/dry-root accepted; formal execution remains locked*

## Accepted source

The accepted source is the clean pushed commit
`b879bbc1e73550234c863e829ddaecd877f6876e` on
`origin/codex/w3-problem-owned-acceptance`.

| source | raw SHA-256 |
| --- | --- |
| `w3_fixed_arm.py` | `58fcdbecb56e1920cc6108b1571a8c56d654610e6d1166f844e0cb5e9a564909` |
| `w3_counter_fixtures.py` | `540ec8d7dd725cf0c78b0a633d19cd303e515e3dde0f1dc14c5b0855eab0052d` |
| `w3_validation.py` | `4d63854c036f2ede6b4e31da5e77ebc43f02d92a63285c1e758b4ebb232cad1a` |
| `w3_analysis.py` | `64f051cdbd7298ad9762beaa074ad13dbbd91500487887d2ae30d729b10b9f50` |
| `warehouse_w3_fixed_arm.py` tool | `407863b4d871d5a95f974f2c37f16cf484b4d71db9b229ef8e6e0d737c44e13b` |
| focused tests | `d885c2007a6dc658378f10b4afe96f0718a40ffc7655abf0d69a49abdbfac897` |
| source/dry-root plan | `70cfd9bfdd50d2fc1bf37edce5ebac1ca14575e28cf35a779ac39b1273cf8fd9` |

The problem layer owns only the fixed Warehouse ancestry, arm construction,
43-cell/172-job schedule, greedy and directed-pair facts, inert generic process
spec construction, closed-observation validation, canonical row bytes, and
deterministic replay/analysis bytes.

Prohibition scans found no `Popen`, process signal/wait call, `run_matrix`,
`close_matrix`, terminal-marker publication, raw-row publication, artifact
publication, rejected `w3_execution` import, or interchange-file path in the
problem-owned W3 modules and tool. The CLI exposes only `prepare` and
`verify-dry-root`. The remaining `subprocess.run` calls are preparation-only
read/probe operations for Git objects, Python isolation, and native-library
identity; none starts a solver job.

## Accepted dry root

The accepted root is:

```text
/home/clawd/research/scion-experiments/v04-warehouse-w3-problem-source-dry-20260722T234345Z-claw
```

It was absent before construction and was prepared from the exact pushed
source commit above. The accepted identities are:

- manifest SHA-256:
  `ad69364623cd817cc74be968528823b7bd08bf3ddef4f019476f769332ea0212`;
- Git-blob provenance aggregate:
  `af7511635a78700f58bbf9466e9ab906129bacf6ba3a85d929855d45a79caf30`;
- complete 166-file content aggregate before and after independent verification:
  `6205460c8f99c040e1845d354b4db7700cd67b09cfacd86d6404f157e7aa7bbf`.

The manifest classifies 35 sealed repository inputs as `git_blob`, 63 inputs
as `external_evidence`, and four arm workspaces as `generated`. Every sealed
repository byte was read from the recorded Git blob rather than from the
working tree. The source receipt records the pushed remote ref and the verifier
rechecked every blob object and sealed byte.

The dry-root rederivation passed with:

- exact `43` cells and `172` jobs;
- exact screening Williams position balance `7/7/7/7` for every arm;
- exact validation position totals distributed `3/4/4/4` per arm;
- all `43` greedy preflight facts Oracle feasible;
- all eight independent directed-counter fixture rows passing;
- exact inventory closure with no symlink or special-file admission;
- empty `raw`, `artifacts`, and `control` directories;
- `formal_jobs_started: 0`;
- `formal_execution_authorized: false`;
- verifier result `filesystem_mutated: false` and identical pre/post file aggregate.

The first CLI invocation used the `claw` environment's stale editable mapping
to the main dirty worktree and failed during import before the output root was
created. The accepted invocation explicitly fixed `PYTHONPATH` to the clean
worktree; the root remained absent until that accepted construction.

## Test evidence

All authoritative runs used `-W error`, fresh basetemps, and no pytest cache:

- focused W3 problem-layer tests: Python 3.12 `4 passed`;
- focused W3 problem-layer tests: Python 3.13 `4 passed`;
- H11 official collection: exact `863`;
- H11 official execution: exact `862 passed / 1 skipped`;
- `py_compile` and `git diff --check`: pass.

A broader default-suite diagnostic was also attempted. It exceeded the
120-second diagnostic limit and its first isolated failure occurred after
`296 passed` in the existing CVRP controlled-campaign fixture because
`cvrplib/E/E-n22-k4.vrp` did not resolve under the clean worktree's configured
safe data roots. That unrelated data-root fixture is not a W3 source/dry-root
gate and no W3 failure was observed.

## Remaining lock

This acceptance does not authorize any of the 172 jobs to run. The currently
accepted generic surface closes process/cgroup capture as
`ClosedSpawnObservation`, but generic invocation terminal ownership and opaque
raw-row/artifact publication are not yet implemented and accepted. Until those
generic owners exist and a separate fresh-root launch review passes, Warehouse
W3 remains dormant and this root must stay read-only.

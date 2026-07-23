# W3 composition and launch-readiness source acceptance

*Date: 2026-07-23*
*Status: dormant source composition accepted; external installation and formal launch remain locked*

## Accepted source

The independent Warehouse W3 composition and launch-readiness source is
accepted at clean pushed commit
`82d5394b5f3157fe5783254b3f02a943f77383f2` on
`origin/codex/w3-problem-owned-acceptance`. Its exact Git tree is
`17f3a3a679abf6c516bee347a99e2db799540d5b`.

| source | raw SHA-256 |
| --- | --- |
| `launch_authority.py` | `27d851ac751e66a175e5fc4972b24faac864fc61e91a6d5b92702b1c8fa5fc76` |
| `systemd_acquisition.py` | `d066e1d7632531075b26c800b4ab90cde6401217f4e8b71caf60529b66debb5f` |
| `invocation_terminal.py` | `804ee1cc47c8e11b469be23ad8903738082c51afeeb586c516e6d29e000899d8` |
| `spawn_backend.py` | `e0b2fab727e4474959c0bd67d8c4a9968f1c4bee5c4f87f9ce73f433b3124b7d` |
| `w3_composition.py` | `fcf88c8296f32c0b235b6eb3f661a7f25cd7c38b4401db6f700d1e60ba9527fd` |
| `scion_w3_tool.py` | `f6dc563d4eff466f030bb21b745f5842f38afdafcaeaacb8fe8afd7fb0344d19` |
| run unit template | `7973b9f7403a448f323e9f5ac8ac17999a6e407a2b8844e5f8b81f4f84ba75e2` |
| close unit template | `dd493ee0dfc54611576dac5749c78370ea40a286cac1a4ed91cebf60e4f79ad2` |

The source authority closes over the exact scientific design, corrected
trusted-execution design, native contract and external native-acceptance
record:

- scientific design:
  `5538a81b6d7980888cf594b07244a0b4863c57db85f3a04beb8f84555ad4bb35`;
- corrected execution design:
  `8e2a610eeec15ca1bb118d7affa855b753b320be1ae055b2e517613731d10945`;
- native contract:
  `afaa0b7e60b820e168d1300ecdf8a0f2085e5dad7461e7f7bbc1edbf88524f27`;
- external native-acceptance record:
  `51948ccda6b9a24811c05e4fd3795ddefcf1b62ac2e1604297e70ede91700de7`.

## Closed ownership and launch path

`AcceptedLaunchAuthority` is a strict canonical duplicate-free JSON authority.
It binds the source commit/tree, accepted dry-root manifest and root, nonce
ledger, row/artifact policy, all four design/acceptance identities, sealed
environment and template identities, source identities, and the closed
provenance union. `InstallationRecord` separately binds exact authority,
installation and projection paths, their cross-identities, and the configured
run/close unit pair. Neither record can be inferred from an experiment
directory.

The nonce owner first creates and fsyncs one external claim with
`O_CREAT|O_EXCL`, then opens the invocation-local claim. A crash after the
external claim consumes the nonce; there is no reuse, retry or resume route.

Systemd acquisition is read-only. The adapter exposes no manager mutation
method and acquires the exact loaded run/close unit configuration, security
properties, path allowlists, lifecycle edges, timeouts, user/group/umask, and
the structured final `ExecStopPost` result. It descriptor-pins the process,
cgroup and boot identities, requires the exact `.control` stop environment,
and proves the supervisor and job cgroups are empty before `UNIT_DRAINED`.

The installed dispatcher has three explicit paths:

- `run`: reacquire loaded configuration before nonce consumption, validate
  readiness, claim nonce, bind durable invocation lineage, execute the exact
  172-job schedule through generic `ServiceCgroup` and `SpawnBackend`, validate
  each complete observation in the Warehouse layer, publish its opaque row,
  then commit `RAW_COMPLETE`;
- `seal-unit-drained`: reacquire the same invocation and stop topology, then
  seal the generic drained fact;
- `close`: acquire the structured final systemd fact, seal `UNIT_FINAL`,
  reread the exact 172 rows, run problem-owned replay/analysis, and publish the
  generic `COMPLETE / CLOSED` artifact transaction.

Problem-owned code owns schedule and scientific bytes. Generic code owns
process/cgroup evidence, terminal facts, raw rows and opaque artifacts. The
composition does not expose `StartUnit`, `StopUnit`, `RestartUnit`, a network
client, `subprocess`, `Popen`, retry or resume.

The cgroup cleanup boundary was tightened as part of this source: cleanup now
requires an in-process writer-issued capability bound to the exact durable
lineage and active settled job. Constructed lookalike row or incomplete facts
cannot authorize cleanup. The frozen public execution `__all__` surface is
unchanged.

## Executed gates

All pytest gates used `-W error`, fresh basetemps and no pytest cache:

- composition-focused matrix: Python 3.12 and 3.13 each exact `132 passed`;
- full generic execution directory: Python 3.12 and 3.13 each exact
  `1723 passed / 1 skipped`;
- H11 implementation oracle: Python 3.12 and 3.13 each exact `456 passed`;
- H11 public C2a surface: Python 3.12 and 3.13 each exact `74 passed`;
- H11 official collection: Python 3.12 exact `863`;
- H11 official execution: Python 3.12 exact
  `862 passed / 1 skipped`;
- Warehouse problem plus composition: exact `9 passed`;
- generic formal case: exact `79 passed`.

Black, `compileall`, `git diff --check`, forbidden launch/network scans, the
frozen public-surface test, and the targeted H11 source-hash tests pass.
Temporary native test libraries were unlinked afterward.

`systemd-analyze verify` parsed both dormant templates and reported only that
the projected Python executable under `/var/lib/scion/projections/w3/...` does
not yet exist. That is an expected pre-install observation, not a successful
live installation check.

## Independent zero-job acceptance

The accepted problem dry root remains:

```text
/home/clawd/research/scion-experiments/v04-warehouse-w3-problem-source-dry-20260722T234345Z-claw
```

Independent composition verification rederived its exact manifest
`ad69364623cd817cc74be968528823b7bd08bf3ddef4f019476f769332ea0212`,
`43` cells, `172` jobs, zero formal jobs and
`formal_execution_authorized: false`. Its complete filesystem identity was
identical before and after verification:
`2a51526eb2771710922c519dd5972c91072b0adbe4215731177f4f906f277f15`.
The accepted root was not written.

No W3 authority, installation or projection exists under
`/var/lib/scion/authorities/w3`, `/var/lib/scion/installations/w3`, or
`/var/lib/scion/projections/w3`. No systemd unit was installed or started.

## Remaining lock

This acceptance closes the source composition and its independent dry-root
readiness gate only. A later root-owned installation acceptance must create
and verify the exact external authority, installation record, projection and
loaded manager receipt on this accepted source identity. Only after that
separate acceptance may a human explicitly authorize the first `StartUnit`.

Formal Warehouse W3 execution remains unauthorized. No campaign root, nonce
claim or formal job was created by this review.

# W3 generic invocation terminal and opaque publication acceptance

*Date: 2026-07-23*
*Status: dormant generic boundary accepted; formal W3 launch remains locked*

## Accepted source

The problem-neutral invocation terminal and opaque row/artifact publication
owner is accepted at pushed source commit
`bf4c74906d91a9dc4ef489c430602e2242fb95e2` on
`codex/w3-problem-owned-acceptance`. The remote branch resolved to that exact
commit after push.

| source | raw SHA-256 |
| --- | --- |
| implementation plan | `67e5111110bcdd454ea24318aa17b2a69ab8577b99e8a5febe376cd0c098fb49` |
| `invocation_terminal.py` | `c894e3a05bf4a000ed0d3a330d70b72497b4215ab39c993764eeb92e4e9526d3` |
| execution public surface | `7b92b86c88afed77bfae589de7cf622263b08464998c4a032c56e807a9480992` |
| focused terminal tests | `ee5b4fc23b707f76df7148e90618750611c962b56be4d2f67865a1564af35b4a` |
| public-surface tests | `ee5f9958516df2712b624b43cf6689dd045de34fbb19c69011aa4015415daee8` |

The exact five-entry Git tree listing has aggregate SHA-256
`78d0fb559a0e9ed2518ed338cfb55e34657b59ef17cb12b043f4a4c427e8eff6`.

## Accepted ownership boundary

The generic layer now owns:

- one exact `TerminalPolicy` binding authority, manifest, nonce, row count,
  artifact names and zero retry/resume/reuse;
- a final, same-process, noncopyable `InvocationWriter`;
- complete durable `ClosedSpawnObservation` evidence before each opaque row;
- exact increasing row ordinals and an ordered `RAW_COMPLETE` identity;
- copied systemd `UNIT_DRAINED` and `UNIT_FINAL` validation;
- one opaque problem-acceptance digest leading to `COMPLETE`;
- one exact ordered opaque artifact bundle leading to `CLOSED`;
- read-only classification and full digest-chain verification.

Generic code never parses a problem row or artifact body. It has no Warehouse,
CVRP, ALNS or VNS import/name and no network, subprocess, timeout, polling,
sleep, budget, truncation, retry or resume path.

The root inventory is exact `control/evidence/raw/artifacts`. Root traversal
opens every path component with descriptor-relative `O_NOFOLLOW`; the durable
start fact binds the root device and inode. Individual publications use an
unnamed `O_TMPFILE`, file fsync, no-replace `linkat`, target-inode
revalidation and directory fsync. `AT_EMPTY_PATH` is used where permitted; an
unprivileged process uses the documented `/proc/self/fd/<fd>` plus
`AT_SYMLINK_FOLLOW` form while retaining the same open unnamed inode.

Artifact files are fsynced in one private directory and the exact bundle is
published with `renameat2(RENAME_NOREPLACE)`. `CLOSED` is published only after
the complete terminal chain and is immediately reread against final artifact
bytes. Existing facts, rows, final directories and closure markers are never
overwritten.

## Fail-closed evidence

Focused tests cover:

- `PREPARED -> ACTIVE/EVIDENCE -> RAW_COMPLETE -> UNIT_DRAINED ->
  UNIT_FINAL -> COMPLETE -> CLOSED`;
- complete observation round-trip including non-UTF-8 stdout/stderr bytes;
- gap, duplicate, digest, exact-type, policy-bound and artifact-order
  rejection;
- writer copy/deepcopy/pickle/reopen rejection;
- existing row/fact/final/marker collision without overwrite;
- injected unnamed-file link and artifact-directory rename failure;
- evidence, raw identity, copied systemd fact, artifact and incomplete-fact
  tampering;
- extra root entries and root/child symlink rejection;
- read-only inspection with identical pre/post tree identities.

Crash-visible evidence-only, unexpected row, staging directory, artifact
directory without `CLOSED`, malformed terminal fact or broken digest chain is
classified `UNKNOWN_INTEGRITY_HOLD`. The layer has no recovery, reuse or
success-upgrade path for those states.

## Executed gates

Every pytest gate used `-W error`, a fresh basetemp and no pytest cache:

- terminal/public focused: Python 3.12 exact `18 passed`;
- terminal/public focused: Python 3.13 exact `18 passed`;
- generic execution-core regression: Python 3.12 exact `249 passed`;
- generic execution-core regression: Python 3.13 exact `249 passed`;
- H11 implementation oracle: Python 3.12 exact `456 passed`;
- H11 implementation oracle: Python 3.13 exact `456 passed`;
- H11 public C2a: Python 3.12 exact `74 passed`;
- H11 public C2a: Python 3.13 exact `74 passed`;
- H11 official collection: Python 3.12 exact `863`;
- H11 official execution: Python 3.12 exact
  `862 passed / 1 skipped`.

Black check, Python 3.12/3.13 `py_compile`, `git diff --check`, AST import
inspection and problem/network/subprocess prohibition scans pass. The two
native ABI modules compiled only for testing were removed afterward. One
broader execution-directory diagnostic reached 67% without a failure before
its 120-second diagnostic limit; the exact authoritative gates above were then
run independently to completion.

## Non-claims and next gate

No solver, provider, network client, systemd manager call or formal W3 job ran.
No experiment root was constructed; pytest basetemps contain synthetic copied
facts only. This acceptance does not modify or authorize the accepted zero-job
W3 problem dry root.

This slice does not own external authority installation/projection, a durable
nonce ledger, systemd property acquisition, `ExecStopPost` command wiring or
campaign composition. A separate W3 composition and launch-readiness review
must close those owners on one clean pushed commit before any guarded formal
launch can be considered. Formal execution remains explicitly unauthorized.

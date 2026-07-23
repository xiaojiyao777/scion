# W3 root installation and first-launch design acceptance

*Date: 2026-07-23*
*Scope: design only; no root application or `StartUnit` occurred*
*Decision: `DESIGN_ACCEPT`*

## Fixed authority

The accepted implementation plan is:

```text
docs/planning/v0.4/v0.4-w3-root-installation-loaded-manager-launch-plan-20260723.md
raw SHA-256:
49196769c0c70f56714791a80e6c683d31d547c5f4e47cc7216ea1b5fda81eb6
```

The plan is subordinate to `design/scion-architecture-v3.md` and the accepted
W3 composition/launch-readiness contract. It authorizes implementation and
non-privileged candidate preparation only after the implementation itself
passes fixed-source review. It does not by itself prove an installation,
loaded manager, nonce claim or formal result.

## Closed design gates

The fixed design closes:

- launch-source Git object provenance distinct from the accepted problem dry
  root;
- an exact reproducible wheel builder and a separately inventoried Python 3.12
  runtime environment;
- capability-free runtime environment probes before nonce claim and before
  `RAW_COMPLETE`;
- descriptor-pinned import of user-owned candidate bytes into root-owned
  quarantine and same-filesystem staging;
- root-owned one-selection, phase-ledger and receipt authority;
- FD-bound `open_tree`/`move_mount` projection with recursive-private
  propagation and exact mountinfo receipts;
- exact systemd 255 manager-owner, Ref/Load/read/fsync/Unref and loaded-unit
  evidence;
- durable crash-consuming `START_ISSUED` followed by only
  `StartUnit(unit, "fail")`;
- definite returned/rejected versus dispatch-unknown outcomes with no reissue;
- a closed pre-claim exit ABI and root-owned terminal classification;
- generic deployment lifecycle versus Warehouse problem-semantics ownership.

## Review closure

The initial fixed plan SHA
`1ba192d0354ec6d7369f1894d22620abf3ec4f92236a948261abfd26512378de`
was rejected with open P0/P1 findings. The next two fixed revisions were also
held until candidate TOCTOU, environment closure, manager pinning, mount
namespace/propagation, one-shot start and unique selection were fully owned.

For the final fixed SHA above:

```text
architecture/runtime review: P0=0 P1=0 P2=0 ACCEPT
root/install/start review:    P0=0 P1=0 P2=0 ACCEPT
host feasibility review:      P0=0 P1=0 ACCEPT
```

The final reviewers independently verified the raw plan SHA before reporting.

## Operational boundary

At acceptance time:

- `/var/lib/scion` did not exist;
- neither W3 system unit fragment existed;
- no authority, installation, projection, root selection or manager receipt
  existed;
- the accepted dry root still had zero formal jobs and no invocation terminal
  root;
- no nonce was generated or claimed;
- no `Reload`, `LoadUnit`, `RefUnit`, mount or `StartUnit` action was executed.

The current non-interactive session has no passwordless sudo. Production code
must check EUID and must never invoke sudo or prompt for credentials. A later
root phase therefore requires an interactive root shell after source,
candidate and independent receipt acceptance.

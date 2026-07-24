# W3 root composition and launch owner source candidate

*Source candidate commit: `5d3efd5e`*
*Branch: `codex/w3-problem-owned-acceptance`*
*Status: pushed; independent fixed-source review pending*

## Scope closed in source

The candidate implements the accepted root installation and first-launch plan
without performing a root operation:

- non-root Git/archive/double-wheel/environment/candidate closure and
  independent reopen;
- root-owned K0-K8 installation with no-replace intent/commit recovery,
  external stores and authorities, FD-bound projections, unit publication,
  split manager reload and loaded-pair acquisition, installed replay, and
  final sealing;
- root-selected one-candidate/one-nonce authority and prospective human
  authorization binding;
- fresh pre-start replay immediately before one durable `START_ISSUED` spend
  and exactly one `StartUnit(unit, "fail")`;
- durable returned, definite-rejected, and dispatch-unknown outcomes with no
  retry, stop, restart, kill, reset, or generic manager passthrough;
- installed pre-claim status ABI `70-73`;
- read-only terminal progress, pinned unit acquisition, independent
  Warehouse replay, and root-owned terminal classification.

The thin administrative CLI has exactly eight commands:

```text
prepare-candidate
verify-candidate
apply-root
verify-installed
record-start-authorization
start
inspect-terminal
accept-terminal
```

`prepare-candidate` and `verify-candidate` reject effective UID zero.
`apply-root`, `verify-installed`, `record-start-authorization`, `start`, and
`accept-terminal` require effective UID zero. `inspect-terminal` is usable by
the unprivileged runtime account. No command invokes sudo.

## Final-byte verification

All counts below were rerun after the final Black pass:

- Python 3.12 Warehouse W3 problem and CLI: `245 passed`;
- Python 3.12 non-formal/non-H11 generic execution: `452 passed`;
- Python 3.12 formal-case and observer fixtures: `132 passed`;
- Python 3.12 systemd formal fixture: `863 collected`, `862 passed`,
  `1 skipped`;
- Python 3.12 H11 C2e oracle: `456 passed` as exact disjoint
  `142 + 108 + 206`;
- full execution directory: `1903 collected`, `1902 passed`, `1 skipped`;
- Python 3.13 candidate/terminal/admin-CLI focus: `28 passed`;
- `compileall`, Black, forbidden-operation source scans, and
  `git diff --check`: pass.

The local CPython 3.12 and 3.13 native extensions used for test collection are
untracked build products and are not part of the commit.

## Remaining locks

This record is not a production candidate or root acceptance. Two independent
reviews must inspect the exact fixed source closure and report P0=0/P1=0.
After that closure, one non-root candidate may be prepared from the accepted
Warehouse dry root and accepted native external record and must be
independently reopened. Root application remains forbidden until that
candidate also closes P0=0/P1=0.

No `/var/lib/scion`, root selection, unit fragment, mount, manager mutation,
nonce claim, terminal root, or formal job was created in this source phase.
The later root phase requires an interactive root shell and does not authorize
code-invoked sudo.

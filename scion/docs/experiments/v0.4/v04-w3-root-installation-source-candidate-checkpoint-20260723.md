# W3 root-installation source-candidate checkpoint

*Date: 2026-07-23*
*Status: pushed production-unwired source foundation; not candidate, root, or
launch acceptance*

## Fixed source

The source candidate is pushed on
`codex/w3-problem-owned-acceptance` at exact commit
`eee9e0f6916e1b4e5505a599e345a263911881f2`. It implements:

- capability-free environment inventory and external-runtime rehash;
- a non-root staging venv/offline-install facade, with distinct staging,
  candidate and simulated-relocation verification paths;
- exact Git/source, selection, sealed-store, candidate and verification
  receipts;
- FD-pinned immutable import, no-replace publication and cloned-mount
  primitives;
- root phase, loaded-manager, start-authorization, issue and dispatch receipt
  contracts;
- binding of the prospective user statement to one preparation intent/commit,
  root selection and complete typed phase tuple.

The final 13-file review manifest SHA is
`d7743f307a0ee0bc52bad8497e343e0bd8e6073d4a4e4ca5c2e95c5a4dfde0fb`.
The prospective intent raw SHA is
`206399f398a43eaef7afd5a560cbc09aae35b509c940677e8f487682ffbcfc6f`.

## Verification

- Python 3.12 focused contracts: `90 passed`;
- Python 3.13 focused contracts: `90 passed`;
- Python 3.12 full execution regression: `1798 passed / 1 skipped`;
- Python 3.12 and 3.13 compile checks: pass;
- Black and whitespace checks: pass.

The focused Python 3.13 run uses a fail-on-use process-local native ABI stub;
the accepted Python 3.12 native extension is loaded for the Python 3.12 gates.
No test invokes a real mount, D-Bus manager mutation or `StartUnit`.

Two independent final reviews report `P0=0 / P1=6 / P2=0`. The P1 items are
deliberate blockers, not waived findings:

1. no exact production owner yet reacquires the full live pre-start gates;
2. loaded-manager properties are not yet mechanically derived from and bound
   to the same canonical configured pair;
3. root effects lack the durable intent-before-effect/commit-after-reopen
   transaction and crash classifier;
4. environment content lacks wheel/native/import/D-Bus semantic closure and a
   typed final-path relocation receipt;
5. candidate verification lacks double-wheel/tool inventory, dry-root
   `LAUNCH_READY` and nonce/terminal absence closure;
6. prospective authorization cannot be consumed until candidate verification,
   root-owned receipt reopening and two fixed-source acceptance reviews are
   bound.

## Operational lock and next slice

No `/var/lib/scion`, unit fragment, mount, manager reload, nonce claim,
`StartUnit` call or formal job was created. This checkpoint is not usable for
root application or launch.

The next slice is candidate artifact closure: deterministic offline
double-wheel evidence, complete wheel/native member inventory, semantic
`environment-content.v1`, typed simulated/final relocation receipts, and
candidate dry-root/absence verification. Root transaction/DAG work follows
only after that source is clean, pushed and independently accepted; the thin
CLI is wired last.

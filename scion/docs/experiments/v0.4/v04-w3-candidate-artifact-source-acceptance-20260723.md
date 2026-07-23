# W3 candidate artifact source acceptance

*Date: 2026-07-23*

## Scope

This checkpoint accepts the dormant source owners for the Warehouse W3
double-wheel, semantic environment, simulated relocation, candidate
dry-root/absence gate, root intent/commit DAG and prospective start binding.
It does not claim that a production candidate, wheel, environment, root
installation or systemd unit has been created.

The accepted architecture boundary remains the fixed
`v0.4-w3-root-installation-loaded-manager-launch-plan-20260723.md`. Generic
transaction and manager codecs remain in
`scion.runtime.execution.external_installation`; Warehouse wheel,
environment, dry-root and launch semantics remain problem-owned.

## Closed source facts

- The public wheel builder has no runner or Git-reader injection. It uses the
  fixed bubblewrap, no-network, Python 3.12 and pip-wheel invocation.
- The public wheel verifier reacquires the local Git commit/tree/blob graph,
  two exact Git archives and two exact wheel inodes. Tar regular members and
  their directory-parent closure equal the source receipt; both wheel member
  inventories, Python/template bytes and the accepted native ELF are exact.
  Git replacement objects are disabled.
- The verifier repeats Git, archive and wheel acquisition after byte equality,
  closing the same-inode equality window. The injected builder returns a
  separate test-only artifact type rejected by the public verifier.
- The public-API threat model is explicit: private Python construction is a
  convention, not an in-process security boundary. Acceptance is based on the
  reviewed non-injected production route plus reacquired external file facts,
  not on a forgeable Python object seal.
- The environment owner runs one fixed target-interpreter probe, closes the
  actual loaded Python/native/shared-library set, reads D-Bus package metadata
  from inventoried bytes, proves ELF identities and binds all environment-
  external runtime files through the generic content receipt.
- The candidate gate reruns complete candidate verification, reopens the
  sealed wheel and receipt bytes, calls the accepted W3 launch-readiness
  verifier on the four exact sidecars, accepts the historical `0700` dry root
  under read-only acquisition semantics, and repeats complete candidate
  verification after inspection.
- Typed absence covers the final sealed/environment/projection roots,
  authority/installation entries, both unit templates and instance drop-ins,
  both nonce claims, terminal/control/raw/artifacts, cgroup and process facts.
- `InstalledAcceptance` v3 removes the former final-phase hash cycle. Its raw
  bytes bind the first eight complete intent/commit phases; the ninth
  `INSTALLATION_ACCEPTED` intent authority and commit effect both equal the
  acceptance raw SHA. Every production consumer verifies the full nine-phase
  DAG.

Final source SHA-256 values:

- `w3_wheel.py`:
  `9f82e14dc9d529276de4b99eda69e12ce422511c49dd281dc29440721a85a83b`
- `w3_environment_receipts.py`:
  `bf6ee8e0f14c5f28d62ecc57f81e639aa44e61dd3d304703d44bb8f32d1dfc88`
- `w3_candidate_gate.py`:
  `3279be599bb836bfcc8988557569975a9e6c67949dc96b81b493f859234f423d`
- `w3_installation.py`:
  `0ca0ff43cbbfa77af5bc7e9e697f31bc748c80f32507c16664c10423b30d7f82`
- `external_installation.py`:
  `fe2e960eeae5c3ac0d40ada6ba1c273e540ee67ff6347e013a3b834d87517d55`

## Verification

- Main combined artifact/install/launch gates:
  Python 3.12 `142 passed`; Python 3.13 `142 passed`.
- Focused environment plus generic integrity:
  Python 3.12 `26 passed`; Python 3.13 `26 passed`.
- Candidate final-reverification gate:
  Python 3.12 `14 passed`; Python 3.13 `14 passed`.
- Candidate source/Git replacement-object gate:
  Python 3.12 `16 passed`; Python 3.13 `16 passed`.
- Root transaction plus start-authorization gate:
  Python 3.12 `52 passed`; Python 3.13 `52 passed`.
- Python 3.12 complete execution suite:
  `1815 passed / 1 skipped`.
- Python 3.12 and 3.13 `py_compile`, Black over all 13 changed Python files,
  and `git diff --check` pass.
- Independent final review at the fixed source hashes reports
  `P0=0 / P1=0 / P2=0`.

## Operational boundary and next work

The shell remains effective UID 1001 and has no passwordless sudo. systemd 255
is live, but `/var/lib/scion`, both W3 unit templates and the external nonce
claim root remain absent. No root path, mount, manager state, nonce or formal
job was created.

Root use remains locked. The next source slice must split manager reload from
loaded-instance acquisition, add typed aggregate receipts and the concrete
root composition/partial-hold owner, add installed-state/dry-root/pre-start
reacquisition, and expose the fixed `apply-root`, `verify-installed`,
`record-start-authorization` and `start` CLI surfaces. Only after that source
also closes at P0=0/P1=0 may the production candidate be prepared and an
interactive root-capable session perform installation acceptance. The
prospective human authorization remains unbound and cannot yet authorize
`StartUnit`.

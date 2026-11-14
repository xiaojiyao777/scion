# Scion v0.4 W3 native spawn/build acceptance

Status: accepted native slice; later W3 layers remain locked

Date: 2026-07-18 UTC

## Decision

The first corrected W3 implementation slice is accepted at pushed commit
`01873dad488d6e4d45e2fdad8af524eb60edf4f0`, Scion tree
`ff5ebc399778634862dfea0804f2c193b00031e6`.

This decision covers only the CPython native spawn/build ABI frozen by
`v0.4-w3-native-spawn-build-acceptance-20260718.md`, raw SHA-256
`afaa0b7e60b820e168d1300ecdf8a0f2085e5dad7461e7f7bbc1edbf88524f27`.
It authorizes the next generic `SpawnBackend`/cgroup/systemd layer. It does not
accept the generic guardian, terminal publisher, problem-owned Warehouse W3
materializer, dry root, formal W3 jobs, CVRP F1 jobs, or a solver experiment.

The accepted root is:

`/home/clawd/research/scion-experiments/v04-w3-native-acceptance-20260718T221215Z-r6-claw`

The earlier r5 root remains receipt-rejected. Its byte-identical artifact facts
were used only as a frozen reproducibility target; no r5 receipt or test status
was promoted into this decision.

## Frozen source

The five accepted source blobs are:

- `pyproject.toml`: `bc924818...deb4e5a`;
- `scion/runtime/native/__init__.py`: `e7f50a75...2e3cb07`;
- `scion/runtime/native/spawn_into_cgroup.c`: `c132261e...f9a75`;
- `scion/tests/unit/runtime/test_native_spawn_into_cgroup.py`:
  `abd5dd71...6fa52`;
- `scion/tests/fixtures/native_spawn_probe.c`: `b26f7dc2...a36e7`.

Before execution, two independent R5 reviews reported
`P0=0 / P1=0 / P2=0` and `PREBUILD_ACCEPT`. Their final authority closed the
actual `umask 0077` build requirement, the verifier's regular-file/no-follow
semantics, every wrapper tool dependency, six Python runtime literal-to-
canonical library mappings, and the two future rehash transactions.

The final prebuild anchors are:

- authority index: `d1345111...d14d6b`;
- environment index: `cb5a0e1d...834e6d`;
- canonical environment: `934b01b2...98a37`;
- transaction authority: `a10696fa...a375c`;
- prebuild rehash: `62f3e678...90f13`, all 2074 files and 22 aliases matched.

## Exact execution result

Both independent offline builds ran once, without a shell, under the frozen
clean environments and `umask 0077`. There was no automatic retry, runtime
timeout, output cap, or truncation. All four build commands returned zero.

Both builds produced byte-identical artifacts:

- wheel: `15cd05e29c87c3321199ee2b098bbf425850f05b0ca118f699b7341682426109`;
- native extension:
  `3d747973bc2eb3b0f6fda68f288987c7b988820eb24df2ff617aa567071803fc`;
- native probe:
  `8e653a076dfd86d513f3ef4493058e124bde8af61b1c5afd4879ae07cc47c936`.

Each wheel had the same frozen 403-member table. The extension and probe
`readelf` and dynamic-symbol receipts matched the frozen artifact basis. The
wheel was installed once into a fresh copied venv; its 803 installed `RECORD`
entries were present and the installed extension retained the accepted hash.
No extra import helper ran.

The sole formal systemd-255 delegated-cgroup transaction passed `64/64` tests
in `0.85s`, with no skip or xfail. The wrapper's raw NUL argv contained exactly
one wrapper-injected `SCION_TEST_DELEGATED_CGROUP`. The target cgroup identity
matched the planned unit, began and ended with `populated 0`, was removed, and
the transient unit was collected. The two expected `Fatal Python error:
Aborted` blocks in stderr are the isolated RELEASED and POISONED destructor
fail-stop fixtures; the pytest and unit transaction returned zero.

The mandatory rehash checkpoints both passed without drift:

- after build 2: `01d682a2...a75f`, 2074 files / 22 aliases;
- after the formal test: `499329e8...6be5`, 2074 files / 22 aliases.

No R6 process, unit, unit cgroup, or `w3-target` remains live.

## Receipt closure and review

The first postrun external record, SHA `aa818f6d...25238f`, was rejected rather
than accepted because it bound result summaries but not every actual build and
rehash transaction or low-level argv/cgroup/ELF receipt. No execution was
repeated. A 50-entry acyclic acceptance-input index was added to bind the
actual transactions, complete stdout/stderr, artifacts, NUL argv, cgroup
identity/events, and ELF/dynsym evidence.

Final receipt anchors are:

- acceptance-input index: `33c534bf29f60b1873ef96a5dd308d0fd462713fa76a10b4c6e6dfe15dc706a6`;
- external acceptance record: `51948ccda6b9a24811c05e4fd3795ddefcf1b62ac2e1604297e70ede91700de7`;
- formal test acceptance: `402ab741283e6fcb95de0040ef5f9d5ce62bf21bb2db2f13d050944f6dba41f9`;
- accepted marker: `8a49bce2c1b5fd08d150b1e6af9f04c1e27a96120e8978d0f44d4df1c2234592`;
- final acceptance index: `5f2047e6b47bbe709bc162441c2e46c58af48e759ea7d3b9f2ea91078454fe42`.

Two independent POSTRUN R2 reviews recomputed the 50 indexed hashes and every
direct external-record binding. Both reported
`P0=0 / P1=0 / P2=0` and `NATIVE_ACCEPT`.

The build-1 file named
`artifact-receipt-overbroad-root-diagnostic.json` is excluded from acceptance.
It came from an operator-only diagnostic that incorrectly treated a fixed,
version-controlled repository path as a disposable build root. The accepted
artifact receipt uses the contract's R6 disposable-root predicate and has zero
violations; neither the input index nor the external record depends on the
overbroad diagnostic.

## Continuation lock

The next action is design-first implementation of the generic
`SpawnBackend`/cgroup/systemd wrapper against the accepted native ABI. Its
acceptance still requires the parent design's systemd 255 GC/handoff fixture
and explicit failed-close `CollectMode=inactive` behavior. Only after that may
the generic guardian/terminal layer and problem-owned Warehouse W3 layer be
implemented and independently accepted. No W3 dry root or formal solver launch
is authorized yet.

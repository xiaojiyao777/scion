# CVRP F1 Materializer Acceptance

*Date: 2026-07-18*
*Decision: implementation accepted; formal execution locked*

## Scope

This acceptance covers only the no-LLM F1 ancestry materializer, sealed-root
verification, 256-row closer/analysis, CLI and focused tests. The scientific
contract remains the frozen four-arm, 64-cell/256-job design at SHA-256
`a8167117e147c8fe4bcccb808ad267a8a88fa9ba864e1389af40497d43d07faa`.

No new dry root or formal root was created, and no solver job was started. The
old diagnostic root ending `final-r6-claw`, manifest
`1842f425adfff43b58727175d79f90c79fb7627e0f75c649b686020f0edf9ee8`,
binds superseded source hashes and remains rejected.

## Accepted source set

| File | SHA-256 |
| --- | --- |
| `f1_contract.py` | `579972f9e4f43ed0e85983ea66447afb7745be5c3a615e1837dce794e1402655` |
| `f1_io.py` | `8466b9554ef31a7846aa6c3614bc245c8c9794d4d7d1d86608857a8700c3f2bd` |
| `f1_materialization.py` | `32cb519b49f206c9fa0a397417eab796f26f7cc22c3027c07eb95ab3208a7be3` |
| `f1_runtime.py` | `5a2113f1ea8d7021f046fa83e078b17d2b3df55b96c1b84e90ac2e64caa03a13` |
| `f1_preparation.py` | `0fa4dc0e091909658b71893ab3979d0320f9b9f5d0d89a429180a92d65a4fae2` |
| `f1_runner.py` | `54543c54c29744b851e82bc9d7a43a5b57b36dbd3f33f662cf04b064835d41ee` |
| `f1_analysis.py` | `30f8f422f8aceb98ad155bf85e13592f9bb06da97390b3a775d29c9b8011b8c4` |
| `f1_ancestry.py` | `7393b30faab98d78fb8d030a346bcee3581d89b96e890cde18a98ebb3ed3cc6a` |
| `tools/cvrp_f1_ancestry.py` | `0614598de4d1cc6d45c0b5f5cfe70e9a0b1a93a17e81edc87a97509201c58bc3` |
| `test_cvrp_f1_ancestry.py` | `83c2c61552e88591cbd1b5250765b6572b1eafd9c4e6463a1642207f9547bdfe` |

Two independent final-hash reviews reported materializer `P0=0/P1=0`.
Each ran the focused suite once, with `28 passed` in 79.28 and 81.83 seconds.
One review reported P2=0; the other retained two non-blocking audit follow-ups:
preserve a typed-missing leaf's original reason in one scheduler summary, and
strengthen closer cross-validation of timing/process/payload failure fields.
Neither changes scientific direction, disposition or closure authority.

## Scientific and integrity findings

The accepted implementation:

- seals and reparses all 16 exact `.vrp + .sol` pairs;
- preserves real R11c initial-distance, SWAP*, best-update and acceptance
  telemetry, while leaving unavailable throughput/SA temperature typed missing;
- compares `(fleet_violation, total_distance)` lexicographically for W/L/T,
  including valid fleet-difference observations, but excludes them from the
  equal-fleet distance delta;
- keeps zero/insufficient evidence `unknown` and `invalid_or_incomplete`;
- revalidates all 256 rows and terminal failure counts before deterministic
  report/receipt publication and byte-replay recovery;
- keeps mechanism and execution-integrity facts out of promotion, profile
  selection, prompt, reward and later B2/B3 authority.

## Formal launch blockers

Formal F1 remains locked by three independent P1 boundaries:

1. no external expected pushed-commit/design/source/manifest authority exists;
2. verified interpreter/package/case bytes are reopened by mutable paths rather
   than one FD/immutable hash-to-exec closure;
3. there is no durable STARTED/ACTIVE guardian with cgroup/descendant ownership
   and runner-death terminalization.

The accepted materializer may be committed as dormant evidence tooling. A new
dry root and formal launch require a separately accepted generic execution-
integrity envelope that closes all three boundaries; committing this source is
not itself launch authority.

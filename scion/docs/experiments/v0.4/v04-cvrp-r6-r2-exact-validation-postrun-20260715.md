# CVRP R6-R2 Exact Validation Postrun — 2026-07-15

## Verdict

The exact cumulative R6 round-2 candidate remains promising on a fresh,
out-of-sample validation split, but it is not yet validated or promotable.
Protocol returned `expand_validation / VALIDATION_EXPAND_HIERARCHICAL_UNCERTAIN`.
The next scientific action is the preregistered 12-case expanded validation of
this same candidate, with no new Hypothesis or Code call.

## Identity and execution integrity

- validation root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-r2-exact-validation-1r-gpt56sol-20260715T180743Z-claw`;
- source campaign:
  `/home/clawd/research/scion-experiments/v04-cvrp-direct-causal-feedback-r6-2r-gpt56sol-20260715T153632Z-claw/campaign`;
- runtime commit: `5a441e4488cc2d6d19ae7c92878ffb3864976e53`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- branch: `ccc5d6df-642e-4f78-adc3-46d15b1b99ac`;
- hypothesis: `2a988064-bcbc-4598-97ef-bd65078c7f48`;
- exact candidate code hash:
  `0d9c2ce5cd62dd88c4666fcfed7a6ef14001a07caf171a6af346c74c4706535a`;
- patch digest:
  `bead4c89b07d75b2512b94bb7173db929b01d3a794ad2ac79fcc0e1c25ca7b88`;
- data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`.

The copied workspace matched the source candidate before launch and remained
unchanged after the run. Wrapper/campaign/postrun exits were `0`; the one
requested validation round completed and was valid. SQLite integrity was
`ok`. Postrun readiness contained 28 `ok`, three optional `skipped`, zero
required/optional failures, and zero recorded run failures.

No provider work occurred in this invocation. The copied database and four
LLM trace files still expose the cumulative R6 totals (`2H/2C`, four provider
calls), but their counts, timestamps, file hashes, and contents did not change.
Current-invocation deltas are therefore `H=0`, `C=0`, provider=`0`, traces=`0`.

## Formal result

- split: eight validation cases not used by R6 screening;
- seeds: `[47,53,71,83]`;
- pairs: `32/32` attempted and valid, no candidate/champion failure;
- fleet violation: exact tie at zero on all candidate and champion results;
- case W/L/T: `6/1/1`, win rate `0.75`;
- pair W/L/T: `25/5/2`;
- total-distance median delta: `+7.75`;
- bootstrap CI: `[0,77]`;
- statistical status: `uncertain`;
- Decision: `expand_validation`;
- terminal branch state: `validating_expand`; champion v1 unchanged.

| Case | Seed deltas | W/L/T | Case median |
|---|---:|---:|---:|
| A-n60-k9 | `13, 28, -1, 24` | `3/1/0` | `+18.5` |
| P-n70-k10 | `24, 6, 5, 9` | `4/0/0` | `+7.5` |
| tai75c | `0, 0, 7, -25` | `1/1/2` | `0` |
| tai150a | `66, -248, -110, -59` | `1/3/0` | `-84.5` |
| tai150b | `6, 6, 6, 6` | `4/0/0` | `+6` |
| X-n120-k6 | `525, 10, 240, 301` | `4/0/0` | `+270.5` |
| X-n129-k18 | `8, 8, 8, 8` | `4/0/0` | `+8` |
| X-n190-k8 | `77, 77, 77, 77` | `4/0/0` | `+77` |

The result is stronger than R6 screening round 2 (`5/1/2`, pair `20/11/1`,
median `+3.5`, CI `[-11,12]`) on a disjoint split. It is still heterogeneous:
the single large-instance loss on `tai150a` is material, and a CI lower bound
equal to zero is uncertain rather than positive. The configured validation
rule therefore expands from eight to twelve cases; it does not promote.

## Runtime and mechanism observations

Champion runtime is fully fresh: cache hits=`0`, misses/writes=`32`, cached
runtime pairs=`0`. The candidate/champion runtime median ratio is `1.0111`,
median delta `+287.5 ms`, with 22/32 slower pairs. This approximately 1.1%
regression is supporting evidence only and did not drive the gate.

| Aggregate | Candidate | Champion | Change |
|---|---:|---:|---:|
| ALNS iterations | 604 | 1202 | `-49.8%` |
| ALNS core runtime | 47,526 ms | 95,192 ms | `-50.1%` |
| initial VNS runtime | 299,320 ms | 138,836 ms | `+115.6%` |
| embedded VNS runtime | 951,869 ms | 1,028,266 ms | `-7.4%` |
| total VNS runtime | 1,251,189 ms | 1,167,102 ms | `+7.2%` |
| VNS attempts | 19,290 | 28,564 | `-32.5%` |
| VNS accepted moves | 4,078 | 6,485 | `-37.1%` |

The candidate shifts work from ALNS into initial VNS, especially on
`tai150a`. This is a causal lead, not proof that swap-star caused either gains
or losses. The formal validation `mechanism_evidence` is empty and VNS
telemetry is still aggregate-only; it does not expose swap-star attempts,
accepts, strict improvements, best updates, or time separately.

A read-only recomputation from ALNS iteration traces found candidate/champion
`route_limit=20/112` and `repair_error=2/0`. The R1 route-cap mechanism still
reduces route-limit rejection, but adds two regret2 repair errors. These values
were not consumed by the validation gate.

## Evidence read-model defect found by audit

The validation metric, DecisionFeatures, decision event, and scheduler state
are internally consistent and authoritative. A separate branch-card defect did
not alter those results: `branch_evidence_summary` retained screening stage,
statistics, runtime, and metric ref while replacing its reason codes with the
validation reason. The mixed object could mislead resume/status consumers.

The framework repair makes current protocol evidence an atomic projection:

- top-level fields and `latest_protocol_evidence` represent the latest stage;
- `protocol_evidence_by_stage` retains only the latest compact record per
  stage, while append-only events/raw metrics remain the full history;
- screening canonical history and formal candidate/replay identity remain in
  their own durable namespaces;
- validation/frozen continue, abandon, and frozen promotion paths all update
  the projection before lifecycle side effects.

The completed validation root remains immutable and still contains the old
mixed read model. Its scientific result is valid. The repaired runtime will
atomically replace it when the expanded validation finalizes.

## Historical candidate-artifact caveat

The inherited R6 v2 R2 artifact is not independently portable from champion
v1: only cumulative R1 then R2 materialization yields the declared candidate
hash. This validation evaluated the exact copied live workspace, not an R2-only
reconstruction. The current v3 recorder/replay repair closes this defect for
new artifacts; the two inherited v2 artifacts remain historical evidence.

## Next action

After the evidence-projection repair is committed and pushed, prepare a clean
one-round resume from this validation campaign. It must enter
`VALIDATING_EXPAND`, select all 12 validation cases with the same four seeds
(`48` pairs), increment `validation_expand_count` to one, and make no provider
call. Start a separate four-round generative experiment only after that same
candidate reaches a terminal validation/frozen decision; expand to eight
rounds only if longitudinal evidence use remains unresolved.

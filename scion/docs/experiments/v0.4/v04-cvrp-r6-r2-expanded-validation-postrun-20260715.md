# CVRP R6-R2 Expanded Validation Postrun — 2026-07-15

## Verdict

The exact cumulative R6 round-2 candidate completed the preregistered
12-case expanded validation. Protocol returned
`queue_frozen / VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS`: the candidate is
eligible for an independent frozen holdout, but it is not statistically
certain, promoted, or attributable to swap-star.

The next scientific action is one eval-only frozen continuation of this exact
candidate. A new generative four-round run must wait until the same-candidate
path reaches a terminal frozen decision.

## Identity and execution integrity

- run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-r2-expanded-validation-1r-gpt56sol-20260715T201008Z-claw`;
- source campaign:
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-r2-exact-validation-1r-gpt56sol-20260715T180743Z-claw/campaign`;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-b6c214a`;
- runtime commit: `b6c214a1046ea9a4ae14fccbfea8d65d5ee6e208`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- branch: `ccc5d6df-642e-4f78-adc3-46d15b1b99ac`;
- hypothesis: `2a988064-bcbc-4598-97ef-bd65078c7f48`;
- candidate code hash:
  `0d9c2ce5cd62dd88c4666fcfed7a6ef14001a07caf171a6af346c74c4706535a`;
- data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`.

The wrapper, campaign, postrun reports, and postrun readiness all exited zero.
The requested round completed, run completeness is `complete`, run validity is
`valid`, SQLite integrity is `ok`, and the single execution outcome is
`evaluated`. Algorithm-level conclusions are allowed for this candidate
comparison.

The terminal branch is `ready_frozen / clean`,
`validation_expand_count=1`, and both current and last-clean hashes match the
candidate above. A read-only recomputation over the 11 editable files produced
the same hash. Champion v1 and its hash are unchanged; there is no promotion
dossier or promotion event.

No provider work occurred in this invocation. The source and current campaign
have the same two H and two C attempts, the same eight proposal-transition
rows and timestamps, and the same four trace filenames and hashes. The four
new rows are only the validation outcome, experiment, Decision, and scheduler
result. Current-invocation deltas are therefore `H=0`, `C=0`, provider=`0`,
trace=`0`, and formal candidate=`0`.

The repaired multi-hop ownership boundary also held: the immutable resume
index has two inherited v2 rows, exact metadata coverage, size `2092`, and SHA
`430b454a38af389e04446511e1c0e39b58d7118d40ff237fdef15a80497ab609`.
The current campaign has no live formal-candidate index. Postrun integrity is
`ok` with current=`0`, inherited=`2`, no conflict, and no orphan artifact.

## Formal result

- stage: expanded validation;
- cases/seeds: 12 cases with `[47,53,71,83]`;
- attempted/valid pairs: `48/48`;
- candidate/champion/total failures: `0/0/0`;
- fleet violation: zero for both sides on all pairs;
- case W/L/T: `8/2/2`, win rate `0.6667`;
- pair W/L/T: `33/13/2`;
- case-level total-distance median delta: `+6.5`;
- hierarchical/bootstrap CI: `[-7.25,47.75]`;
- statistical status: `uncertain`;
- raw metrics:
  `metrics:11ec5573-6fc7-473a-b3b8-daca0bace035.json#71b20e6dfeff`;
- Decision: `queue_frozen`;
- reason: `VALIDATION_EXPAND_EXHAUSTED_MARGINAL_PASS`.

Positive delta means the candidate distance is lower. The gate outcome is a
marginal pass because expanded validation is exhausted and the median remains
nonnegative; the CI still crosses zero. It queues the independent frozen
holdout and must not be reported as promotion or general statistical proof.

| Case | Seed deltas | Pair W/L/T | Case result | Median |
|---|---:|---:|---:|---:|
| A-n60-k9 | `13, 28, -1, 24` | `3/1/0` | win | `+18.5` |
| B-n66-k9 | `4, 3, 16, -2` | `3/1/0` | win | `+3.5` |
| P-n70-k10 | `24, -3, 5, 9` | `3/1/0` | win | `+7` |
| tai75c | `0, 0, 7, -25` | `1/1/2` | tie | `0` |
| tai75d | `21, 2, -38, -44` | `2/2/0` | tie | `-18` |
| tai150a | `89, -248, -110, -59` | `1/3/0` | loss | `-84.5` |
| tai150b | `6, 6, 6, 6` | `4/0/0` | win | `+6` |
| F-n72-k4 | `-5, -2, -32, -24` | `0/4/0` | loss | `-14.5` |
| X-n120-k6 | `525, 10, 240, 301` | `4/0/0` | win | `+270.5` |
| X-n129-k18 | `8, 8, 8, 8` | `4/0/0` | win | `+8` |
| X-n157-k13 | `253, 415, 415, 58` | `4/0/0` | win | `+334` |
| X-n190-k8 | `77, 77, 77, 77` | `4/0/0` | win | `+77` |

The aggregate is strongly heterogeneous. Large gains on X-n120, X-n157, and
X-n190 dominate, while F-n72 is consistently worse, tai150a is materially
worse, and tai75d changes sign across seeds. A positive overall median does
not demonstrate stable improvement across instance families.

## Runtime and mechanism observations

Champion runtime was fully fresh: cache hits=`0`, misses/writes=`48`, and
cached-runtime pairs=`0`. The candidate/champion runtime ratio median is
`1.011813`, the median delta is `+367.5 ms`, and the candidate is slower on
`35/48` pairs. Aggregate wall time is `1,840,648 ms` for the candidate versus
`1,785,848 ms` for the champion. Runtime remains supporting evidence, not an
independent optimization objective or the reason for the gate decision.

| Phase aggregate | Candidate | Champion | Change |
|---|---:|---:|---:|
| construction | 2,966 ms | 2,959 ms | `+0.2%` |
| initial VNS | 499,896 ms | 188,812 ms | `+164.8%` |
| ALNS core | 70,372 ms | 128,552 ms | `-45.3%` |
| embedded VNS | 1,250,838 ms | 1,447,376 ms | `-13.6%` |
| search iterations | 1,021 | 1,853 | `-44.9%` |

The candidate moves substantial time into initial VNS and performs less ALNS
exploration. Its solver path is loaded and active on all 48 pairs, all outputs
are valid, and solver errors are zero. This supports a real search-allocation
change, but not a swap-star-specific causal claim.

Formal validation has `mechanism_evidence={}` and
`opportunity_status=unknown`. VNS telemetry is phase-aggregate only and does
not expose swap-star attempts, accepts, strict improvements, best updates, or
net contribution. The candidate is cumulative across `destroy_repair.py`,
`scheduler.py`, and `local_search.py`; frozen results therefore cannot be
uniquely attributed to the latest local-search edit without new problem-owned
telemetry in a later generative candidate.

## Prepared-readiness reporting mismatch

The generic prepared-handoff checker reported `launch_ready=false` because it
classifies any resume source as `formal_launch_contains_resume` and also
requires completion preflight. This root was intentionally an eval-only
diagnostic continuation: resume was required, completion preflight was
disabled because it is incompatible with resume, and `run.sh` does not consume
the generic report as a launch gate.

The successful wrapper/campaign/postrun lifecycle proves this was a reporting
classification mismatch, not an infrastructure or scientific failure. It is
follow-up operational debt: prepared readiness should distinguish clean fresh
formal roots from explicitly copied eval-only continuations. It is not a
reason to add a gate, retry, provider call, or delay the frozen holdout.

## Next action

Prepare one distinct copied-state continuation from this terminal campaign.
It must reuse the exact `ready_frozen` branch and candidate, run the first
eight frozen cases with seeds `[61,67,89]` (`24` pairs) plus the declared
canary, make no H/C/provider call, and terminate in one frozen Decision. Only
after that terminal result should Scion start a clean four-round generative
run; expand to eight rounds only if adaptation or reproducibility remains
unresolved.

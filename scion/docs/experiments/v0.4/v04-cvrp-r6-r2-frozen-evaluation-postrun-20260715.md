# CVRP R6-R2 Frozen Evaluation Postrun — 2026-07-15

## Verdict

The exact cumulative R6 round-2 candidate reached the independent frozen
holdout, but the frozen comparison is incomplete. Protocol correctly failed
closed with `INCOMPLETE_EVIDENCE / CHAMPION_RUNTIME_FAILURE`, and Decision
recorded `abandon / INCOMPLETE_RUNTIME_EVIDENCE`. There is no promotion.

The 22 valid pairs are descriptively positive, but two comparisons lack valid
champion evidence. They cannot be promoted to a complete frozen result, and
the terminal root must not be retried, extended, or reinterpreted by changing
seeds, cases, time limits, or gates.

The failure exposed a common CVRP baseline time-control defect rather than a
heavy-gate problem: the baseline declares an 80% internal search window, but
initial VNS used the full subprocess clock and several expensive neighborhood
scans did not poll the deadline inside their nested loops. Large cases could
therefore run through the scientific limit and consume the runner's separate
15-second output/termination grace.

## Identity and execution integrity

- run root:
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-r2-frozen-evaluation-1r-gpt56sol-20260715T213106Z-claw`;
- source campaign:
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-r2-expanded-validation-1r-gpt56sol-20260715T201008Z-claw/campaign`;
- runtime checkout:
  `/home/clawd/research/or-autoresearch-agent-v04-direct-runtime-a369112d`;
- runtime commit: `a369112d41a4da952f3751a53dedee7821125b48`;
- model/runtime: `gpt-5.6-sol / direct_v3`;
- branch: `ccc5d6df-642e-4f78-adc3-46d15b1b99ac`;
- hypothesis: `2a988064-bcbc-4598-97ef-bd65078c7f48`;
- candidate code hash:
  `0d9c2ce5cd62dd88c4666fcfed7a6ef14001a07caf171a6af346c74c4706535a`;
- data identity: 81 files, digest
  `ca7e470ec8d1f3569a690d10df5a170c4994108c71fecf5aa1a7a76b42630743`.

Preparation copied the complete terminal expanded-validation campaign. Before
launch, the only branch was `ready_frozen / clean`, its workspace recomputed to
the exact candidate hash, champion v1 was unchanged, the immutable inherited
formal-candidate index contained two rows with size `2092` and SHA
`430b454a38af389e04446511e1c0e39b58d7118d40ff237fdef15a80497ab609`,
and the current live index was absent. The wrapper was launched exactly once.

Wrapper, campaign, postrun reports, and postrun readiness exited zero. The one
requested typed round completed; run completeness is `complete`, run validity
is `valid`, SQLite integrity is `ok`, and the canary passed on the declared
synthetic case with seed `101`. These facts establish orchestration integrity;
they do not repair the missing frozen comparisons.

No provider work occurred in this invocation. Source and current H/C
transitions, provider accounting, and four trace files are unchanged, and no
new formal candidate was recorded. The candidate workspace remains archived
under the same 11-file hash. Champion v1 remains unchanged and no promotion
dossier exists.

## Frozen selection and result

The formal manifest contains 12 preregistered frozen X cases. The configured
eight-case evaluation selected deterministic evenly spaced entries, not the
first eight manifest rows:

| Case | Scientific limit | Seed deltas | Valid pairs | Case result | Median |
|---|---:|---:|---:|---:|---:|
| X-n139-k10 | 60s | `396, -98, 487` | 3/3 | win | `+396` |
| X-n204-k19 | 60s | `269, 254, 472` | 3/3 | win | `+269` |
| X-n251-k28 | 90s | `337, 337, 337` | 3/3 | win | `+337` |
| X-n327-k20 | 90s | `89, 98, 98` | 3/3 | win | `+98` |
| X-n401-k29 | 90s | `invalid, 65, 65` | 2/3 | win | `+65` |
| X-n573-k30 | 120s | `0, 0, 0` | 3/3 | tie | `0` |
| X-n641-k35 | 120s | `0, 0, 0` | 3/3 | tie | `0` |
| X-n1001-k43 | 120s | `invalid, 0, 0` | 2/3 | tie | `0` |

Seeds are `[61,67,89]`. Positive delta means the candidate has lower total
distance.

- attempted/valid/failed pairs: `24/22/2`;
- recorded candidate/champion failures: `0/2`;
- case W/L/T: `5/0/3`;
- valid-pair W/L/T: `13/1/8`;
- case-level median/CI: `+81.5 / [0,337]`;
- statistical status: `uncertain`;
- fresh runtime ratio/delta: `1.00818 / +847 ms`;
- candidate slower pairs: `14/24` elapsed-time observations;
- raw metrics:
  `campaign/metrics/18c88452-0bf8-4d93-a2ae-780b07d79f96.json`;
- raw file SHA-256:
  `21c8b35ab78815ceb3d695e3f9c9d6032bc8b9f5a94c8cf9bcb11695f5b23ef3`;
- Protocol: `fail / INCOMPLETE_EVIDENCE + CHAMPION_RUNTIME_FAILURE`;
- Decision: `abandon / INCOMPLETE_RUNTIME_EVIDENCE`.

The candidate has a strong descriptive signal on X-n139 through X-n401 and no
gain on X-n573, X-n641, or X-n1001. That is useful partial scientific evidence,
but it is not a frozen pass. The candidate remains best described as
`promising but frozen-incomplete / not promoted`; the historical terminal
branch state remains read-only.

## Runtime failures and root cause

The two invalid pairs both used seed `61`:

1. X-n401 champion exceeded the 90-second scientific limit and the 15-second
   runner grace. It ended after `105.288s` with exit `-9`. The candidate
   returned a valid incumbent after `89.296s`.
2. X-n1001 produced no valid result on either side. Champion ended after
   `135.407s` with exit `-9`. Candidate crossed the same 120+15 deadline and
   was classified `timeout`, although it exited `0` during the termination
   race at `135.243s`. This is still a missed deadline, not a valid result.

The successful large-case executions confirm this is systematic rather than a
single noisy kill. All 18 side runs at the 120-second tier exceeded the nominal
scientific limit; 16 happened to serialize output within the grace period.
Successful X-n1001 runs spent roughly `20–22s` in construction and
`110–112s` in initial VNS, reaching `131–133s` total.

`BASELINE_TIME_FRACTION=0.80` should constrain a 90/120-second subprocess to a
72/96-second internal search window. Instead, scheduler outer-loop checks used
that local duration while initial VNS and its operators compared
`context.remaining_time()` against the full 90/120-second clock. The
`two_opt_intra`, `relocate`, `swap`, `or_opt`, and `two_opt_star` neighborhoods
then entered O(n^2)-to-O(n^3) nested scans with polling only at coarse outer
boundaries. The runner's `time_limit + 15s` watchdog behaved as designed and
made the algorithm defect visible; increasing that grace or relaxing the gate
would hide the defect.

There are also two framework-accounting debts revealed by the terminal root:

- two independent sequential timeouts are labeled
  `shared_process_failure`, which is too broad even though the raw side
  categories remain visible;
- later-stage champion/shared evidence-acquisition failure is flattened into
  `evaluated -> abandoned`, while V3 distinguishes an infrastructure/runtime
  incident from a scientific frozen failure. The gate must still fail closed,
  but a future branch should enter `BLOCKED_INFRA`, require an explicit operator
  resume, and never schedule an automatic retry.

These debts do not retroactively change this root or make it promotable.

## Repair and next experiment

Before a new generative campaign, apply two narrow repairs:

1. Bind the existing 80% CVRP search window to one absolute deadline visible
   through the problem-owned solver context, and cooperatively poll it inside
   every expensive local-search scan so the current valid incumbent is returned
   before the scientific subprocess boundary.
2. Route later-stage champion/shared evidence-acquisition failure to
   `BLOCKED_INFRA` before Decision, preserve the partial raw metrics reference,
   persist the pre-block branch state, and require the existing explicit
   operator-resume event. Candidate-only runtime failure remains a hard
   scientific abandon.

Neither repair adds a proposal budget, content cap, semantic stop counter,
truncation rule, gate, automatic retry, or post-hoc time-limit change.

After focused and full verification, commit and push the common repair, create
a new clean exact runtime checkout, and launch a distinct four-round CVRP
generative experiment. Four rounds are an observation count, not a retry
budget. Expand to eight only if the four-round terminal evidence still leaves
adaptation or reproducibility unresolved. Do not rerun this frozen root or use
the common repair to claim an exact replay of the historical R6 candidate.

## Repair verification

The implemented repair passes the focused deadline/lifecycle/protocol set
(`81` tests), the complete unit set (`724`), and the standard Scion suite
(`1962 passed, 1 skipped`). Compileall, Black check, and `git diff --check`
pass.

A direct compliance probe used X-n1001-k43 seed61 with a 30-second scientific
limit. It returned exit `0` after `23.78s` with a feasible 43-route incumbent,
zero fleet violation, and `stop_reason=time_limit`. Construction used
`20.745s`; initial VNS saw the remaining local deadline and exited after
`2.522s`. This validates the observed failure path without modifying or
replaying the historical frozen root.

Two nonblocking P2 follow-ups remain explicit. Construction and ALNS
destroy/repair receive the bounded context but do not yet poll it inside every
internal loop; the real maximum-scale probe shows construction finishes within
the current window, while the proven overrun was initial VNS. Also,
`_DeadlineContext` deliberately proxies the currently used telemetry API
explicitly, so a future baseline module that consumes a new context method must
extend that adapter and its contract test.

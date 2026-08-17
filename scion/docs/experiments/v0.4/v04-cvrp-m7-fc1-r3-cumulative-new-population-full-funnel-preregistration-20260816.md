# CVRP M7-FC1 cumulative R3 new-population full-funnel preregistration

*Date: 2026-08-16*

*Label: `v04-cvrp-m7-fc1-r3-cumulative-new-population-full-funnel-20260816`*

*State: `PREPARED_NOT_STARTED / AWAITING_EXPLICIT_EXECUTION_AUTHORIZATION`*

## Question

Does the exact, outcome-known cumulative R3 candidate-06 retain a
Protocol-admissible `total_distance` improvement over exact R3 B0 on a new,
outcome-blind-to-this-exact-comparison 48-case population, when evaluated by
the subtraction-complete direct V3 carrier?

This is a new M7 fixed-candidate rung. It is not a repair, retry, resume,
replacement or renaming of R67. R67 stopped in preflight before scientific
delegation and contributes no observation to this run.

## Ordinary frozen scientific inputs

The machine-readable input is
[`population.json`](v04-cvrp-m7-fc1-r3-cumulative-new-population-full-funnel-20260816/population.json).
It is the single ordinary value for the cases, seeds, order, budgets and claim
boundary described below. It is not an authorization manifest and is never
rewritten or read back as runtime authority.

### Arms

| arm | source | files | bytes | descriptive content digest |
| --- | --- | ---: | ---: | --- |
| A | exact R3 B0 | 104 | 686,519 | `f2436c23b6c169f0cb9a167b4fd0bab45b87ec761aa9c5e5e401b9abae22ebf5` |
| B | complete cumulative candidate-06 | 104 | 693,394 | `cf223be81b45d04164f0b7dd88c9d78a49b4419d115b1413405d9dcf2832cf53` |

The digest is a compact source-equality check, not an identity or authority.
It preserves the historical framing exactly: for each regular file in
sorted relative-path order, hash `relative_path`, the two literal bytes
backslash-zero, `file_sha256`, literal backslash-zero, `decimal_size`, then the
two literal bytes backslash-n. The driver checks it once before execution. It
does not rehash a subject in the solver hot path.

The two arms differ only in the cumulative contents of:

- `policies/baseline_modules/acceptance.py`;
- `policies/baseline_modules/destroy_repair.py`;
- `policies/baseline_modules/scheduler.py`.

The new ordinary input root is
`campaign_out/v04-cvrp-m7-fc1-r3-cumulative-new-population-full-funnel-20260816-input`.
It contains copied B0 and candidate source trees plus
read-only copies of exactly the 48 selected `.vrp` files and their 48 companion
`.sol` files. Solvers read this private data copy, not the mutable repository
dataset. The driver must not import or execute the R67 launcher, manifest,
frozen-input checker, executor, supervisor, embedded runtime, control root,
ledger or authorization state.

The execution-carrier commit will be recorded after the driver and its
provider-/solver-free tests are committed. No framework source may change
between that carrier commit and the one authorized run.

### Population and exposure

The 48 cases are four mutually disjoint 12-case strata: screening,
validation, frozen and retained B0. They were selected deterministically with
salt
`v04-cvrp-m7-fc1-r3-cumulative-new-population-full-funnel-20260816|population-v1`
from regular, non-symlink CVRPLIB `A/B/CMT/E/F/M/P/X/tai` cases of dimension at
most 1,001 that the current adapter can parse. Cases from the historical R3
48-case population and the unexecuted R67 48-case plan were excluded before
selection.

All 48 selected cases have a readable `.vrp` file and a matching solution
file. The selected case set has zero overlap with both excluded 48-case sets.
The selected seeds do not occur in an existing seed ledger. No outcome from
candidate-06 on any of these 48 exact comparisons was used for selection:

- `population_selection_outcome_blind_relative_to_exact_estimand=true`;
- `exact_candidate06_outcome_overlap_count=0`;
- `globally_case_unseen=false`.

The complete ordered case lists, per-subject limits, seeds, and byte counts and
SHA-256 values for every `.vrp` and companion `.sol` input are in
`population.json`; they may not be shortened, expanded, substituted, changed
or reordered after launch. These hashes are one-time input equality checks,
not runtime authority or a repeatable receipt lifecycle.

### Stage order

1. Strict comparator-first canary on B0 then candidate.
2. Initial screening: first 8 screening cases × first 4 screening seeds.
3. If and only if Protocol returns `expand` and Decision returns
   `EXPAND_SCREENING`, run another strict comparator-first canary.
4. Expanded screening: all 12 screening cases × all 8 screening seeds, run
   fresh rather than merging the initial pairs.
5. If and only if Protocol returns `pass` and Decision returns
   `QUEUE_VALIDATE`, run a strict comparator-first canary and then validation
   on 12 × 8.
6. If and only if Decision returns `QUEUE_FROZEN`, run a strict
   comparator-first canary and then frozen holdout on 12 × 8.
7. If and only if Decision returns `PROMOTE`, make one output-local,
   byte-equal candidate snapshot and compare it with original B0 on the
   retained 12 × 8 population.

The retained comparison is a fifth Protocol call using the frozen gate. It
does not make a fifth Decision and it does not mutate a production champion.

For formal pairs, A is B0 and B is candidate-06. Pair execution is AB when
`(block_ordinal0 + case_ordinal0 + seed_ordinal0) % 2 == 0`, otherwise BA.
Block ordinals are 0 initial, 1 expanded, 2 validation, 3 frozen and 4
retained. Execution is serial and cache-disabled.

The canary case and its ordinary byte count/SHA-256 value are likewise frozen:
`controlled/data/synthetic_controlled_canary_5.vrp`, seed `2267`, at 10 seconds
per subject. Comparator failure, missing output, runtime-audit failure or
infeasibility is execution-invalid and supplies no candidate-quality claim.
Only a valid comparator permits candidate execution. Any candidate canary
failure or infeasibility is an immediate candidate veto.

## V3 path and Protocol

There are no provider, Hypothesis, Code or patch-generation calls in this
fixed-candidate estimand. Exact full-source equality allows the historical
Contract and Verification pass for the same source to enter as ordinary safe
facts. The driver passes `contract=True` and `verification=True` to the current
`SafeFeatureExtractor`; it does not read an old database or projection and
does not issue a new receipt. Current Contract, Verification, V3 and V4 calls
are all zero. Any source-digest mismatch invalidates this reuse and stops
before a solver call.

The live path is therefore:

```text
exact full-source equality + prior safe facts
  -> strict current canary
  -> current ExperimentProtocol
  -> current SafeFeatureExtractor
  -> current deterministic DecisionEngine
```

The Protocol configuration is the exact R3 formal configuration copied with
B0, with the preregistered split, seed ledger and explicit per-case time limits
supplied by `population.json`. The driver also binds
`screening.priority_case_ids` to the first eight screening entries so the
initial stage is exactly the declared prefix rather than the generic selector's
evenly spaced subset. Its scientific rules remain:

- paired case effect is `B0 total_distance - candidate total_distance`;
- case aggregation is paired-effect median with equivalence band 0;
- `fleet_violation` is protected and any regression blocks;
- initial screening cannot pass directly. Its preregistered quality-expansion
  predicate is net case score `>= 0.125`, loss rate `<= 0.25`, no candidate
  failure, and CI high `>= 2`; the current sparse-no-loss branch additionally
  requires at least one win, zero losses, median `>= 2` and CI high `>= 2`.
  The current case-level-uncertain expansion branch remains frozen as
  implemented. Any initial outcome other than `expand` is terminal;
- expanded screening requires `(wins - losses) / 12 >= 0.25`, loss rate
  `<= 0.20`, median delta `>= 2`, and bootstrap CI low `>= 0`;
- validation, frozen and retained require the same net-score, loss-rate and CI
  conditions with median delta `>= 1`;
- bootstrap uses 1,000 resamples, alpha 0.05 and seed 42;
- any candidate failure, incomplete pair set or protected-objective regression
  stops the run.

The four expected Decisions are exactly:

```text
EXPAND_SCREENING -> QUEUE_VALIDATE -> QUEUE_FROZEN -> PROMOTE
```

Any other typed result is terminal and starts no later stage.

## Resource envelope

| item | fixed maximum |
| --- | ---: |
| formal pairs | 416 |
| formal solver subprocesses | 832 |
| canary pairs / subprocesses | 4 / 8 |
| all solver subprocesses | 840 |
| Protocol / SafeFeature / Decision calls | 5 / 4 / 4 |
| output-local snapshots | 1, only after `PROMOTE` |
| planned nominal subject-seconds | 45,200 |
| fail-closed nominal ceiling | 50,000 |
| positive-path `declared + 15s` timeout sum | 57,800 seconds |
| outer hardwall | 64,800 seconds |
| concurrency | 1 |

The initial 8 × 4 block contributes 2,880 subject-seconds. Each complete 12 ×
8 block contributes 10,560; four such blocks contribute 42,240. Four canary
pairs contribute 80, totaling 45,200.

The driver uses a fresh temporary copy for each subject, a clean subprocess
environment, the existing local resource limits and one active solver at a
time. Subject templates are read-only scientific inputs. It exposes no retry,
resume, repair, replacement or substitution option and never reads an existing
output as runtime input. The output directory must not exist at launch.

## Terminal and claim rules

Any failed prerequisite, comparator failure, candidate veto, Protocol terminal,
unexpected Decision, budget breach, signal, exception or hardwall immediately
stops the only run. Provider retry, solver retry, repair, resume, replacement,
substitution, population or seed addition, alternate candidate, automated next
rung and R67 recovery are all zero.

A positive terminal supports at most:

> The outcome-known cumulative R3 candidate-06 retained a
> Protocol-qualified total-distance improvement over exact R3 B0 on the
> complete preregistered M7-FC1 population under the frozen V3 carrier.

It must also report:

```text
candidate_selection_outcome_known=true
candidate_discovery_independent=false
incremental_effect_isolated=false
population_selection_outcome_blind_relative_to_exact_estimand=true
exact_candidate06_outcome_overlap_count=0
globally_case_unseen=false
MDE@80%=null
```

`execution_replication_independent` remains null. A fresh output, serial
execution and a complete run establish a clean execution of this comparison;
they do not by themselves establish independent replication.
No outcome may be described as independent discovery, an isolated effect of
the last route-removal edit, an isolated component effect, global CVRP
generalization, provider improvement, production readiness or a new mechanism.

A valid negative terminal is evidence only against this exact cumulative
source on the population reached before the stop. An infrastructure or
comparator-invalid terminal makes no candidate-quality claim.

## Authorization boundary

Preparing this record, the driver and provider-/solver-free tests is authorized
work under TASK M7. Formal execution is not yet authorized: the new label,
population and 45,200-second envelope did not exist when the preceding broad
instruction to continue TASK was given.

After the carrier is committed and the read-only preflight passes, one explicit
authorization naming this label and confirming the frozen scientific envelope
is sufficient for one launch. No hash-signing, authorization manifest,
refreeze, sentinel or second confirmation is required. A failed launch consumes
that one attempt and cannot be repaired or repeated without a new scientific
record and new authorization.

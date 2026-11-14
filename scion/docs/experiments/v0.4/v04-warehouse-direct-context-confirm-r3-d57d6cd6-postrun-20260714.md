# v0.4 Warehouse Direct Context Confirmation R3 at `d57d6cd6`

- Date: 2026-07-14
- Model: `gpt-5.6-sol`
- Runtime mode: `direct_v3`
- Formal fresh root:
  `/home/clawd/research/scion-experiments/v04-warehouse-direct-repaired-context-confirm-r3-2r-gpt56sol-20260714T135820Z-claw`
- Same-candidate expanded-screening continuation:
  `/home/clawd/research/scion-experiments/v04-warehouse-r3-same-candidate-expand-1r-gpt56sol-20260714T142050Z-claw`

## Verdict

R3 confirms that the repaired warehouse context reached the real formal
launcher and that the small direct runtime can perform iterative algorithm
research without the previous governance noise. The fresh two-round root is
fully green: both rounds were evaluated on one branch, exactly two H and two C
calls completed without retry, both candidates passed Contract, Verification,
and Canary, and postrun readiness passed.

The second round produced the first genuinely promising warehouse signal in
this series: a directed vehicle-merge operator improved total cost across a
broad initial screen. Scion correctly chose `expand_screening`. An eval-only
continuation then reused the exact same candidate without another provider
call and strengthened the result to 14 cases / 28 seed pairs, after which the
deterministic decision became `queue_validate`.

The subsequent eval-only validation rejected the cumulative branch. On five
larger, lock-heavy cases it achieved case W/L/T `2/3/0`, primary
`subcategory_splits` median `0` with CI `[0,1]`, and runtime ratio `1.578`.
Decision was `abandon / VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`; no frozen run or
promotion followed. The positive screening signal was real on its declared
screen, but it did not generalize sufficiently.

## Formal Execution Evidence

- prepared/runtime commit: `d57d6cd6`;
- guarded readiness: passed with no blocker and no separate live probe;
- completion preflight: authenticated HTTP 200 with non-empty response;
- requested/evaluated rounds: `2/2`;
- provider calls: H=`2`, C=`2`, total=`4`;
- automatic retries or replacement attempts: `0`;
- branch:
  `52b0b193-7bc3-469c-97a2-216b494b4e4a` for both rounds;
- both rounds: Contract pass, Verification pass, Canary pass;
- campaign wrapper / outer wrapper / postrun: all green;
- execution-outcome and decision identities: complete and consistent;
- champion remained version 1.

Actual provider-visible H/C contexts contained none of the removed telemetry
guard, activation/effect-counter, validation-transfer, top-k,
`max_candidates`, candidate-cap, runtime-budget-strategy, retry, or truncation
instructions. H2 consumed round 1's canonical result, and C2 carried the round
1 source as verified `branch_history_current/full_current` content.

No Scion prompt/session/tool/file/item/token budget, semantic termination
budget, content truncation, or automatic retry was active. The protocol's
30-second per-solver-run time limit is a scientific subprocess fact.

## Round 1: Subcategory-Focused Destroy/Rebuild

The agent replaced `operators/destroy_rebuild.py` with a 386-line
subcategory-focused beam destroy/rebuild search.

- case W/L/T: `2/2/2`;
- pair W/L/T: `5/5/2`;
- `subcategory_splits` delta: `0` on every pair;
- total-cost median delta: `-1150`, CI `[-10175, 550]`;
- runtime median ratio: `3.2567`;
- runtime median delta: `+20304.5 ms`;
- runtime regression rate: `0.75`;
- Decision: `continue_explore / RUNTIME_REGRESSION`.

The mechanism was substantive but not a positive full-solver result. It also
remained in the cumulative branch at weight `0.15`, which matters when
interpreting round 2.

## Round 2: Directed Best-of-k Vehicle Merge

The second H/C iteration modified `operators/merge_vehicles.py` with a
221-line directed merge search. Its H6 lookup uses the exact oracle key:

```python
f"{destination_country},{ship_method}"
```

Initial screening result:

- case W/L/T: `3/0/3`;
- pair W/L/T: `8/1/3`;
- `subcategory_splits` delta: `0` on every pair;
- total-cost median delta: `+775`, CI `[150, 3000]`;
- statistical status: positive;
- Decision: `expand_screening /
  SCREENING_EXPAND_LOW_SNR_TRAJECTORY_DIVERGENT`.

The formal runtime aggregate was excluded because the champion side came from
a low-confidence cache, so no runtime conclusion should be drawn from that
aggregate. Descriptively, four larger pairs took about 30.1--30.2 seconds on
the candidate side.

## Same-Candidate Expanded Screening

The continuation copied the completed campaign state, reopened the same
branch/candidate, and ran the scheduler's eval-only `EXPLORE_EXPAND` path.
There were no new H/C calls: the durable trace count remained four.

- evaluated rounds in this invocation: `1/1`;
- cases / pairs: `14 / 28`;
- valid / failed pairs: `28 / 0`;
- case W/L/T: `7/0/7`;
- pair W/L/T: `19/2/7`;
- `subcategory_splits` median/CI: `0 / [0, 0]`;
- total-cost median delta: `+625`, CI `[300, 1600]`;
- statistical status: positive;
- fresh runtime evidence: high confidence;
- runtime median ratio: `0.7004`;
- runtime median delta: `-279 ms`;
- runtime regression rate: `0.4286`;
- Protocol gate: pass;
- Decision: `queue_validate`;
- branch state after the run: `ready_validate`;
- screening expansion count: `1`.

The consistent case wins were spread across micro, small, medium-small,
medium, and medium-large fixtures. Pair-level losses were confined to one
seed each on `m04` and `ml02`. The largest consistent gain was on `ml01`
(`+15100`, `+11800`). This is broad enough to justify validation, but all gain
is still on the secondary total-cost objective.

## Same-Candidate Validation

- Runtime commit: `9c88ef6a`;
- continuation root:
  `/home/clawd/research/scion-experiments/v04-warehouse-r3-same-candidate-validation-1r-gpt56sol-20260714T145307Z-claw`;
- campaign ID: `a24b5d73-153a-4f85-85e8-17fbb69c50e1`;
- trace count before/after: `4 / 4`;
- provider calls or retries in this invocation: `0`;
- code/branch identity: unchanged cumulative candidate;
- cases / seeds / pairs: `5 / 3 / 15`;
- valid / failed pairs: `15 / 0`;
- case W/L/T: `2/3/0`;
- pair W/L/T: `6/9/0`;
- `subcategory_splits` median: `0`, CI `[0,1]`;
- runtime median ratio: `1.578`;
- runtime median delta: `+11072 ms`;
- runtime regression rate: `13/15 = 0.8667`;
- Decision: `abandon / VALIDATION_FAIL_NO_HIERARCHICAL_GAIN`;
- final branch state: `abandoned`;
- campaign/outer wrapper: `0 / 0`;
- postrun: ready, no required or optional failure.

The copied status/summary retains cumulative H=`2`, C=`2` counters from the
source campaign. They are not current-invocation calls. The validation
campaign has zero proposal-attempt transitions, and the four trace files are
byte-identical artifacts whose mtimes predate validation launch.

Pair-level interpretation:

- `val_l01` improved `subcategory_splits` by `+1` on all three seeds, so it
  won lexicographically despite cost deltas `-11500/-10600/-8000`;
- `val_l02`, `val_l04`, and `val_lx01` tied on splits and lost cost on all
  nine pairs;
- `val_lx02` tied on splits and won cost on all three seeds by
  `+52900/+43800/+48100`.

Thus only one of five cases had a consistent primary-objective gain, one other
case had a large cost gain, and three cases consistently regressed. The
descriptive median of the five case-level cost effects is `-8300`. Twelve of
15 candidate runs were near the 30-second solver limit, while champion took
about 13.6--21.1 seconds. The validation rejection is therefore scientific,
not a framework or gate false negative.

The validation root also proves the resumed-postrun fix under real execution:
the copied database has four cumulative evaluated outcomes across three
campaign IDs, while current-invocation integrity correctly compares summary
`1` with scoped lineage `1`. Decision/outcome consistency is `consistent`, and
postrun is fully green.

## Remaining Scientific Uncertainty

1. The final branch contains both the round-1 destroy/rebuild change and the
   round-2 merge change, each at weight `0.15`; current evidence is cumulative,
   not merge-only attribution.
2. Both new operators change RNG consumption and therefore the later operator
   sequence. `opportunity_status` and `mechanism_evidence` are empty, so the
   artifacts do not prove direct calls, acceptances, or causal contribution to
   the final best solution.
3. `_PAIR_LIMIT=24` is not a true computation boundary: the implementation
   enumerates, validates, and sorts all directed `O(V^2)` pairs before slicing.
4. Runtime is strongly bimodal. Several micro/small pairs were 2.4--23 times
   slower than champion, and all six `m03`/`m04`/`ml02` pairs reached roughly
   30 seconds even though the formal paired median was faster.
5. Screening, validation, frozen, and canary fixtures all have empty
   `amount_limits`. The H6 source code is correct, but the H6 rejection path is
   not empirically exercised by the production split. Validation does contain
   many locked orders and will exercise that separate feasibility boundary.

These are reasons to preserve attribution and runtime diagnostics, not reasons
to send governance instructions back into the provider prompt or to block the
already-earned validation step.

## Resume-Postrun Scope Defect

The expanded-screening campaign itself exited `0`, is valid, and recorded one
evaluated outcome. Its original outer wrapper nevertheless exited `64` because
postrun compared the current invocation summary against cumulative rows in the
copied SQLite database:

- current campaign ID `94d52219-...`: one evaluated outcome;
- copied source campaign ID `acbb5338-...`: two evaluated outcomes;
- unscoped database total: three evaluated outcomes.

The correct integrity comparison is current summary `1` against current
campaign lineage `1`. Cumulative event statistics remain useful resume/audit
history but must not be substituted for current-invocation evidence.

The repair keeps cumulative top-level event counts, projects outcome/decision
integrity by the current summary's `campaign_id`, remains fail-closed when that
identity exists but the scoped outcome is absent, and marks legacy schemas
without usable campaign identity as incomparable rather than comparing mixed
history. The acceptance rule itself is unchanged. The completed repair passes
the full Scion suite (`1859 passed, 1 skipped` in `494.65s`), compileall,
`git diff --check`, and an independent P0/P1/P2 audit.

## Next Action

Do not retry, modify, freeze, or promote this branch. Preserve it as a useful
negative generalization result: Scion found a broad screening signal, expanded
it, escalated it to validation, and then rejected it on the preregistered
larger locked split without another model call.

The warehouse direct-runtime lifecycle is now resolved. After committing this
status update, prepare one fresh, clean, open, non-target-bound CVRP control as
the second problem-family test. Keep the same no-retry/no-truncation rules and
inspect actual provider context before launch. H6 still needs a separately
constructed non-empty `amount_limits` fixture in later constraint-coverage
work; this validation cannot be cited as H6 behavioral evidence.

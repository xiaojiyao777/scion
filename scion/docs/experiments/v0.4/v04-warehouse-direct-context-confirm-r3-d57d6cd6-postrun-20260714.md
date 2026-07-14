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

This is not yet validation or promotion evidence. The branch is cumulative,
the primary `subcategory_splits` objective never improved, and the present
artifacts do not isolate the merge operator from round 1's slower
destroy/rebuild operator or from changed seeded search trajectories.

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

After the scoped-lineage repair passes the full suite and is committed, create
a detached clean runtime at that exact commit and resume the expanded campaign
into one eval-only validation invocation. It should reuse the same candidate,
make no provider call, and evaluate only the preregistered validation split.
The manifest contains five validation cases and three validation seeds, so the
expected surface is 15 pairs even though the protocol's upper request is six
cases. Their locked-order counts are `12/49/43/15/58`. Before launch, assert
the cumulative candidate identity. The exact identities are:

- code:
  `b214e9e18fcbf86c5b58ae58aed1be0db1cfd1daf57f3e874bda6bbe8c42d069`;
- destroy/rebuild:
  `4910ad450fb8bf8a876b0d3287ce9322e5600a4a87e156e95e36b4ea1a22cc36`;
- merge:
  `6e251c9f5bba4562bc2893cc4d56e10c9e74fa9874a2afacb0fa9428f144dcd5`.
- registry:
  `4a3f8c737bb02cd3b87230ae4dad4a758287e0fef3ffb82e810a3f0592c212f1`.

Replaying only the round-2 patch would be the wrong candidate. Proceed to
frozen evaluation only if the deterministic validation decision requires it.
Do not promote or start CVRP from screening evidence alone.

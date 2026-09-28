# CVRP R15 read-only postrun: valid validation failure and remaining research gaps

Analysis date: 2026-09-28. Profile: Experiment Analysis; canonical entry pack,
operations/runbook/postrun handoff and R15 preregistration read before the
bounded raw-artifact audit. No provider, solver, tests, original SQLite access,
campaign mutation or new experiment was performed. Only analysis/handoff docs
change. Runtime/inputs were committed and pushed as `f73e89e7` after launch;
the preregistration preserves the actual dirty-at-launch source description.

## Scope and terminal result

Run: `/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927`.
Started 2026-09-27 13:54:37 UTC; final status written at
`2026-09-27T22:04:54.956555+00:00`, approximately 8 h 10 min later.
The pane is dead, without an available exit-status value. Completion is
established by [status](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/campaign_summary.json):

- `completed` / `requested_rounds_completed`, valid invocation.
- 14 scheduled steps: 12 evaluated stages and two research rejections.
- 12 H exports, 11 C exports, ten distinct candidates reaching Protocol.
- Eleven screening stages (ten initial plus one expansion), one validation;
  124 screening pairs plus 12 validation pairs, **136/136 valid**.
- Zero formal pair failures, runtime errors, invalid solutions or protected
  fleet regressions. Recomputed objective deltas, case medians and stage
  medians agree with recorded values; both arms use the declared equal limits.
- 125 successful physical provider calls, all attempt index zero: H 58,
  C turns 66, C finalization one. Of the 600-call envelope, 475 remain.
- Champion stays v1 / weight revision zero. No promotion, frozen or retained
  execution. The final initial-screen positive remains unexpanded.

The report field `formal_screened_candidates=11` counts screened stages here,
including expansion; it is not eleven distinct generated candidates. The
ordinary H/C and step records distinguish the ten unique evaluated candidates.

All effects compare against the local complete R12-A-fixed champion, not
original B0 or B0-fixed. Screening is adaptive development. Validation had
already been operator-exposed in R10/R12; it is not independent confirmation.
The formerly incomplete validation matrix is complete in R15: the shared
constructor failure did not recur on these cases/seeds. This is evidence of
repaired execution on this matrix, not a universal correctness claim.

## Stage trajectory

Delta is champion distance minus candidate distance; positive favors candidate.
W/L/T is over case medians, not over individual seed pairs. A/B/C/D below are
local labels for branch prefixes 946d4396/c9eb2fce/6f0b4a38/d87b4965.

| Step | Branch / actual proposal | Pairs | Case W/L/T | Median [recorded CI] | Outcome |
|---|---|---:|---|---|---|
| 1 | A: two-slot ALNS opening | — | — | — | C abandons after four failed self-tests |
| 2 | B: SWAP* before initial VNS | 10 | 0/3/2 | -4 [-125.5,0] | continue |
| 3 | C: route-pair bound screen | 10 | 1/1/3 | 0 [-17.5,11869] | continue |
| 4 | A: versioned pair closure | 10 | 1/1/3 | 0 [-39.5,48.5] | continue |
| 5 | B: SWAP* after first 2-opt | 10 | 0/3/2 | -4 [-93.5,0] | continue |
| 6 | C: fused pair move oracle | 10 | 1/2/2 | 0 [-56.5,11810] | continue |
| 7 | A: restore relocate/Or-opt order | 10 | 0/2/3 | 0 [-129,0] | continue |
| 8 | B: two-branch SWAP* lookahead | 10 | 0/3/2 | -4 [-583,0] | continue |
| 9 | C: source-unit oracle wrappers | — | — | — | V5 solution-consistency rejection |
| 10 | A: restore pair restart order | 10 | 1/1/3 | 0 [-55.5,21] | continue |
| 11 | B: replace lookahead with ejection chain | 10 | 2/1/2 | 0 [-81,42] | expand |
| 12 | B: same candidate, expanded | 24 | 3/0/3 | +11.5 [0,43.25] | queue validation |
| 13 | B: same candidate, validation | 12 | 1/4/1 | -39.75 [-459.5,2.75] | abandon |
| 14 | D: sampled capacity-aware SWAP* ranking | 10 | 3/1/1 | +9 [-140,16] | expand pending |

All ordinary initial screening negatives retain their verified branch heads.
V5-rejected step 9 does not replace C's accepted step-6 source. B's validation
failure abandons B; step 14 starts a fresh branch from the champion, not B's
failed candidate. The 12-stage requested stop does not authorize resuming R15.

### The candidate that reached validation

[Expanded screening](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/metrics/1bb82728-0573-458e-b424-f52691e80f3e.json)
has case medians: B34 0, tai100a +29, X351 +57.5, A54 0, X190 +23,
X513 0. The ejection-chain implementation really removes the inherited early
lookahead. It can cross a 0.5%-of-snapshot worsening corridor for up to eight
relocations, then commits only an exactly better feasible state.

However, X351 and X513 have **no ejection-chain event and zero ALNS** in all
six pairs per case across the initial and expanded screens. Their initial VNS
consumes the available budget. X351's positive expanded median therefore
cannot be credited to the chain. X190 does execute the chain, accepting a
23-distance local gain at all four expanded seeds, but its final pair deltas
are -19, +103, +23, +23: local activation is not uniform final improvement.
Small-case chain activity also occurs in full-scope embedded invocations;
the implementation is once per full-scope VNS call, not once per whole solve.

[Operator-only validation](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/metrics/4e5b9aba-3bd9-43d6-a1af-d07524fb040e.json)
is complete and negative: B39 0, X106 -67, tai385 -726, A62 -12.5,
X228 -459.5, X627 +5.5. Preserve `VALIDATION_FAIL_CASE_QUALITY` and the
recorded abandon. These case/outcome details must not enter later H/C input.
There is no basis for claiming generalization or promotion.

### The strongest localized discovery is not the last candidate

Step 3's [pair-bound screen](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/metrics/82ddc660-a695-4795-92b7-0d542a442ca9.json)
has X351 pair gains +11636/+12102 (about 26.8%/27.9%). Initial VNS falls
from approximately 138.6 s to 88.7/87.0 s, and candidate ALNS executes 3/2
iterations versus zero. Step 6's [fused oracle](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/metrics/d08c04cd-f442-4870-92be-f639103e1e0d.json)
retains approximately +11810 X351 case median and 2/3 iterations. This is
substantive active-path discovery, but only on one case and two seeds; tai100a
regresses, step 6 also regresses X513, and neither passes overall case quality.
Step 6 actually changes relocation/string selection order, so these are bundle
effects, not proof of a semantics-preserving accelerator.

Step 14's [last screen](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/metrics/52df4158-65c7-4889-90b9-050cbcd5a1ae.json)
has B34 0, tai100a +9, X351 -140, X190 +12, X513 +16. tai100a and X190
have opposite-sign seed effects; X351 loses both seeds. It is an unconfirmed
initial signal, not the best demonstrated solver. Although customer samples
and retained heap size are bounded, ranking still visits every eligible route
pair and computes insertion scans before retaining ten pairs. The sampled
minimum is not a certified lower bound over unsampled exchanges. Initial VNS
on X190 rises from about 2.4–2.8 s to 4.5–4.7 s; no broad speedup is shown.

## What improved in the agent research

- H reads actual branch-current source and ordinary history. It correctly
  identifies changed relocate/Or-opt traversal semantics in steps 7/9, and
  changed pair-restart order in step 10. The latter proposals explicitly
  distinguish cumulative candidate effects from the latest edit's effect.
- B's step-11 replacement really deletes `_branch_lookahead`; the R14 pattern
  of merely describing a replacement while leaving that mechanism inherited
  is not repeated in this example.
- Broader five-case initial screening actually evaluates X190/X513 instead
  of using an off-population result to judge those mechanisms.
- The live transport is healthy and deterministic boundaries reject invalid
  code / adverse validation. No evidence of source loss or sibling-code mixing.

These are observations, not a controlled causal estimate of the new prompt.
R15 also changes seeds, history and initial population relative to R14.

## Remaining concrete problems

### 1. Repeated research on an inactive entry path

A's steps 4, 7 and 10 implement and refine `_initial_vns_operators`, but the
only scheduler connection is inside `_run_progress_sensitive_initial_vns`.
The caller requires `customer_count > self.alns_threshold`; unchanged
`ALNS_THRESHOLD=2000`, while screening covers 33–512 customers. The ordinary
initial path still calls `_default_vns_operators`.

See the final full [scheduler](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/candidate_workspaces/candidate-rf9up1s9/policies/baseline_modules/scheduler.py:611),
[unused connection](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/candidate_workspaces/candidate-rf9up1s9/policies/baseline_modules/scheduler.py:699),
and [threshold](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/candidate_workspaces/candidate-rf9up1s9/policies/baseline_modules/config.py:39).
All three are real source edits, but their proposed mechanism is untested on
this population. Thirty formal pairs cannot support its benefit or harm.
H then reasons about its ordering from observed bundle deltas without first
establishing that this modified path ran. Complete context was available;
this is research grounding / implementation-fidelity failure, not lost source.

The step-4/7/10 self-tests directly invoke the helper, inspect the operator
list, or use mocked routes. They do not exercise the actual scheduler entry.
Contrast C's step 3, which connects its initial operators to **both** initial
paths and does produce the X351 activation signal.

### 2. A mock test concealed missing production methods

Step 9 changes wrappers to call `oracle.relocate_unit` and
`oracle.or_opt_unit`, but `_RoutePairMoveOracle` still defines only its
previous pair methods (`relocate`, `or_opt`, `swap`, `two_opt_star`, etc.).
Its [self-test](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/llm_traces/20260927T183209623403_code_research_turn_10305a0b.json)
supplies a fake `Oracle` that implements `relocate_unit`. That checks wrapper
wiring but cannot demonstrate that the real class works. Public checks and
this probe pass, while formal V5 rejects the candidate before Protocol.
The [safe history](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/research_history.jsonl:8)
preserves the full faulty file. Missing real methods are a definite static
defect consistent with V5; the available JSON does not expose its exception
stack, so this audit does not assert the unique runtime exception cause.

### 3. Self-test feedback remains opaque and tests can miss the claim

There are 17 development-test requests: all host public suites pass; the
optional falsifier is failed six times, passed ten times, omitted once.
No C8/C9 rejection occurs. Consequently this run does **not** live-exercise
the new import/API preflight feedback; its prior focused tests and R14 static
diagnostic remain the evidence for that repair.

In step 1, four different drafts receive only `falsifier_outcome=failed`.
The first probe even monkeypatches `scheduler._frequency_removal`, although
that import is local to `solve`, not a scheduler module attribute. Such test
construction errors cannot be separated from failed mechanism assertions by
the returned enum. A fifth untested revision is correctly refused by `ready`,
then abandoned at the local 12-turn/four-test bound. This uses 19 calls, not
the global 600-call budget. No claim that another budget increase fixes it.

In step 3, the exact-equivalence probe fails; the next executable revision
changes the numeric margin from 16 to 32 times EPS and is tested **without**
that probe. Existing host checks permit it, and the old failed executable
value is not re-exported. Nevertheless, equivalence has not been re-established.
Do not infer intent or silently treat omission as proof that the failed claim
was repaired. In step 8 a failed probe is revised and rerun successfully, which
is a better observed feedback loop but still only as strong as its fixture.

The current sandbox discards test stdout/stderr and maps pytest exit code 1
to `failed` (`verification/development.py::run_probe/_execute`). The missing
diagnostic is distinct from the C8/C9 preflight problem repaired before R15.
Any future feedback change needs a bounded, safe structural projection for
self-authored tests; never expose raw exceptions, private tests or host paths.

### 4. Timing-sensitive evidence still limits small gains

Across repeated unchanged champion executions at the same seed, X351 distance
ranges span 352 and 363 units; tai100a spans 29 and 105. This is larger than
several reported candidate effects. Time-limited execution can change the
search endpoint even with unchanged source and seed. The autonomous arm order
is champion-first, not counterbalanced. No competing maintenance/test/solver
was introduced by this audit, but absent such activity does not prove timing
noise is absent. Preserve the recorded decisions; require fresh balanced
confirmation before interpreting small discovery gains as retained benefit.

## Source and boundary audit

- All 100 champion files exactly equal the declared R13 R12-A-fixed snapshot.
- All 374 visible C path/content values exactly match the applicable current
  branch base. All 63 H visible source values match after prompt newline
  normalization. The cumulative-source guidance is present in all applicable
  H/C traces; C has no H-only history injected.
- All eleven exported `ready` patches match the corresponding full source
  values in ordinary history. No second confirmation follows successful ready.
- All three surviving 100-file trees exactly match their accepted branch
  histories: A `candidate-rf9up1s9`, C `candidate-9pklpiwd`, D
  `candidate-gcy643rg`. The C tree still contains step 6, not rejected step 9.
- B's abandoned full workspace and intermediate workspaces have been cleaned
  by normal runtime behavior. Its code is identified through unchanged
  complete base plus full-file history and exact ready context, not a surviving
  standalone stage snapshot: **PATCH_FALLBACK_IDENTIFIED**. This audit does
  not rematerialize or execute it, or fabricate a formal-candidate recorder.
- H-only history has eleven screening rows and one Verification rejection;
  no validation row. Validation details above remain operator-only.
- All 136 raw pairs were read, with 272 valid active solver arms and matching
  distance arithmetic; scientific intervals/verdicts are reported as recorded,
  not recomputed or overridden. No gate or source is changed post hoc.

Framework verdict: audited source/context, rejection and Decision paths work;
remaining shared research-support debt is bounded test-diagnostic usefulness,
not evidence of source corruption or unauthorized promotion. Research verdict:
real localized discovery and better cumulative reasoning, but repeated inactive
code, incomplete real implementations and weak self-tests still waste research.
No general or retained CVRP improvement is established.

## Next action, not executed or authorized by this status request

1. Preserve all negative/positive artifacts; do not resume R15 or select the
   last candidate merely because its initial median is positive.
2. Design bounded safe feedback for self-authored test failures, separating
   test/setup exceptions from actual assertion failures where evidence permits.
   Keep all Contract/Verification/held-out boundaries; no arbitrary traceback.
3. Improve ordinary research guidance/examples and public problem-owned test
   support for real entry-path activation and real collaborator integration.
   Do not mandate reads, mock bans, algorithm choices, novelty, or extra host
   quality gates. H/C remain responsible for choosing and testing mechanisms.
4. Before another run, independently review the research-support fix and its
   tests. If shared runtime changes, use the independent problem control per
   runbook. Any fresh algorithm experiment needs a prospective population,
   frozen complete source, clean output and unchanged scientific gates.
5. Treat the strong X351 signal and the last SWAP* signal as different,
   uncertain discovery leads. Broader balanced confirmation must precede a
   claim of superiority; private validation cannot be recycled into H/C advice.

No runtime/test/input changes, commit, push or launch were made in this analysis.

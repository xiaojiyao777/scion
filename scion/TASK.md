# Scion v0.4 Solver-Improvement Research Task

*Working branch: `v0.4-dev`*

*Accepted runtime baseline: `4d637959`*

*Last updated: 2026-08-14*

This is the active task source. `design/scion-architecture-v3.md` is the
sole architecture authority. The direct-runtime addendum may explain an
implementation choice, but it may not reverse a V3 research boundary.
`docs/status/current-state.md` records accepted evidence; detailed chronology
belongs in experiment reports.

## Objective

The lightweight direct-V3 runtime now has retained Warehouse solver evidence:
synthetic continuity reached v3 and production transfer reached and retained
v2. CVRP champion remains B0. Its first open-research rung produced valid
partial algorithm evidence, including one reproducible mixed-positive
depth-one repair signal, but stopped on infrastructure at 5/8 formal stages
and produced no promotion. This task is complete only when Scion also
demonstrates retained CVRP algorithmic improvement, not merely valid research
activity or a promising screening observation.

The required end state is:

1. **Warehouse continuity:** one fresh, uninterrupted campaign produces at
   least two Protocol-complete structural promotions (`v1 -> v2 -> v3` or
   later), and the final champion independently beats both v1 and its immediate
   predecessor on the declared held-out evidence.
2. **Warehouse transfer:** production-style Warehouse obtains at least one
   independently supported promotion, or a pre-registered matched experiment
   establishes that the remaining limitation is production headroom/noise
   rather than framework continuity. Multi-promotion is not required on
   production because v0.3 never established it there.
3. **CVRP improvement:** one exact candidate passes screening, validation and
   complete frozen holdout, receives deterministic `PROMOTE`, and independently
   improves the original B0 champion without feasibility or fleet regression.

If a finite experimental rung is negative, record the conclusion and redesign
the next rung. Do not relabel a scientifically valid negative result as task
completion.

## Current execution order

Work is split into bounded modules; a later module starts only when its stated
evidence prerequisite exists:

1. **R3 terminal boundary:** R3 is sealed
   `RUN_INVALID_INFRA / VALID_PARTIAL_SCIENCE` after the host rebooted during
   formal validation. Retain completed quality and chronological H/C evidence;
   do not adjudicate the partial validation, resume or retry it. No Protocol
   promotion means no recovery candidate.
2. **R45 comparison seam:** complete at `c32f5b8a`. The default-off
   fresh-subject AB/BA seam stayed within its 100-line production ceiling and
   passed 46 focused/adjacent tests plus independent review; it added no runner,
   ledger, gate or campaign expansion framework.
3. **Ordinary-lineage diagnosis:** the terminal outcome-blind reconstruction
   froze six chronological exact candidates and all three 53-file branch heads
   matched byte-for-byte. Diagnosis R1 is sealed
   `RUN_INVALID_INFRA / ZERO_ACCEPTED_BLOCKS / NO_ADMISSIBLE_ANALYSIS` after
   process disappearance during its first block. R2 completed 96/96 valid MDE
   pairs but its one-off driver rejected the legitimate auxiliary `routes`
   field before accepting the block and is sealed with zero accepted blocks.
   The fresh R3 replacement completed with exit `0`, all 37 atomic blocks and
   1,056 unique pairs. Its exact-roster MDE is `2.0`; the six complete `12x8`
   immediate-base medians are zero for five candidates and negative for one.
   Case/seed and budget contrasts are descriptive, while interaction and
   whole-budget-arm machine drift remain `UNIDENTIFIABLE`. The diagnosis selects
   no candidate and restores no formal recorder.
4. **Minimal V3 cleanup:** land only
   the reviewed problem-Protocol routing correction, bounded rejection
   diagnostic, minimal failure-only nondeterminism record and Warehouse canary
   completeness facts. Each is a separate small commit; no new gate, ledger or
   orchestration layer.
5. **Research-expression cleanup:** the frozen C-expression A/B is terminal.
   All four strict-diff cells failed exact source application while all four
   exact cells passed Contract, so retain exact and close strict diff. The
   follow-on research-hot-path subtraction is also complete: provider views are
   reduced to the V3 research core and the internal source ledger is replaced
   by ordinary editable source context with 278 net production lines deleted.
   H scientific content and tools remain unchanged; only host/control wrappers
   leave the provider view.
6. **Minute one-step complete:** the fresh short CVRP
   [one-step experiment](docs/experiments/v0.4/v0.4-cvrp-minute-one-step-postrun-20260812.md)
   completed once with exit `0` on the clean `e4b6b98d` runtime. One Terra H
   and one approved-H-bound C produced a single active solver change; Contract,
   Verification, canary and four fresh SCREENING pairs completed through
   `run_one_step()` exactly once. The exact result is `0W/1L/3T`, median
   `0 [-16,0]`, no fleet regression and
   `SCREENING_FAIL_CASE_QUALITY`; B0/v1 remains champion. The run proves a
   stable analyzable research step, not solver improvement. It never drained
   validation/frozen, promoted or resumed. Warehouse measurement reanalysis
   remains non-blocking backlog.
7. **R54 feedback-conditioned one-step terminal:** the second short CVRP
   [postrun](docs/experiments/v0.4/v0.4-cvrp-minute-feedback-one-step-postrun-20260812.md)
   is sealed `VALID_TERMINAL_CANDIDATE_RUNTIME_FAILURE / DECISION_ABANDON /
   FRAMEWORK_POST_DECISION_CONTEXT_PERSISTENCE_ERROR / NO_PROMOTION`. H used
   the R53 feedback well and selected elapsed-budget simulated annealing. C was
   conceptually faithful but removed `cool()` while leaving three negative-path
   calls. Verification did not cover those branches; P-n65 produced a typed
   candidate runtime-audit failure, while E-n101, X-n120 and X-n233 were three
   valid ties. P's emitted objective is excluded from delta and W/L/T. Decision
   abandoned the candidate, then canonical screening-context persistence raised
   a separate cardinality `ValueError`, causing wrapper exit `1`. B0/v1 remains
   champion; no next experiment is preregistered by this closeout.
8. **R55 Verification/accounting correction complete:** screening-context
   persistence now accepts three valid feedback rows plus one separately typed
   candidate failure without weakening exact W/L/T accounting. CVRP V3/V4 now
   execute subsecond problem-owned recovery and public-entrypoint tests instead
   of skipping; the tests are mechanism-agnostic consistency checks, not a new
   quality or novelty gate. A provider-free replay of the exact R54 patch fails
   all three recovery fixtures and therefore would have rejected it before the
   formal screen. No provider call or Protocol/formal experiment was rerun;
   only provider-free unit/smoke verification ran. No next H/C is launched or
   authorized by this correction.
9. **R56 corrected-runtime minute step terminal at Verification:** the
   [postrun](docs/experiments/v0.4/v0.4-cvrp-r56-minute-corrected-one-step-postrun-20260812.md)
   seals `VALID_TERMINAL_RESEARCH_PROCESS_OBSERVATION /
   VERIFICATION_LIGHT_REJECTED / ZERO_PROTOCOL_EVIDENCE / NO_DECISION /
   NO_PROMOTION`. The wrapper exited `0` after one Terra H/C and a passing
   Contract. H explicitly required elapsed-budget updates on all recovery paths
   and no stale cooling API. C retained that intent but its indentation-specific
   `replace_all` matched only one of five calls, leaving four calls to the
   removed `cool()` method. V3 rejected all three recovery fixtures in 519 ms;
   V4, canary, formal Protocol and Decision were not reached. B0/v1 remains
   champion. Do not repair or retry this root; redesign and test the minimal C
   expression/tool seam provider-free before considering another short run.
10. **R57 provider-free expression seam complete:** commit `f537fed5` adds the
   optional source-bound `exact_line_replace` edit intent for exact whole-line
   replacement across indentation levels. It adds no provider search/tool
   loop, retry, or quality gate. A counterfactual re-expression of the frozen
   R56 C response matched all five callsites through the production
   parse -> Contract -> materialize path, and non-skipped V3/V4 passed. This is
   expression-fidelity evidence only, not a new R56 or solver-quality result;
   no provider, canary, formal Protocol or Decision call ran. R57 itself did
   not preregister, authorize or launch a successor H/C experiment.
11. **R58 expression-corrected seed-29 minute step terminal at Verification:**
   the [postrun](docs/experiments/v0.4/v0.4-cvrp-r58-minute-expression-corrected-one-step-postrun-20260812.md)
   seals `VALID_TERMINAL_RESEARCH_PROCESS_OBSERVATION /
   VERIFICATION_LIGHT_REJECTED / ZERO_PROTOCOL_EVIDENCE / NO_DECISION /
   NO_PROMOTION`. The clean `42535efc` wrapper exited `0` after one valid Terra
   H/C and passing Contract. H again chose elapsed-budget SA. C saw all 11 files
   and the optional `exact_line_replace` form but emitted six uniquely applying
   `exact_replace` edits, deleted `cool()` and removed only two of five calls.
   V3 rejected the three residual recovery-path calls in 568 ms. V4, canary,
   formal Protocol, seed-29 comparison and Decision were not reached; B0/v1
   remains champion. Pause provider algorithm experiments and redesign/test the
   C expression-selection surface provider-free. Do not retry, resume, or
   launch an R59 provider experiment, a long campaign or a WSL run.
12. **R59 provider-free typed-tool presentation correction complete:** commit
   `47fe81ee` gives root and nested changes one shared flat schema factory.
   When `edit_intent` is explicit, four branches discriminate the three typed
   intents and their valid actions; legacy missing intent and default
   `replace_all=false` remain compatible. Exact-span and indentation-neutral
   exact-line choices are described in parallel, with one shape-only line-edit
   example that does not require its use. A mocked OpenAI request proves the
   actual `tools[0]` payload matches the version-controlled snapshot. Frozen
   R56/R58 counterfactual replays preserve the R58 original's three residual
   calls, while the line re-expression matches all five and passes non-skipped
   V3/V4. The scoped suite passed 170 tests and independent review passed 68.
   This is tool-presentation evidence only: no provider, canary, formal
   Protocol or Decision call ran and it supplies no algorithm evidence.
   Provider algorithm experiments remain paused.
13. **R60 C-only tool-presentation pair terminal with no separation:** the
   [postrun](docs/experiments/v0.4/v0.4-cvrp-r60-c-tool-presentation-pair-postrun-20260813.md)
   seals `TERMINAL_MATCHED_PAIR_OBSERVATION / BOTH / BOTH_LINE_SELECTION /
   NO_IDENTIFIED_PRESENTATION_ADVANTAGE / ZERO_ALGORITHM_QUALITY_EVIDENCE`.
   The fixed OLD `42535efc` then NEW `47fe81ee` pair completed exit `0` in
   about 69 seconds with two terminal Terra C responses, zero H/retry and both
   opaque primary records written before reveal. Both arms passed parse,
   source binding, Contract, materialization and non-skipped V3/V4. Both also
   selected one five-match `exact_line_replace` and left zero residual
   `annealing.cool()` calls. The old presentation therefore also succeeded on
   this call; one fixed-order pair cannot identify an R59 causal advantage.
   Post-hoc source inspection found duplicate destroy-weight recording in OLD
   and an uncalled deadline-progress setter in NEW, so neither proposal enters
   algorithm testing. Canary, formal Protocol, Decision and algorithm-quality
   calls are zero. At R60 closeout, provider algorithm experiments remained
   paused and no R61 had been preregistered or launched.
14. **R61 provider-free semantic audit terminal:** the
   [postrun](docs/experiments/v0.4/v0.4-cvrp-r61-provider-free-semantic-audit-postrun-20260813.md)
   seals `TERMINAL_DIAGNOSTIC / SEPARATE_ENDPOINT_TRADEOFF /
   ZERO_ALGORITHM_QUALITY_EVIDENCE`. Fresh subprocesses drove one synthetic
   ordinary worsening iteration at progress `0.1` and `0.9` from read-only R60
   workspaces. OLD wired progress and cooled
   `2.6857958838184386 -> 0.018616455666360693`, but recorded destroy/repair
   weights `2/1`. NEW defined the deadline setter but called it zero times and
   stayed `5.0 -> 5.0`, while weight accounting was `1/1`. The endpoint vector
   remains separate and `aggregate_algorithm_success=null`. Provider, canary,
   formal, quality and benchmark calls are zero; R60 primary evidence is not
   rewritten, provider pause remains and no R62 is preregistered or launched.
15. **R62 provider-free C semantic-risk sidecar terminal:** the
   [postrun](docs/experiments/v0.4/v0.4-cvrp-r62-provider-free-c-semantic-risk-sidecar-postrun-20260814.md)
   seals `TERMINAL_CALIBRATION / SEPARATE_SYNTAX_RISK_SIGNALS /
   ZERO_ALGORITHM_QUALITY_EVIDENCE`. The frozen fresh-B0 projection, sealed R60
   workspaces and ephemeral controls calibrate two independent T/F/UNKNOWN
   syntax signals. Alpha is same-name-call `TRUE` and adjacent-call-risk-absent
   `FALSE`; beta is `FALSE / TRUE`. Fresh B0 is `UNKNOWN / UNKNOWN`; cleaned
   controls are `TRUE / TRUE`, the branch control is `UNKNOWN / TRUE`, and the
   callback control is `UNKNOWN / FALSE`. Receiver type and call effects are
   unresolved; both aggregate fields remain null. Provider, Contract, V3/V4,
   Protocol, Decision, quality and benchmark calls are zero. No production
   source, gate, R60 or R61 artifact changed. At R62 closeout, provider pause
   remained and no R63 was preregistered, authorized or launched.
16. **R63 whole-patch-review message pair terminal with no identified
   message-review advantage:** the
   [postrun](docs/experiments/v0.4/v0.4-cvrp-r63-c-message-whole-patch-review-pair-postrun-20260814.md)
   seals `TERMINAL_MATCHED_PAIR_OBSERVATION / BOTH /
   NO_IDENTIFIED_MESSAGE_REVIEW_ADVANTAGE /
   ZERO_ALGORITHM_QUALITY_EVIDENCE`. The fixed
   CONTROL→REVIEW pair completed exit `0` in about 55 seconds with H/retry
   zero, two terminal Terra C outcomes, two opaque scores and two opaque
   sidecars. Both 13-field mechanical vectors are entirely true; both changed
   only `_two_opt_star` in `local_search.py` with near-matching boundary-delta
   patches. The sidecars are `UNKNOWN/TRUE` for both arms. V3/V4 passed but do
   not enter `_two_opt_star`: V3 disables embedded VNS; V4 passes `0.01`
   seconds, but `_algorithm_time_limit` clamps the scheduler time limit to
   `0.05` seconds, equal to its minimum `0.05`-second reserve, so strict
   `remaining_time() > reserve` is not met. Thus they do not establish cut-pair
   equivalence, directed correctness or near-EPS behavior. No canary,
   formal Protocol, quality solver or Decision ran. One fixed pair cannot show
   review benefit, ineffectiveness or harm; the seal does not mean the suffix
   was ineffective or the model did not review. At R63 closeout, no R64 was
   preregistered, authorized or launched.
17. **R64 provider-free `_two_opt_star` semantic diagnostic terminal:** the
   [postrun](docs/experiments/v0.4/v0.4-cvrp-r64-provider-free-two-opt-star-semantic-diagnostic-postrun-20260814.md)
   records one `TERMINAL_DIAGNOSTIC` formal root created at
   `2026-08-14T09:41:56Z`, with `complete=true` and
   `semantic_endpoints_claimed=true`. Both arms durably reproduce
   `TRUE/TRUE/TRUE` for cut-delta, near-EPS and first-improvement-state
   equivalence, with descriptive distance-evaluation calls `0`. All 27 cut and
   three near-EPS cases equal their references; the three state fixtures have
   candidate/reference accepted-move counts `0/0`, `1/1`, and `5/5`, equal
   traces/final states, all invariants and no exceptions. Classification and
   both aggregates remain null. The formal role is
   `DURABLE_REPRODUCTION_OF_EXACT_CANDIDATE_CALIBRATED_PROVIDER_FREE_DIAGNOSTIC`,
   with `outcome_blind=false` and `independent_confirmation=false`; it is not
   independent evidence. All provider, Contract, V3/V4, canary, formal
   Protocol, quality, Decision and mutation counters are zero. Provider pause
   remains and R63 is unchanged. At R64 closeout, no R65 was preregistered or
   authorized.
18. **R65 exact-alpha minute quality calibration terminal with no signal:**
   the
   [preregistration](docs/experiments/v0.4/v0.4-cvrp-r65-provider-free-r63-alpha-minute-quality-calibration-preregistration-20260814.md)
   freezes a provider-free comparison of exact B0 against only sealed R63
   `cell_alpha/control_original_message`. Alpha is a neutral ordinal-0
   tie-break, not a quality selection. After one fresh B0/alpha seed-101
   two-second veto canary, a passing canary permits exactly four fresh,
   cache-disabled pairs on P65/E101/X120/X233 with seed 73, per-subject limits
   8/12/12/15 seconds and orders AB/BA/AB/BA. The ceiling is ten solver
   subprocesses, 98 subject-seconds, 300 seconds and concurrency one; provider,
   H/C, Contract, V3/V4, retry/repair, validation/frozen, Decision, promotion,
   beta and R66 are zero. Historical R1 already tested the same mechanism more
   strongly (`3W/0L/29T` pairs, `0W/0L/8T` cases, median `0 [0,0]`): stage 1
   had zero champion cache hits, while most later R1 B0 observations were
   cached. R65 is only an implementation-specific exposed-
   coordinate calibration, never effect or independent evidence. At final
   preparation its status was
   `PREPARED_NOT_STARTED / AWAITING_EXPLICIT_SOLVER_EXECUTION_AUTHORIZATION`;
   generic assent and R64 authorized no canary or SCREENING subprocess.
   The frozen nine-file input binds preregistration SHA-256
   `4905fdfca6b91d6c24d5e8be3eb736060671dad9d468976122e9ee953323f8ac`.
   Env-injected `launch.sh --preflight-tests` passed 42 tests in 0.87 seconds;
   an independent run passed the same 42 in 0.80 seconds.
   Outer pytest uses an `env -i` allowlist, with API/proxy/auth sentinels proven
   absent. Ruff check/format, `bash -n`, `jq`, and `launch.sh --check` pass;
   at final preparation check, cache/pyc and the formal output/control/socket
   roots were absent. Atomic
   staging-ref tests require durable `raw_metrics_ref`/fresh-workspace paths
   only after final rename. Fake acquisition proves the pid/acquired marker,
   `LAUNCHED` return and exit-code precedence without waiting for the formal
   output. Five manifest science-surface mutation negatives exact-bind formal
   role, research question, estimand, endpoints and claim boundary. The input
   tests also exclude timeout-ancestor self-conflict, bind the exact
   predelegated 10-subprocess/98-second ledger, directly bind R63 cell to score,
   capture the minimal child Python environment, and persist/re-require the
   sealed production runtime-audit validity endpoint. B0/alpha canary and
   SCREENING audit-only failure negatives preserve comparator/candidate
   precedence and null aggregates. The input directory and launcher are mode
   `0700`, the other eight regular non-symlink files are mode `0600`, and no
   exact candidate or solver ran during preparation. The user subsequently
   recorded the exact R65 authorization below verbatim:

   > 我明确授权执行一次 v04-cvrp-r65-provider-free-r63-alpha-minute-quality-calibration-20260814：以 51f9bbd77f1e93777bbe9c401b8ba05c09a3e819 的 exact B0 为对照，只使用 sealed R63 cell_alpha/control_original_message 候选和 sealed 47fe81ee6e17c04bc805197e2b2ad34e0fff4d14 runtime；先串行运行 B0/alpha 的 seed-101、每个 2 秒 veto canary，通过后仅在 P65/E101/X120/X233、seed 73、每 subject 8/12/12/15 秒、AB/BA/AB/BA、fresh 且 cache disabled 下运行一次四对 SCREENING。最多 10 个 solver subprocess、98 subject-seconds、单并发、300 秒 hard wall；provider/H/C/Contract/V3/V4/retry/repair/validation/frozen/Decision/promotion/beta/R66 均为 0。失败不重试、恢复、替换或追加 seed；无论结果如何 R65 停止。此授权仅覆盖这一 R65。

   Launch-only history: the launcher returned `R65_FORMAL_LAUNCHED` after
   acquisition at `2026-08-14T12:53:36Z`, with `inner_pid=514140`. R65 was
   then `IN_FLIGHT`; no outcome was read for that update. The byte-bound
   preregistration remains unchanged at SHA-256 `4905fdfc...`.

   The
   [postrun](docs/experiments/v0.4/v0.4-cvrp-r65-provider-free-r63-alpha-minute-quality-calibration-postrun-20260814.md)
   seals `VALID_COMPLETE_EXPOSED_COORDINATE_MINUTE_CALIBRATION /
   EXPLORATORY_SCREEN_NO_SIGNAL / ORDINARY_MINUTE_RULE_NOT_MET /
   NO_GO_EFFECT_INFERENCE / NO_MORE_PROVIDER_FREE / NO_R66`. All ten fresh
   subprocesses and 98 declared subject-seconds completed. B0 then alpha both
   passed the seed-101 canary at distance 20. The seed-73 AB/BA/AB/BA screen
   produced exact ties at P65=798, E101=1124, X120=14250 and X233=20112:
   `0W/0L/4T`, deltas `[0,0,0,0]`, median `0 [0,0]`, and zero protected fleet
   regressions. Route counts also tie `10/10`, `14/14`, `6/6`, and `17/17`.
   Every subject was successful, feasible and runtime-audit valid; raw metrics
   are 4/4 valid with zero failures and cache hits/misses/writes. Alpha-minus-B0
   elapsed deltas `[-80,-24,-4,-427]` ms, median `-52` ms, are association-only
   and support no causal speed claim. Decision and promotion are null; all
   declared zero-call/action fields remain zero. R65 stops with no effect
   inference and no R66.
19. **R66 original action and recovery1 are terminal infrastructure failures;
   recovery2 is provider-free prepared and awaiting authorization:** the
   [preregistration](docs/experiments/v0.4/v0.4-cvrp-r66-h-only-mechanism-frontier-probe-preregistration-20260814.md)
   freezes one prior-informed, non-blind Terra H observation over the exact
   fresh-B0 11-source values at `51f9bbd7` and the clean production H carrier
   at `47fe81ee`. Source is carried only as production
   `champion_operators_code`; the typed question has no `research_prior`, and
   experiment history, last rejection, branch-current code and the ordinary
   outcome-rich cross-campaign prior are absent. The exact current question
   asks for one bounded causal mechanism outside the neutral E01–E10
   replay/tuning/repair frontier; the
   ledger is not a novelty gate or permanent blacklist. Production system
   blocks and the base H prompt remain unchanged; the exact production
   context-bound H tool permits only `change_locus=solver_design`, with no
   experiment-owned schema change. The exact ledger block is appended with no
   explicit `prompt_cache_key`. The
   envelope is H at most one, 180-second provider timeout, retry zero and a
   300-second outer wall. Mechanical recording is limited to provider
   completion, exactly one expected named tool, argument availability/JSON and
   typed hypothesis-schema validity. Scientific classification, algorithm
   quality, Decision and promotion remain null. C, patch, materialization,
   Contract, V3/V4, solver, canary, Protocol, quality/formal evaluation,
   Decision, promotion, repair, retry/resume/substitution and R67 remain zero.
   The user finally authorized this one immediate H-only action verbatim:

   > 我明确授权执行一次 v04-cvrp-r66-h-only-mechanism-frontier-probe-20260814：将 commit 51f9bbd77f1e93777bbe9c401b8ba05c09a3e819 的 fresh-B0 CVRP problem-owned 11-source 源码派生上下文（local_search.py、baseline_algorithm.py、acceptance.py、config.py、construction.py、destroy_repair.py、route_first_heuristic.py、route_first_improvement.py、route_first_seeding.py、scheduler.py、state.py），连同冻结的研究问题、E01–E10 机制排除表以及 clean 47fe81ee6e17c04bc805197e2b2ad34e0fff4d14 production H system/tool，通过本机 Codex proxy http://127.0.0.1:8080 发送给 gpt-5.6-terra。最多执行 1 次 H、180 秒、retry 0；不得发送历史 H/C response、候选或结果；C、patch、solver、canary、Protocol、Decision、promotion 和 R67 均为 0。此授权仅覆盖这一 R66 H-only 调用。

   The authorized action was invoked once after the UTC date changed to
   2026-08-15. Before inner-process acquisition or any provider request, the
   outer provider-free check found one exact canonical-context drift:
   `calibration_age_days` was frozen at `64` but rebuilt at `65`. The
   [postrun](docs/experiments/v0.4/v0.4-cvrp-r66-h-only-mechanism-frontier-probe-postrun-20260815.md)
   seals `PREP_INVALID / OuterPreflightFailure / NO_PROVIDER_REQUEST /
   NO_H_OBSERVATION / NO_RETRY / NO_R67`. The sole control root records
   `exit.code=1`, H attempts/provider calls zero, no provider terminal response
   and all downstream counters zero. Formal output, socket/session and inner
   acquisition markers are absent. No payload was sent and no H exists to
   assess. The terminal policy forbids repair, retry, resume, substitution,
   same-label relaunch, C, solver work or R67; S6 remains open.

   The original terminal record remains unchanged. After its one-field date
   diagnosis, the user issued this exact recovery instruction:

   > 是的，那你直接去掉，做好修复，然后继续实验

   The append-only recovery amendment resolves that instruction only to fresh
   label
   `v04-cvrp-r66-h-only-mechanism-frontier-probe-20260814-recovery1`.
   Its manifest separately exact-binds the historical broad continuation
   statement, the later full eleven-source disclosure authorization, and the
   exact recovery instruction; none substitutes for another.
   Its sole corrected invariant reconstructs production static context with
   typed `as_of=2026-08-14`, yielding the frozen `calibration_age_days=64`
   instead of comparing against the later wall-clock date. Every other source,
   runtime, prompt, tool, question, ledger, schema and fresh-root equality
   remains. Original plus recovery1 still permit at most one H call because the
   original consumed zero; provider retry, C, patch, solver, Protocol,
   Decision, promotion and R67 remain zero. At its provider-free launch freeze,
   recovery1 was `RECOVERY1_PREPARED_AUTHORIZED_NOT_STARTED`; no recovery
   provider call had started. Its historical frozen input-tree preparation
   receipt, public-call payload, counterfactual OpenAI-create kwargs and
   manifest SHA-256 values are `89e7994a...`,
   `573d4451...`, `0dc1c5b4...` and `ba196da1...`; the public receipt is not
   the SDK kwargs. The counterfactual kwargs use float timeout `180.0`, exclude
   `prompt_cache_key`, and were never emitted because recovery1 failed before
   kwargs evaluation. The tree has 4,191 files and 72,632,636 bytes.
   Thirty-six tests pass in 11.91 seconds together with
   runner/style/shell/JSON checks, with fresh output/control/socket roots
   absent.

   Recovery1 subsequently acquired at `2026-08-15T03:23:06Z`, PID `591276`,
   and then exited `3`. The
   [recovery1 postrun](docs/experiments/v0.4/v0.4-cvrp-r66-h-only-mechanism-frontier-probe-recovery1-postrun-20260815.md)
   preserves the emitted `TERMINAL_HYPOTHESIS_PROVIDER_FAILURE`, logical
   `h_attempts=1`/`hypothesis_provider_calls=1`, no provider terminal response,
   error `API error: No module named 'jiter'` and latency 637 ms. Read-only
   causal audit separately seals
   `RUN_INVALID_LOCAL_INFRA / MISSING_JITER_BEFORE_REQUEST`: lazy
   `client.chat` import failed before HTTP, so actual outbound model requests,
   research-payload sends and H observations are zero. Every downstream/R67
   counter is zero. Result/status SHA-256 values are `a781f1fb...` and
   `af1608d8...`; `exit.code=3`, the inner PID is gone, and the mode-`0600`
   recovery1 socket remains stale.

   A provider-free recovery2 now vendors exact `jiter==0.13.0` as nine files
   under `vendor/python312`, keeps `PYTHONNOUSERSITE=1`, and exercises the exact
   lazy chat dependency seam without HTTP. Its status is
   `RECOVERY2_PREPARED_AWAITING_EXPLICIT_AUTHORIZATION`. The earlier source-
   send and recovery1 instructions remain preserved, while new field
   `recovery2_source_send_authorization_text` is null; they do not authorize
   recovery2. It must not launch until the user explicitly authorizes its exact
   fresh roots and at-most-one H envelope and overrides the prior no-recovery2
   stop for this one action; C, solver, Decision, promotion and R67 remain zero.
   Its frozen provider-free receipt is 4,200 files/73,523,973 bytes, tree
   SHA-256 `f8e82201...`, manifest SHA-256 `e056afcf...`, and 47 passing tests
   in 12.15 seconds plus runner/style/shell/JSON checks. Output, control and
   socket roots remain absent; this preparation sends no provider payload.
20. **S6 closeout:** only after retained CVRP improvement, run the full relevant
   regression record and publish the cross-problem claim boundaries.

## V3 non-negotiable boundary

The active path remains:

```text
complete safe problem facts + complete current branch source + prior safe evidence
  -> one structured Hypothesis call
  -> structural Hypothesis Contract
  -> one approved-H-bound Code call
  -> structural Patch Contract
  -> isolated Workspace
  -> executable Verification
  -> problem-owned paired Protocol
  -> Safe Features
  -> deterministic Decision
  -> exact stage reuse, branch iteration, or promotion
```

- LLM output is tainted proposal material. It never selects Protocol outcomes,
  Decision actions, cases, seeds, or promotion.
- Contract protects schema, approved-H binding, editable/frozen paths, public
  interface, import resolution, injected randomness, and dangerous host
  capabilities. It must not grade algorithm taste, patch style, novelty,
  activation, or expected performance.
- Verification owns import, execution, feasibility, objective semantics,
  determinism, state isolation, and declared behavioral invariants.
- Protocol owns paired comparisons and statistical gates. Decision consumes
  only typed Safe Features.
- Exact source, case/seed pairing, and stage reuse provide scientific
  determinism. Digests may compare content but confer no authority and create
  no lifecycle.
- A branch is one iterative research direction. Per V3 §11.2, a candidate that
  passes Verification and completes screening remains the branch's current
  code for the next same-branch H, even when screening does not promote it.
  Verification failure returns to the last clean branch source; a branch that
  has never verified code starts from champion.
- Promotion still requires the unchanged screening -> validation -> frozen
  Protocol. A provisional branch head is never a champion.

## Explicitly out of scope

Do not spend implementation, review, experiment, or root time on:

- distribution, deployment, installation, packaging, wheels, reproducible
  builds, release artifacts, systemd, D-Bus, cgroups, or `StartUnit`;
- root-owned source acceptance, Git mirrors, source signing, review closures,
  loaded-manager acceptance, or `/var/lib/scion` receipts;
- object identities, capabilities, leases, issuance/claim/spend flows,
  registration, nonce ledgers, owner authorities, or repeated
  intent/commit/closure self-proof;
- duplicate hashes, hash chains, or reopen proofs for facts already present in
  ordinary branch/source/evidence state;
- provider retry, Scion token/file/session budgets, token-triggered truncation,
  top-k evidence selection, opaque summary substitution, forced mechanisms,
  forced surfaces/actions/targets, novelty gates, or host-authored
  algorithm-quality gates. A fixed V3 semantic projection may keep recent
  current-branch research detailed, older evidence structured, and sibling
  state brief while preserving the complete raw scientific lineage;
- tuning Protocol thresholds, cases, seeds, or time limits after observing a
  candidate result.

Historical deployment and authority prototypes remain historical evidence.
They do not block this task and cannot satisfy it.

### Research-loop quality contract

Context, tool surface and experiment design are first-class research inputs,
not incidental framework plumbing. Before every fresh provider campaign:

- H receives the problem objective and invariants, solver mechanics, complete
  current research-surface source exactly once, legal actions/files, concise
  screening-level algorithm evidence and the latest actionable failure. It
  does not receive validation/frozen detail, authority metadata, source hashes,
  repeated rule packets or raw log accumulation. Campaign/branch/version
  identifiers, schema/taint labels and repeated `Decision-excluded` notices
  remain in the durable trace rather than competing with the research core.
- C receives the approved H, complete source/API context exactly once and a
  multi-file-capable implementation surface. The required structured terminal
  result may constrain data shape, but must not constrain algorithm taste,
  mechanism, patch size or style. Additional read/search/edit tools are an
  empirical proposal-surface choice: if introduced, they may inspect only the
  already visible source and can neither execute Protocol nor read protected
  evidence. Correct source anchoring with incomplete causal wiring is first an
  expression/fidelity question, not evidence that more tools are needed.
- Case population, family/size strata, ordered seeds, per-dimension time budget,
  estimator, equivalence rule, stage transitions and claim scope are frozen
  outcome-blind. An expansion should change one measurement axis at a time
  whenever attribution matters; case count and seed count must not be coupled
  merely for implementation convenience.
- H, C, screening, validation, frozen and independent replay answer different
  questions. The launch card states each phase's estimand and supported claim.
  A numerical change across disjoint case, seed or budget populations is not a
  research trajectory or causal stage effect unless a matched contrast was
  frozen for that purpose.
- The minimum durable record is the exact H/C context and terminal proposal,
  source/patch, Verification result, declared case/seed/budget coordinates,
  raw pair reference, aggregate Protocol result, Safe Features and Decision.
  Prompt self-proof, duplicate closure and provider-visible audit metadata are
  not research evidence.
- A negative root is decomposed into proposal focus, implementation fidelity,
  mechanism activation, search opportunity, case/seed heterogeneity,
  measurement reach and Protocol outcome. Only observed friction justifies a
  matched context/tool A/B; no diagnostic becomes a candidate gate.

## Evidence already accepted

### Previous lightweight V3 stage

- Baseline commit `4d637959` passed the complete suite:
  `1946 passed, 1 skipped, 0 failed`, plus compileall, focused Ruff/format and
  diff checks.
- Warehouse 3R produced 44/44 valid pairs; CVRP 4R produced 128/128 valid
  pairs. Every candidate crossed Contract, Verification and real Protocol.
- Both experiments remained at champion v1. They establish runtime validity,
  not retained improvement.

### Warehouse historical control

- v0.3 synthetic Warehouse really did promote: 6/6 campaigns promoted, with
  10 structural promotions. The strongest campaign promoted at rounds
  8/19/24/41 and reached v5; independent frozen replay beat v1 on all 12/12
  pairs for each final champion.
- v0.3 production was much weaker: corrected Sonnet runs produced one
  promotion per campaign; GPT-mini produced none. Therefore synthetic
  multi-promotion and production single-promotion are separate claims.
- Current 3R production evidence is not a regression comparison. Its third
  candidate reached 3W/0L/3T, median cost improvement +950 and CI [0, 10025],
  then stopped in `EXPLORE_EXPAND` with exact candidate reuse queued. The later
  1R run was a fresh root and did not continue that candidate.

### CVRP historical control

- Repeated successor work has already rejected or failed to resolve segment
  exchange, broad cross-exchange, destroy-size, lookahead repair, seed
  selection, route-pair overlap, double bridge, generic VNS allocation, and
  several pool/recombination variants. A new campaign currently sees little of
  this cross-campaign scientific history and can repeat an old weak direction.
- Bounded embedded-only SWAP* is one unresolved historical observation:
  screening and validation were positive and frozen observations were
  descriptively positive, but frozen evidence was incomplete, the candidate
  was cumulative rather than mechanism-isolated, and it starved ALNS on Tai
  cases. This evidence is neutral research context; it does not select the
  first H, prescribe an implementation or become a fallback ladder.
- The current B0 solver spends most search time in embedded VNS. Pure ALNS and
  globally disabling embedded VNS are both known regressions. These facts rule
  out a simplistic global switch but do not let the host choose the next
  mechanism.

## Root-cause register

| ID | Status | Finding | Consequence |
|---|---|---|---|
| R1 | resolved scientific negative | Warehouse 3R ended with an exact candidate queued for screening expansion. Exact eval-only replay passed expanded screening but timed out on 11/15 validation pairs. | Do not promote or tune around this candidate; proceed to a fresh long-horizon synthetic campaign. |
| R2 | proven | v0.3 synthetic campaigns ran 25-66 rounds; first promotion appeared at rounds 4-19. | A 3R campaign cannot test continuous promotion. |
| R3 | proven | Current production Warehouse has near-saturated split objective and noisy cost effects; v0.3 multi-promotion used high-headroom synthetic cases. | Use synthetic recovery and production transfer as different controls. |
| R4 | proven baseline deviation; corrected on current branch; causal effect unproven | The accepted baseline mapped screening `fail` to clean-parent rejection, contrary to V3 §11.2. | Keep the lightweight provisional branch head and test it without changing promotion gates. |
| R5 | proven context gap | Warehouse H context omits solver mechanics such as pool size, iteration/stagnation limits, weights and operator-pool wiring. | Add transparent problem-owned mechanics, not a gate. |
| R6 | observed attribution limit | Create-new Warehouse operators alter both mechanism and pool allocation; direct invocation/adoption is not visible. | Use minimal problem-owned counters only for analysis; never Decision. |
| R7 | proven | CVRP candidates often combine an algorithm idea with broad rewrites or large runtime cost. | Test one mechanism and preserve unrelated source before formal scale-up. |
| R8 | proven | Several CVRP changes were inactive or activated too late; others consumed ALNS opportunity. | Retain activation and allocation telemetry only as analysis and next-H feedback; do not create another candidate gate. |
| R9 | proven and corrected with R19 | CVRP campaigns repeat known failures because accepted cross-campaign conclusions were absent from the actual H context. A problem-owned prior was added, but component-level presence did not establish provider-visible delivery. | The short neutral prior now reaches the active H path without selecting a target, surface, action or Decision. |
| R10 | proven | Repeated pair trees make later prompts grow sharply while adding little new information. | Use fresh one-candidate lines now; later allow only reversible lossless factoring. |
| R11 | proven and corrected at `88c1bc2b` | Warehouse continuity R3 promoted one candidate to v2, then stopped at 6/36 when a patchless stale branch was misclassified as a markerless research rejection. | Retire that stale branch as non-research lifecycle work and let typed Contract/Verification rejection schedule forward without a second disposition authority. Preserve all infra and missing-outcome stops. |
| R12 | resolved launch invalidity | R4 passed the literal `<stdin>` as the proxy key because of an operator-side `jq input_filename` mistake. It stopped on the first H with 401, 0 evaluated stages and 0 experiments. | Seal R4 with no scientific conclusion. R5 uses one exact key extraction plus a silent authenticated `/v1/models` check in a fresh root. |
| R13 | resolved infrastructure exclusion | R5 authenticated and completed H, but its first C stream ended upstream after 2,022 partial events without a terminal event; the proxy intentionally returned 504. There were 0 evaluated stages and 0 experiments. | Seal R5 with no C/source or scientific conclusion. R6 is a fresh matched campaign with new H/C; do not replay the failed C or change Scion/proxy configuration from one intermittent event. |
| R14 | proven and corrected on the current branch | R6 produced one complete Warehouse promotion and then fourteen more formal screenings, but stopped at 17/36 when a provider-complete C used an `exact_replace` selector absent from the visible source. Proposal ownership misclassified that tainted-content rejection as terminal `NOT_EVALUATED`. | Keep exact source binding strict, classify malformed/schema-invalid H/C and unapplicable typed edits as `RESEARCH_REJECTED`, release only that H/C, and scheduler-forward to a fresh H on the clean base. Never retry the failed call; local context/binding, missing outcome, provider-without-terminal-response, infra, resource and interruption outcomes still stop. |
| R15 | resolved infrastructure exclusion | R7 completed three screening and one validation stage with 62/62 valid pairs, then its third C ended upstream without a terminal event. The runtime correctly stopped `BLOCKED_INFRA`; proxy authentication/account state remained healthy. | Seal R7 as 4/36 valid partial science with two candidate negatives and no promotion. Do not replay its failed C. One fresh matched R8 may sample new H/C without changing framework, proxy configuration or scientific inputs. |
| R16 | proven; retained replay complete | R8 completed all 36 formal stages and 534/534 pairs, continued through two candidate-local research rejections, and promoted exact candidates `89f3edbb...` and `3f204b01...` from v1 to v2 to v3 in one campaign. Its separately preregistered held-out replay completed 108/108 valid pairs with all three comparisons positive. | Warehouse synthetic continuity is `CONTINUOUS_OPTIMIZATION_CONFIRMED`; production transfer remains a separate S4 question. |
| R17 | proven task-design violation | The proposed CVRP public assay could stop an exact verified candidate for being inactive or starving search before the existing Protocol/Decision route completed. Calling it observational did not remove its disposition authority. | Remove assay admission and host-stop. Diagnostics may explain evidence or inform the next H, but only Verification and the declared Protocol/Decision path may reject or advance a candidate. |
| R18 | proven and corrected | Expanded evaluation accepted case ids derived from the current branch's wins and losses, so result-dependent evidence could change the same candidate's expanded screening population. | Outcome-derived case selection is removed. Expansion uses only the case population and deterministic selection frozen in the pre-experiment Protocol; fixed problem-owned case priorities remain valid when declared before results. |
| R19 | proven and corrected | The CVRP cross-campaign prior existed in problem-owned guidance but did not reach the active provider H, while the host prompt asked for a `materially different` mechanism and thereby suppressed valid V3 same-branch refinement. | The complete neutral prior now reaches H, and `materially different` is removed as a prompt or Contract quality requirement. Exact approved-H binding remains; novelty and refinement choice belong to the agent. |
| R20 | proven production evidence | The fresh prod-1.1 12-stage Warehouse shakedown completed 211/211 formal pairs and produced a final candidate with 5/0/0 validation cases and 14/1/0 pairs, but the primary split CI remained `[0,1]`; Protocol queued expansion and the horizon ended with champion v1. | Classify it only as `VALID_FUNNEL_FOR_24STAGE_PREREGISTRATION`; seal the root and use a fresh 24-stage campaign. It is neither a promotion nor a framework failure. |
| R21 | proven and corrected | Production validation declared `n_cases=5` and `expand_to=5`, so queued expansion would repeat identical cases and seeds. The execution path also ignored declared `bootstrap_n=10000` and used the statistics default. | An expansion must strictly add cases or conservatively fail for insufficient evidence; validation/frozen use the declared bootstrap count. R1 remains unchanged because it stopped before the duplicate stage. |
| R22 | proven and corrected prospectively | Hierarchical statistics stopped at the first non-exact higher-priority metric. With identical lexicographic wins and identical positive cost deltas, adding a sparse positive primary improvement could change a pass into uncertainty. The predeclared `measurement.effect_scale.metric` was ignored. | Lexicographic case W/L/T remains direction evidence; every objective is recorded; the predeclared effect metric now supplies practical effect and CI. Only explicitly problem-declared protected objectives may veto regression. R1 is not reinterpreted. |
| R23 | proven and corrected prospectively | Initial and expanded evenly-spaced selections were computed independently. In CVRP, modify screening 8 -> 12 dropped four initial cases, so expansion changed rather than enlarged evidence. | Expanded populations now contain the complete deterministic initial population plus predeclared new cases with unchanged stage seeds, and fail conservatively when no evidence can be added. |
| R24 | proven and corrected prospectively | Real H prompts accumulated complete per-pair history and repeated telemetry (Warehouse 11.3k -> 83.8k input tokens; CVRP 20.7k -> 100.2k), while Warehouse surface hypothesis guidance was absent. C exposed source hashes, owner/provenance/views and repeated edit rules. | Complete raw lineage remains durable; the provider receives a fixed V3 research view with recent current attempts detailed, older attempts structured, siblings brief, actionable problem evidence, complete current source, phase-correct guidance and a neutral problem-owned prior when prior campaigns contain relevant scientific evidence. Provider-visible self-proof metadata is removed without weakening source-content binding. |
| R25 | proven; retained replay complete | Warehouse prod-1.2 completed 24/24 formal stages and promoted a subcategory-aware DestroyRebuild candidate from v1 to v2. The independent fixed replay completed 12/12 fresh pairs at 4/0/0 cases, 12/0/0 pairs, `total_cost +15150 [8400,22000]`. | Classify production transfer as `RETAINED_PRODUCTION_IMPROVEMENT`. Warehouse acceptance is complete; do not require production multi-promotion. |
| R26 | proven organization defect; corrected prospectively at `8909f635`; causal effect on promotion unproven | The launch-time EXPLORE scheduler repeatedly served the oldest branch, yielding 16 H on one cumulative branch and one each on two schedulable siblings. Two independent Merge candidates had sparse no-loss 2/0/4 case evidence but could not reach declared expanded screening. A candidate-local traceback also hid its exception root cause from the next H. | Rotate EXPLORE siblings by persisted least-recently-served time, allow exactly one measurement expansion for a practical sparse no-loss initial signal without weakening the pass threshold, and project one typed Verification root cause. Do not add rollback, novelty, algorithm-quality or negative-result gates. |
| R27 | proven measurement/claim limit; claim-bounded prospectively, four-seed power unchanged | CVRP screening's declared practical delta is `2`, while the accepted A/A calibration reports `MDE@80%=9.9` and recommends eight seeds. The current four-seed design has greater power for large effects but cannot rule out smaller improvement. Historical CMT case-ID priority is also a population property, not a V3 research obligation. | Keep the first 8-stage Terra rung matched to the existing cases/seeds so context/runtime corrections are identifiable; explicitly limit negative claims below MDE. If evidence is power-limited, redesign a fresh pre-registered campaign. Never add seeds post hoc or turn case priorities into H obligations/gates. |
| R28 | proven valid partial science; terminal root sealed | CVRP open-research R1 completed 5/8 formal screenings and 176/176 valid pairs before an upstream stream closed without a terminal event. It exercised three branches, exact expansion, least-recently-served exploration and evidence-informed same-branch refinement; no candidate reached validation/frozen or promotion. | Classify the root as pre-registered `RUN_INVALID_INFRA` with `VALID_PARTIAL_SCIENCE_5_OF_8`. Never resume or retry it. Use its completed evidence only as input to a separately pre-registered fresh rung. |
| R29 | proven measurement design defect; prospective correction required | The current case estimator calls a case win only when seed wins strictly exceed both losses and ties. It maps sparse `2W/0L/2T` evidence to a case tie. R1's depth-one repair reproduced direction on expansion at 6/1/5 gate cases, median `+3.75 [0,11]`, but four seeds are underpowered relative to MDE `9.9`. A prospective paired-median reanalysis would be 7/2/3, win rate `0.583`, still below the fixed `0.60`; R1 is not a hidden pass. | Pre-register a scientifically interpretable paired case estimator and a claim-bounded staged fresh population before R2. Pair outcomes remain descriptive; initial mechanism evidence may only route to a larger exact quality screen, while promotion still requires the complete unchanged V3 Protocol authority path. Do not reinterpret R1 or tune an active root. |
| R30 | proven proposal-operation friction; prospective correction required | A complete structured branch-C refinement was rejected before Contract because its exact selector contained one blank line between top-level functions while visible source contained two. This was not an algorithm failure. | Permit only deterministic, globally unique blank-line-run selector normalization for non-`replace_all` edits, record the ordinary repair attribution, and keep every other mismatch fail-closed. Do not add fuzzy code matching, retry or an algorithm-quality gate. |
| R31 | proven evidence-accounting/context gaps; corrected prospectively | R1 contains five evaluated attempts, two candidate-local research rejections and one infrastructure block, but terminal status projects only one rejection. The neutral H prior also omits the recent deep-ejection negative and R1 depth-one/depth-two contrast. | The research-rejection finalizer now owns one typed outcome row plus cleanup/audit fact; the loop audit remains a cross-check rather than a second counting authority. Candidate-local rejection stays scheduler-forward, and one concise neutral evidence item reaches H without selecting an operator or entering Decision. |
| R32 | proven calibration-compatibility defect; corrected prospectively | The checked-in CVRP readiness and adapter projected the old 8-case x 4-seed pair-level MDE `9.9` as ready for R2, whose estimator, 12-case population, eight-seed quality screen and scale-aware runtime differ. A later 8-seed pair-level A/A reported MDE `9.6`, but it is also incompatible and does not validate its heuristic 16-seed recommendation. | Mark R2 uncalibrated, keep both MDE values as explicitly incompatible historical low-power diagnostics, and synchronize the declared matrix with actual execution. R2 may test research behavior and large effects but must not claim calibrated power or rule out effects near delta `2`. |
| R33 | active experimental-design risk; bounded prospectively | A no-promotion campaign can reflect the candidate ideas, the stage/case/seed measurement design, or an H/C context and tool surface that diverts attention from algorithm research. Adding more host rules cannot distinguish those causes and can itself suppress useful search. Effects measured on different stage populations also cannot be presented as one candidate trajectory without a shared estimand. | Treat each stage population, estimator, provider-visible context and available edit/research tool as an explicit experiment input. Declare the question and estimand for H, C, Verification, screening, validation, frozen and provider-free analysis separately; cross-stage effects on disjoint cases remain separate robustness evidence. Preserve only V3 Contract/Verification/Protocol authority and minimum ordinary scientific lineage. Analyze proposal focus, usable evidence, edit fidelity and measurement reach separately. If causal isolation is still needed, use a later fresh preregistered matched ablation rather than tuning an active root or adding a quality gate. |
| R34 | proven V3 exposure/context-burden defect; corrected at `41956f36` | The proposed R2 H prior exposed current-split validation case `tai150a`, seed-level deltas and frozen/validation summaries. C also received several overlapping source/interface/rules packets, one route-count statement contradicted the protected-objective semantics, and H was told to use an incompatible MDE. | Remove all validation/frozen detail from H, retain screening-level mechanism facts only, expose every current source file once, correct excess routes to `fleet_violation`, and keep one problem-owned object/API packet plus target-specific guidance. The result removes 94 net lines, adds no gate and passes the complete suite. |
| R35 | proven valid partial science; terminal root sealed | Corrected R2 completed 10 formal stages and 448/448 valid pairs before the final C stream ended upstream without a terminal event. Two schema-invalid H calls scheduled forward; no Contract/Verification candidate failed and no feasibility or fleet regression occurred. | Classify the root as pre-registered `RUN_INVALID_INFRA` with `VALID_PARTIAL_SCIENCE_10_OF_12`. Never resume or retry it. There was no validation, frozen stage or promotion; retain completed evidence only as neutral input to a fresh R3. |
| R36 | proven proposal-fidelity gap; observability corrected, expression cause open | R2 time-aware operator credit had a complete source-grounded H but C added only three unused constants. R3 later proposed the same multi-site causal mechanism from another complete H, while its schema-valid, provider-complete C added only an unused `segment_outcomes` list. The fresh prior did not say the R2 mechanism remained unimplemented, so intent could again be mistaken for executed algorithm evidence. | Keep mechanical finish/tool/argument facts trace-only and keep `proposal_intent` distinct from actual changed-symbol use sites. Add one neutral implementation-status fact after R3 terminal, without forcing that mechanism. The two independent scaffolding-only traces trigger one frozen-input C expression A/B scored on implementation fidelity, not solver W/L/T; they add no patch grader, retry or gate. |
| R37 | proven prospective measurement-design defect; implemented and null-checked | R2 elapsed-budget SA reached 6W/1L/5T cases, pair 49/20/27 and distance `+2.75 [0,11]`, but fixed `wins/all_cases >= 0.60` treats exact ties as breadth failures and therefore correctly returned unclear. The candidate is not a hidden pass. | R3 prospectively uses case net score `(W-L)/12 >= 0.25`, loss rate `L/12 <= 0.20`, median practical effect and CI low `>= 0` through quality/validation/frozen. Initial evidence can only request exact expansion. The pre-registered A/A/null check completed acceptably as limited false-pass evidence; it is not an MDE/power claim and never reinterprets R1/R2. |
| R38 | proven context-framing burden; lossless correction complete at `6d5be022` | R2 H grew from 21,124 to 45,373 input tokens; final visible context was 219,048 chars, with source 42.2% and history 51.5%. C remained stable near 22k tokens and its 11-file source was useful. | Deterministic compact canonical JSON reduces the stored final H rendering by 63,094 chars (28.8%) without dropping a field. Keep complete current source, existing last-three/older-compact history semantics and validation/frozen non-exposure; measure actual R3 tokens before any further context change. |
| R39 | proven descriptive-schema friction; corrected at `6d5be022` | Two of 11 R2 H calls contained a complete mechanism and every other required field but omitted only `expected_effect`. They consumed 45,528 tokens, 9.0% of all provider input, and produced no solver experiment. | Keep `expected_effect` as optional tainted lineage text with an empty deterministic default. It is not inferred, scored or read by Decision. The mechanism, target weakness, change locus/action and target file remain required. |
| R40 | proven experimental-population risk; outcome-blind R3 assets frozen at `6d5be022` | Earlier formal blocks were X-heavy, validation/frozen used fewer seeds than quality, and a short 12-stage horizon could censor a late candidate before quality -> validation -> frozen drained. | Freeze three mutually exclusive 12-case quality/validation/frozen blocks with exact size/headroom balance, 4->8/8/8 disjoint seeds, dimension-only 30/45/60/90/120-second budgets and a 16-stage horizon. Freeze a fourth disjoint 12x8 final B0 replay before launch and keep it out of proposal/search context. |
| R41 | proven fresh-context omission; corrected at `76f3e976` | A fresh R3 campaign does not inherit R2's database, while the fixed problem prior still stopped at R1 and described only R2's missing MDE. Terra would not see the strongest elapsed-budget SA result or its deadline-model residuals. | Add one neutral problem-owned R2 aggregate prior with 6W/1L/5T cases, 49W/20L/27T pairs, `+2.75 [0,11]` and source-grounded residuals. Keep it non-prescriptive and holdout-free. Describe the completed same-seed A/A only as limited false-pass evidence, keep `screening_mde_at_power_80=None` and leave `calibration_ref` empty. No new gate or tool is added. |
| R42 | proven experimental-attribution limit; prospective diagnosis only | CVRP quality expansion changes case count and seed count together (`8x4 -> 12x8`), so a stage flip cannot identify the seed, case or interaction cause. Quality, validation and frozen are exactly 3 non-X `<=100` / 3 non-X `101-200` / 1 X `101-200` / 5 X `>200`; final replay is 4/1/1/6. No non-X-large or X-small support exists, so only the shared-mid cell supports a family direction, within-family size directions are partial and the full interaction is unidentifiable. Warehouse uses action-dependent case counts, two-seed majority in production and one 30-second budget across very different sizes. | Keep R3 sealed and do not reinterpret its partial validation. Separate its infrastructure outcome from a provider-free atomic case-by-seed and budget diagnosis on the chronological frozen cohort. If a fresh CVRP campaign is needed, use a predeclared four-cell connecting quality population with equal non-X `<=100`, non-X `101-200`, X `101-200` and X `>200` counts; infer only fixed stratum directions and common-mid family support. A causal within-family size claim requires shared benchmark families across sizes. Reanalyse accepted Warehouse evidence with frozen strata. Every diagnosis remains excluded from Decision and each new campaign changes one experimental axis at a time. |
| R43 | proven operator-side experiment contamination; conditional recovery now inapplicable | Pytest ran concurrently with the deadline-driven R3 quality expansion on a two-vCPU/one-physical-core host. Exact overlap cannot be reconstructed for every invocation, so excluding only selected pairs would be false precision. | The formal chain remains `OPERATOR_LOAD_CONTAMINATED_FOR_STRICT_PROMOTION_CLAIM` and no selected pair is deleted or retried. The later reboot left no Protocol promotion, so the conditional [recovery preregistration](docs/experiments/v0.4/v0.4-cvrp-v3-r3-operator-load-recovery-preregistration-20260809.md) has no eligible candidate and is not launched. Proceed to R45 and the R42 diagnosis; add no Scion gate. |
| R44 | proven recurring active-fixed-source Protocol routing deviation; correction narrowed prospectively | Candidate three's initial 32-pair result was 3W/0L/5T cases, median `0 [0,1.5]`; candidate five later completed 32/32 at 6W/1L/25T pairs and 2W/0L/6T cases, effects `[1,0,0,0,0,0,1,0]`, median `0 [0,1]`, with no failure or fleet regression. In both, CI high was below practical delta `2`, so none of the three pre-registered expansion routes applied, but exact runtime `76f3e976` used the old generic uncertainty fallback. Candidate three's extra 96-pair stage ended at 34W/11L/51T pairs and 6W/0L/6T cases, `+1 [0,2.25]`. Candidate five's scaffolding-only extra stage completed 3W/13L/80T pairs and 0W/1L/11T cases, median `0 [0,0]`, and correctly failed case quality once already expanded. | Do not reinterpret, retry, stop or delete either extra R3 stage; retain them as exploratory evidence under R43. The first prospective patch blocked the generic expansion but overclassified ineligible evidence as a hard fail. The narrowed route returns `unclear / SCREENING_INITIAL_QUALITY_CI_INSUFFICIENT_FOR_EXPANSION -> continue_explore`, without expansion, promotion or a new candidate veto. Formal #7 can characterize only the executed unused scaffold, not the unimplemented time-aware-credit mechanism. |
| R45 | proven measurement replay and order-attribution gap; minimal seam complete at `c32f5b8a` | Formal pairs ran in fixed champion-then-candidate order, champion result caching was enabled by default, cumulative expansion reran old cells, and raw pairs retained deltas/cache/runtime but not both absolute objective vectors, execution order or feasibility. This does not reinterpret accepted Warehouse results or R3's completed evidence, but makes objective headroom, order/load effects and atomic case-versus-seed attribution partly `UNIDENTIFIABLE`. | The default-off diagnosis path now runs both subjects fresh, deterministically counterbalances AB/BA and records only the bounded raw comparison facts. The four production files grew by net 100 lines and 46 focused/adjacent tests plus independent review passed. Default Protocol and Decision behavior remain unchanged; the experiment side owns atomic blocks and adds no runner, ledger or gate. |
| R46 | proven scoped R3 signal; broad advancement correctly withheld | Candidate four's initial elapsed-deadline SA refinement expanded from 4W/0L/4T cases. Its exact 12x8 quality result completed 96/96 pairs at 32W/12L/52T and 5W/0L/7T cases, with median `0 [0,3.25]`, no fleet/execution failure and `continue_explore`. Non-X cases were 5W/0L/1T with subgroup median `+3.25`; all six X cases tied. Every case above dimension 200 was X, so family and size effects are confounded. | Retain `SCOPED_SIGNAL_ONLY / UNIDENTIFIABLE_FAMILY_VS_SIZE` as exploratory science under R43. The fixed broad Protocol correctly withheld validation because median `0 < 2`; do not tune it or reinterpret the candidate as a pass. Let subsequent H use the screening evidence, and use the provider-free family/size/budget diagnosis before deciding whether a separately preregistered scoped campaign is justified. |
| R47 | proven exact-candidate quality advance; validation infrastructure-interrupted | The source-grounded whole-route/partial-route removal candidate expanded on the same exact source to 96/96 valid quality pairs: 37W/16L/43T pairs, 7W/0L/5T cases, case medians `[7.5,25.5,3,14,5,0,0,0,4,4.5,0,0]`, overall `+3.5 [0,6.25]`, net score `0.583`, zero case losses, failures, fleet or protected-objective regressions. Two independent raw recomputations matched. All five predeclared quality components passed, and actual and expected routing were both `SCREENING_PASS -> queue_validate`. The host then rebooted with validation at 52 attempted and 51 completed/valid pairs; durable Protocol counts remained 10 screening, zero validation and zero frozen, champion v1. | Seal R3 as `RUN_INVALID_INFRA / VALID_PARTIAL_SCIENCE`. Retain the terminal quality result, but do not read or adjudicate the partial validation, resume/retry the root or call the reboot an algorithm negative. No Protocol promotion means no clean-recovery candidate; proceed to R45 and the ordinary-lineage factor/budget diagnosis. |
| R48 | proven R45 diagnosis R1 infrastructure invalidity; zero accepted science | The R1 process disappeared during its first `MDE` block. Terminal structure is `complete=false`, zero of 37 accepted blocks, `last=null`, one partial 46/96 raw file with zero recorded subject failures, no analysis artifact, and no remaining driver or solver process. No W/L/T, effect, gate or objective was read. The disappearance cause is `PROCESS_DISAPPEARANCE_CAUSE_UNIDENTIFIABLE`. | Seal R1 `RUN_INVALID_INFRA / ZERO_ACCEPTED_BLOCKS / NO_ADMISSIBLE_ANALYSIS`; do not resume, modify or reuse any partial pair. R2 changes only the ordinary-user launch/process-observation seam, starts fresh at MDE 0/96, and is separately preregistered. If R2 is interrupted, seal it and do not launch an automatic R3. |
| R49 | proven experiment-driver overgate; R2 sealed with zero accepted blocks | R2's first MDE raw completed 96/96 attempted and valid pairs with zero candidate/champion/total failures, then the one-off driver exited `2` before atomic acceptance because all 192 valid A/B objective mappings contained the CVRP diagnostic field `routes` in addition to the two declared metrics. Every other structural predicate passed; no analysis exists and no W/L/T, effect, gate, ranking or objective value was read. | Seal R2 `RUN_INVALID_EXPERIMENT_DRIVER / ZERO_ACCEPTED_BLOCKS / NO_ADMISSIBLE_ANALYSIS`. In a fresh R3 bundle, require the declared metrics as a finite numeric subset, retain exact declared deltas and every real execution/completeness check, and remove only the false exact-key-set gate. Do not reuse R2 pairs or change Scion core. R3 requires separate preregistration and explicit launch confirmation. |
| R50 | proven complete provider-free diagnosis; no broad immediate-base advance | R3 completed with exit `0`, 37/37 atomic blocks and 1,056/1,056 unique fresh AB/BA pairs. Independent B0 A/A gives `MDE@80%=2.0` only for the frozen `12x8`, `1x`, homogeneous-additive estimand. Full `12x8` candidate median signs are 0 positive / 5 zero / 1 negative. Candidate five is uniformly harmful; candidate four did not implement its claimed time-aware-credit mechanism; the elapsed-budget-SA-related sources retain only descriptive scoped/`2x` opportunity. Added-case and joint contrasts never improve a candidate median. Interaction and whole-budget-arm machine drift remain `UNIDENTIFIABLE`. | Seal R3 `VALID_COMPLETE_PROVIDER_FREE_DIAGNOSIS / DESCRIPTIVE_COHORT_ONLY / NO_BROAD_IMMEDIATE_BASE_ADVANCE`. The exact-roster sensitivity and budget diagnoses are complete, but they do not promote, recover, rank or reinterpret an R3 candidate. Treat implementation fidelity, cross-case generalization and search opportunity as CVRP research questions; add no deployment, Trust/Hash, identity, ledger, recorder or candidate gate. |
| R51 | proven strict-diff expression negative; exact retained | The frozen matched C-expression A/B completed exit `0` with 8/8 terminal provider cells, no provider failure and no solver call. All four exact cells normalized, applied and passed Contract; all four diff cells had hunk-position/context mismatches and correctly failed the frozen no-offset/no-fuzzy application with fixed `0/0` scores. Two blind reviewers agreed on exact scores (`2/2`, `1/1`, `1/1`, `1/1`), totaling H=`5` and source-anchor=`5` versus diff `0/0`. | Classify `VALID_COMPLETE_C_EXPRESSION_DIAGNOSTIC / STRICT_DIFF_NOT_ADOPTED / EXACT_RETAINED`: all four adoption conditions fail. Do not retry, relax the parser, add a patch grader/gate or change production. This diagnoses only proposal expression, not solver quality; continue net-deletion context/source simplification before a short real CVRP research block. |
| R52 | proven research-hot-path subtraction; independently reviewed | Nine production files changed by `+273/-551`, net `-278`: the source ledger and its owner/provenance/view/self-proof machinery are gone. One ordinary `editable_source_context` now supplies approved target, unique canonical path/content values and consolidated target API guidance; H sees the research core and C sees exactly approved H plus that source context, while the complete raw context remains in trace. | Close source-context and provider-projection cleanup. Keep branch-current history/workspace source precedence over champion, touched-missing no-fallback semantics, `None` versus empty content and exact selector content binding. Add no replacement ledger, Trust/Hash authority, gate or provider tool loop. Main focused tests passed 169 and the independent expanded set passed 207; CVRP direct outer passed once in 32.70s. Warehouse outer traversed the full V3 chain but failed only at an unrelated dirty V8 `typed_telemetry_summary` assertion, so it is not claimed as passing. |
| R53 | proven complete one-step V3 algorithm experiment; negative exact screen | The clean `e4b6b98d` minute run completed exit `0` with exactly one Terra H, one approved-H-bound C, one canary and one four-pair SCREENING call. The only semantic candidate change set `EMBEDDED_VNS_MAX_RUNTIME_SHARE` from `0.0` to `0.35`. All pairs were fresh, successful and feasible; independent recomputation is `0W/1L/3T`, effects `[-16,0,0,0]`, median `0 [-16,0]`, with no fleet regression. Telemetry is consistent with a real allocation shift—ALNS iterations `44 -> 151`, ALNS-core share `0.195208 -> 0.382246`, embedded-VNS share `0.419914 -> 0.287778`—but best updates fell `7 -> 4` and final quality did not improve. | Seal `VALID_COMPLETED_ONE_STEP_SCREEN / SCREENING_FAIL_CASE_QUALITY / NO_PROMOTION`. Keep the telemetry `association_only`; do not validate, freeze, promote, resume or retry this root. Retain the result only as neutral research evidence. It proves that the simplified V3 chain can complete one analyzable algorithm step, not that Scion has achieved CVRP improvement or continuous optimization. Add no gate, ledger, Trust/Hash or telemetry requirement. |
| R54 | proven feedback uptake plus candidate/runtime and framework persistence defects | The clean fresh-B0 feedback-conditioned step used exactly one Terra H/C sequence. H explicitly converted R53's “more iterations, fewer best updates” negative into an elapsed-budget-SA hypothesis. C implemented the core elapsed-fraction mechanism but deleted `_SimulatedAnnealing.cool` while leaving three calls in repair-error, infeasible and route-limit paths. Contract and nine recorded Verification checks passed, but unit/regression checks were skipped and the controlled smoke missed those branches. Formal raw completed 4/4 attempts: E101/X120/X233 are three valid ties; P65 has a typed candidate `solver_algorithm_runtime_error` and its emitted objective is inadmissible for delta/W/L/T. Decision durably recorded `abandon / CANDIDATE_RUNTIME_FAILURE`. Afterward, canonical screening-context persistence rejected the three-item valid feedback against `valid=3 + candidate_failed=1`, raising `ValueError` and causing wrapper exit `1`. | Seal `VALID_TERMINAL_CANDIDATE_RUNTIME_FAILURE / DECISION_ABANDON / FRAMEWORK_POST_DECISION_CONTEXT_PERSISTENCE_ERROR / NO_PROMOTION`. Keep candidate failure, Decision, and later framework error as separate facts. Do not reinterpret the three valid ties as a four-case result, use the P objective, retry/resume the root, validate/freeze/promote the candidate, or add a candidate-quality gate. The report preregisters no successor. |
| R55 | proven narrow persistence and CVRP Verification coverage correction | Commit `3221416c` permits feedback cardinality from the exact valid-pair count through valid plus candidate-failed pairs while retaining exact observed W/L/T accounting. Commit `9aedfb64` makes CVRP V3/V4 execute subsecond problem-owned operator-recovery and public-entrypoint tests. A provider-free materialization of the exact R54 patch fails the repair-error, infeasible and route-limit fixtures; the ordinary focused/adjacent suite passes 25 tests on B0. | Retain these tests as mechanism-agnostic runtime-consistency coverage only. They add no quality, novelty, promotion or research-direction gate. No provider call or Protocol/formal experiment was rerun; only provider-free unit/smoke verification ran. No successor H/C is preregistered, launched or authorized by this correction. |
| R56 | proven clean early rejection plus repeated C multi-site expression defect | The clean `acdc80ba` step completed wrapper exit `0` with exactly one Terra H/C and passing Contract. H explicitly required elapsed-budget updates on every recovery path and no stale cooling API. C preserved the mechanism but an indentation-specific `replace_all` matched only one of five `annealing.cool()` calls after removing the method, leaving four residual calls. V3 executed in 519 ms and all three recovery fixtures failed with `AttributeError`; the fourth ordinary-path call remained latent. V4 and later checks, canary, formal Protocol and Decision were not reached; B0/v1 remained champion. | Seal `VALID_TERMINAL_RESEARCH_PROCESS_OBSERVATION / VERIFICATION_LIGHT_REJECTED / ZERO_PROTOCOL_EVIDENCE / NO_DECISION / NO_PROMOTION`. Draw no algorithm-quality conclusion and do not repair/retry the root. Treat this as evidence for minimal provider-free C expression/tool redesign, not another rule or candidate gate. No successor H/C experiment is preregistered, authorized or launched. |
| R57 | proven provider-free C expression correction; no algorithm experiment | Commit `f537fed5` adds optional source-bound `exact_line_replace`: it matches a complete logical line independent of its outer indentation and replays replacement indentation under each exact match. A counterfactual re-expression of the frozen R56 C response matched all five `annealing.cool()` callsites through the production parse -> Contract -> materialize path; non-skipped V3 and V4 passed. The combined regression passed 183 tests, and independent review passed focused 38 plus adjacent 92 tests. | Retain this only as expression-fidelity and regression evidence. It adds no provider source-search/tool loop, retry, quality gate or Decision input. It is not an R56 repair/retry, a new R56 result or solver-quality evidence: no provider, canary, formal Protocol or Decision call ran. R57 itself did not preregister, authorize or launch a successor H/C experiment. |
| R58 | proven clean early rejection plus unresolved C expression-selection defect | The clean `42535efc` run completed wrapper exit `0` with one terminal valid Terra H/C, retry/repair zero and passing Contract. H again selected elapsed-budget SA. C received all 11 editable files and the optional `exact_line_replace` form, but emitted six uniquely matching `exact_replace` edits and no line-oriented edit. It removed two of five `annealing.cool()` calls while deleting the method, leaving three 16-space recovery-path calls. V3 rejected all three fixtures in 568 ms; V4, canary, formal Protocol and Decision were not reached. | Seal `VALID_TERMINAL_RESEARCH_PROCESS_OBSERVATION / VERIFICATION_LIGHT_REJECTED / ZERO_PROTOCOL_EVIDENCE / NO_DECISION / NO_PROMOTION`. Seed-29 W/L/T, effect, CI and fleet comparison are undefined; draw no algorithm-quality conclusion. Pause provider algorithm experiments and redesign/test C expression selection provider-free, without a source-navigation loop, retry/repair call, patch grader, algorithm rule or quality gate. Do not launch an R59 provider experiment, long or WSL work. |
| R59 | proven provider-free typed-tool presentation correction; no algorithm experiment | Commit `47fe81ee` uses one flat root/nested schema factory, dispatches explicit intents through four singleton-intent branches, preserves legacy missing intent and `replace_all=false`, and presents exact-span and indentation-neutral exact-line choices neutrally with one shape-only example. A mocked OpenAI request's actual `tools[0]` matches the tracked payload snapshot. Frozen R56/R58 replay retains the R58 original's three residual calls; its line re-expression matches all five and passes V3/V4. Scoped tests passed 170 and independent review passed 68. | Retain this only as tool-presentation, transport and expression-fidelity evidence. It adds no provider source-navigation loop, retry/repair call, patch grader, algorithm rule, quality gate or Decision input. No provider, canary, formal Protocol or Decision call ran, so there is no algorithm evidence. R60 later tested the complete presentation separately and is recorded below. |
| R60 | proven complete single matched-pair tool-presentation observation; no identified advantage or algorithm evidence | The fixed OLD `42535efc` then NEW `47fe81ee` C-only pair completed exit `0` with 2/2 terminal provider responses and 2/2 opaque primary records before reveal. Both arms passed parse, source binding, Contract, materialization and non-skipped V3/V4 (`full_executable=true`). Both chose one unindented five-match line replacement with zero residual `annealing.cool()` calls. OLD emitted six other exact edits; NEW emitted three and had one no-op dropped. | Seal `TERMINAL_MATCHED_PAIR_OBSERVATION / BOTH / BOTH_LINE_SELECTION / NO_IDENTIFIED_PRESENTATION_ADVANTAGE / ZERO_ALGORITHM_QUALITY_EVIDENCE`. Because one OLD-then-NEW pair confounds presentation with order, time and model stochasticity, claim no population rate, p-value or R59 causal benefit. Post-hoc OLD duplicate weight recording and NEW inactive deadline setter keep both out of algorithm testing. At R60 closeout, provider pause remained and no R61 had been preregistered, authorized or launched. |
| R61 | proven provider-free scheduler semantics; separate crossed endpoints only | Fresh subprocesses copied the sealed R60 workspaces and drove exactly one fake ordinary worsening-candidate iteration at progress `0.1` and `0.9`. OLD called `set_progress` before accept and cooled `2.6857958838184386 -> 0.018616455666360693`, but dynamically recorded destroy/repair weights `2/1`. NEW defines `set_deadline_progress` but called no setter and remained `5.0 -> 5.0`, while dynamically recording `1/1`. | Seal `TERMINAL_DIAGNOSTIC / SEPARATE_ENDPOINT_TRADEOFF / ZERO_ALGORITHM_QUALITY_EVIDENCE`. Keep `deadline_wiring_pass` and `ordinary_weight_accounting_pass` separate with `aggregate_algorithm_success=null`. The fake state and controlled clock prove only scheduler control flow; provider/canary/formal/quality/benchmark calls are zero. Do not rewrite R60, rank candidates, infer quality/generalization or enter Protocol/Decision. Provider pause remains; no R62 is preregistered, authorized or launched. |
| R62 | proven provider-free static sidecar calibration; separate syntax signals only | Frozen fresh-B0, the sealed R60 workspaces and in-memory controls calibrate same-name direct Attribute Call and changed-span adjacent identical call signals. Alpha is `TRUE/FALSE`; beta `FALSE/TRUE`; B0 `UNKNOWN/UNKNOWN`; cleaned alpha/beta `TRUE/TRUE`; branch `UNKNOWN/TRUE`; callback `UNKNOWN/FALSE`. | Seal `TERMINAL_CALIBRATION / SEPARATE_SYNTAX_RISK_SIGNALS / ZERO_ALGORITHM_QUALITY_EVIDENCE`. Keep receiver resolution and callee effects explicitly unknown, both diagnostics separate and both aggregate fields null. This is post-hoc R60-informed calibration, not C completeness, candidate correctness, a gate, prompt change or repair loop. Provider/Contract/V3/V4/Protocol/Decision/quality/benchmark calls and production/R60/R61 changes are zero. At R62 closeout, provider pause remained and no R63 was preregistered, authorized or launched. |
| R63 | proven complete single C-message pair; no identified message-review advantage or algorithm evidence | The authorized fixed CONTROL→REVIEW pair completed exit `0` in about 55 seconds with H/retry zero, two terminal C outcomes, two opaque primary records and two opaque sidecars. All 13 primary fields are true in both arms (`BOTH`). Both proposals use one-file `_two_opt_star` exact replacement with nearly the same boundary-delta semantics; REVIEW differs only in depot-assignment placement/format and has 51 more input tokens. Sidecars are `UNKNOWN/TRUE` for both, aggregate null. | Seal `TERMINAL_MATCHED_PAIR_OBSERVATION / BOTH / NO_IDENTIFIED_MESSAGE_REVIEW_ADVANTAGE / ZERO_ALGORITHM_QUALITY_EVIDENCE`. V3/V4 do not enter `_two_opt_star`: V3 disables embedded VNS; V4 passes `0.01` seconds, but `_algorithm_time_limit` clamps the scheduler time limit to `0.05` seconds, equal to its minimum `0.05`-second reserve, so strict `remaining_time() > reserve` is not met. Claim neither review benefit nor ineffectiveness from one confounded ordered pair; the seal does not mean the suffix was ineffective or the model did not review. Run no canary, formal Protocol, quality solver, Decision or promotion. At R63 closeout, no R64 was preregistered, authorized or launched. |
| R64 | terminal complete provider-free `_two_opt_star` semantic diagnostic; durable calibrated reproduction only | The unique formal root was created at `2026-08-14T09:41:56Z` and contains only mode-`0600` `result.json`/`status.json` under a mode-`0700` root. Both arms report cut/near/state `TRUE/TRUE/TRUE` and descriptive route-distance calls `0`. All 27 cut and three near-EPS cases equal their references without exception. State candidate/reference accepted-move counts are `0/0`, `1/1`, and `5/5`; complete traces/final partition/load/cost states equal the reference and all invariants hold. | `TERMINAL_DIAGNOSTIC`, `complete=true`, `semantic_endpoints_claimed=true`; classification and both aggregates are null. Formal role `DURABLE_REPRODUCTION_OF_EXACT_CANDIDATE_CALIBRATED_PROVIDER_FREE_DIAGNOSTIC`, with `outcome_blind=false` and `independent_confirmation=false`. Nested `preparation_calibration.formal_output_created=false` describes only the earlier temporary calibration, not current root absence. This finite-fixture result is non-gating, zero algorithm-quality evidence, and no independent confirmation. Provider/Contract/V3/V4/canary/formal Protocol/quality/Decision/mutation counters are zero; provider pause remains and no R65 is authorized. |
| R65 | terminal complete exposed-coordinate minute calibration; no signal | The exact authorized B0→alpha canary and four seed-73 AB/BA/AB/BA pairs completed all 10 fresh subprocesses and 98 declared subject-seconds. Canary subjects both succeeded feasibly with runtime-audit validity, distance 20 and fleet violation zero. P65/E101/X120/X233 are exact B0/alpha ties at 798/1124/14250/20112; all eight screen subjects are successful, feasible, runtime-audit valid and fleet-safe. | Seal `VALID_COMPLETE_EXPOSED_COORDINATE_MINUTE_CALIBRATION / EXPLORATORY_SCREEN_NO_SIGNAL / ORDINARY_MINUTE_RULE_NOT_MET / NO_GO_EFFECT_INFERENCE / NO_MORE_PROVIDER_FREE / NO_R66`. Pair/case result is `0W/0L/4T`, all deltas zero, median `0 [0,0]`, protected regressions zero. Only CI-low, loss-rate and fleet criteria pass; win-rate, practical median and net-score criteria fail. Decision/promotion are null; provider/H/C/Contract/V3/V4/validation/frozen/Decision/promotion/beta/R66 are zero. Do not infer an effect, pool R1, extend the screen or launch R66. |
| R66 | original `PREP_INVALID`; recovery1 terminal local-infra failure before HTTP; recovery2 awaiting explicit authorization | Original stopped on the frozen `64` versus wall-clock `65` date drift with zero calls. Recovery1 fixed `as_of`, acquired, then emitted `TERMINAL_HYPOTHESIS_PROVIDER_FAILURE`, logical H attempt/call `1/1`, no terminal response and `No module named 'jiter'`. Audit classifies `RUN_INVALID_LOCAL_INFRA / MISSING_JITER_BEFORE_REQUEST`: actual outbound model requests, research-payload sends and H observations are zero. | Keep emitted and causal classifications separate; all downstream/R67 counters are zero and no algorithm/model claim follows. Recovery2 vendors exact `jiter==0.13.0` provider-free under a fresh identity and has a green 47-test preparation receipt, but is `RECOVERY2_PREPARED_AWAITING_EXPLICIT_AUTHORIZATION`. Do not launch it on prior instructions; a new exact authorization is mandatory. |

## Modular execution plan

### S0 - Preserve and pre-register

- [x] Commit the completed lightweight V3 runtime as `4d637959`.
- [x] Fast-forward `v0.4-dev` to that commit while preserving unrelated user
  worktree changes and the named overlap stash.
- [x] Create `codex/v04-solver-improvement-research`.
- [x] Independently review v0.3 Warehouse promotions, current Warehouse
  blockers, and historical/current CVRP evidence.
- [x] Record exact experiment inputs, campaign root, model
  (`gpt-5.6-terra`), local Codex proxy, case/seed manifests, time limits and
  stop conditions before every new run. S1 and the first S4 campaign have
  committed preregistrations; repeat/new-problem runs must do the same.
- [x] Replace the legacy postrun bundle/receipt/formal-index handoff with one
  thin read-only V3 analysis guide over ordinary DB events, H/C traces,
  source/workspaces, Verification, raw metrics, Protocol, Safe Features and the
  recorded Decision. Missing exact candidate composition is
  `UNIDENTIFIABLE`; analysis never restores a recorder or rejudges Decision.

### S1 - Finish the truncated Warehouse candidate

- [x] Materialize the exact Warehouse 3R round-3 MergeVehicles candidate and
  its exact v1 champion without another provider call.
- [x] Run the queued expanded screening population. If Protocol passes, drain
  validation and frozen with the same source; otherwise stop that candidate.
- [x] Classify the result as `TRUNCATED_QUEUE_CONFIRMED` or
  `SCIENTIFIC_NEGATIVE`. This diagnostic does not by itself prove continuous
  agent research. Result: `SCIENTIFIC_NEGATIVE`; screening passed 8W/0L/6T,
  but validation had 11/15 candidate timeouts, 0 champion failures and stopped
  before frozen.

### S2 - Restore the small V3 research semantics

- [x] Change screening-fail disposition from clean-parent rejection to a
  provisional verified branch head, while leaving champion, Protocol and
  promotion state unchanged.
- [x] Restore V3 branch depth/breadth semantics without forced diversity: up
  to three active branches, FIFO/state priority, one natural direction per
  branch, complete branch evidence, and exact branch-current source.
- [x] Set branch direction from its first retained verified H and expose it as
  context; do not add a mechanism classifier or same-mechanism gate.
- [x] Add concise Warehouse solver mechanics and safe aggregate objective
  headroom/noise facts to proposal-only problem context.
- [x] Add a concise CVRP cross-campaign research prior and explicit request for
  the smallest causal implementation that preserves unrelated code. A later
  end-to-end audit found that the prior did not reach the active provider H;
  S5 owns that delivery correction. The prior must not select surface, action,
  target or Decision.
- [x] Add no framework mechanism counter or gate in this stage. If a later
  measured attribution question justifies a minimal counter, keep it
  problem-owned, observational and absent from Contract, Safe Features and
  Decision.
- [x] Delete or quarantine the remaining dead problem-specific algorithm-shape
  Contract checks encountered on this path; behavior belongs in Verification
  or Protocol.
- [x] Remove formal-candidate identity manifests, source-owner attribution,
  duplicate digests and replay-closure recording from the active campaign.
  The active lineage now records ordinary campaign/branch/H references, one
  exact branch-source equality value, stage inputs, metrics, verification and
  Protocol/Decision facts. Historical candidate evaluation may use only a
  local safe-path compatibility reader for cumulative full-file replacements;
  that reader is not an active writer or authority.
- [x] Reduce provider context to one frozen, validated value boundary with
  ordinary value/prompt equality. Remove active prompt manifests, context and
  snapshot identities, prompt hashes and receipt authority; trace and H/C call
  journal persistence are best-effort diagnostics and cannot discard a valid
  provider result. Keep the H-to-C approved-hypothesis binding.
- [x] Remove active promotion dossiers, registry hashes, summary closure and
  formal-readiness projection. Champion persistence and ordinary promotion
  lineage remain, but observer/report writes no longer form a second promotion
  gate. Remove the validation/frozen verification audit hash while retaining
  required branch code equality and clean-state checks.

### S3 - Focused implementation verification

- [x] Test the disposition truth table, branch source reuse, clean fallback
  after Verification failure, exact stage reuse and three-branch scheduling.
- [x] Test the intended Warehouse mechanics/headroom and CVRP guidance
  projection at its component boundary and keep it absent from
  DecisionFeatures. A later active-provider-context audit found the CVRP prior
  missing from the actual H payload; this is R19, not accepted end-to-end
  delivery.
- [x] Test that no removed host algorithm-shape check blocks a valid
  executable candidate.
- [x] Run focused Contract, proposal, workspace, Verification, Protocol,
  Decision and campaign tests; run focused lint and diff-check changed files.
  The focused V3 integration set passed 270 tests; after the active lineage
  simplification, the evidence/proposal/composition set passed 58 tests and
  the campaign/preflight integration set passed 43 tests. Critical
  Ruff `E9/F63/F7/F82` and changed-file diff checks passed. These focused
  results do not replace the S6 full-suite run. The combined prompt, Decision,
  promotion, summary, Warehouse/CVRP smoke and fixed-replay regression set then
  passed 180 tests after the final hot-path subtraction. The stable pre-S1
  checkpoint then passed the complete suite: `1949 passed, 1 skipped` in
  628.19 seconds. At that checkpoint, S6 remained open because the final
  solver-evidence state still required its own post-experiment regression run.
  After the R6 proposal-rejection correction, the complete suite passed
  `1965 passed, 1 skipped` in 629.99 seconds; the focused adjacent set passed 92
  tests and critical Ruff plus diff checks passed. The latest post-heldout
  complete suite then completed with `1988 passed, 1 skipped` in 627.26 seconds.
  This is a historical post-heldout checkpoint; the later exact clean-source
  `2081 passed, 1 skipped` result recorded under S5 is the latest completed
  full-suite checkpoint before the currently active experiment work.

### S4 - Warehouse recovery ladder

- [x] Classify the first three launch attempts without rewriting their evidence:
  R1 failed pre-campaign on the synthetic data root; R2 stopped before an H on
  proxy authentication; R3 was scientifically valid but incomplete at 6/36.
  R3 generated three H/C pairs, completed 106/106 pairs, and promoted the
  `move_order.py` candidate from v1 to v2 after screening, validation and
  frozen. It proves one real promotion, not continuous optimization.
- [x] Correct the R3 post-promotion lifecycle defect without changing
  Protocol, Decision, Scheduler priority, thresholds or gates. Commit
  `88c1bc2b` retires a patchless stale branch as non-research housekeeping and
  removes `attempt_disposition` as a scheduling authority. The post-fix suite
  passed `1964 passed, 1 skipped` in 620.83 seconds.
- [x] Exclude R4 as operator-side launch infrastructure only: one unauthenticated
  H request, zero evaluated stages and zero experiments. Do not reuse its root;
  R5 preserves every scientific input and changes only credential extraction.
- [x] Exclude R5 as an intermittent upstream stream termination: authentication
  and H succeeded, but C had no terminal event, leaving zero evaluated stages
  and zero experiments. Seal its partial stream; R6 is a new matched H/C line.
- [x] Record R6 as valid partial science and an incomplete framework run. It
  completed 17/36 formal stages, promoted one candidate through screening,
  validation and frozen to champion v2, then completed fourteen further
  screenings across three v2-based branches. It did not reach v3. Its final
  provider-complete C failed exact source-bound normalization and was wrongly
  made invocation-terminal.
- [x] Correct the R6 proposal-failure route without relaxing source binding,
  Contract, Verification, Protocol, Decision, thresholds or Scheduler. A
  malformed/schema-invalid terminal H/C or unapplicable typed edit now rejects
  that H/C and schedules a fresh H from the clean base; it does not retry the
  old call or install an execution hold. True local/provider/infra/resource/
  interruption failures remain fail-closed.
- [x] Exclude R7 as a complete continuity result while retaining its bounded
  partial science. It completed 62/62 pairs across three screening stages and
  one validation stage; one candidate failed expanded screening and one passed
  screening then failed validation. The third C had no terminal provider
  response, so the run correctly stopped `BLOCKED_INFRA` at 4/36 with no
  promotion.
- [x] Run a fresh uninterrupted Terra synthetic Warehouse campaign with a
  pre-registered 36 formal-stage horizon. Do not split it into fresh roots when
  a candidate is queued for expansion/validation/frozen. This horizon covers
  the historical round-19 second-promotion tail; a 12-stage run is diagnostic
  only and cannot establish continuous promotion. R8 completed `36/36`,
  promoted `v1 -> v2 -> v3`, and preserved exact candidates across both
  validation/frozen funnels.
- [x] If the first campaign does not reach v3, run at most two matched repeats
  before changing framework or problem context. Report first-promotion round,
  promotion funnel, branch depth and exact failure class. R8 was the second and
  final matched repeat and reached v3, so no further matched Warehouse root is
  authorized before the independent replay.
- [x] Independently replay every promoted champion against its immediate parent
  and replay the final champion against v1 on declared held-out evidence. All
  three comparisons completed 36/36 valid pairs with both canary sides passing
  and zero candidate/champion failures or cached champion runtimes. Results:
  v2-v1 case 11/1/0, pair 32/4/0, median `+8`, CI `[4, 23.5]`; v3-v2 case
  12/0/0, pair 35/1/0, median `+39`, CI `[15, 48]`; v3-v1 case 12/0/0, pair
  36/0/0, median `+48.5`, CI `[40, 65]`. Classification:
  `CONTINUOUS_OPTIMIZATION_CONFIRMED`. See the
  [preregistration](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-r8-heldout-replay-preregistration-20260808.md)
  and [postrun](docs/experiments/v0.4/v0.4-warehouse-v3-continuity-r8-heldout-replay-postrun-20260809.md).
- [x] Run the pre-registered production transfer 12-stage shakedown. It
  completed 12/12 stages and 211/211 formal pairs with no solver or infra
  failure. The final exact candidate passed screening and reached 5/0/0-case,
  14/1/0-pair validation before Protocol queued expansion. Classification:
  `VALID_FUNNEL_FOR_24STAGE_PREREGISTRATION`; champion remains v1 and the root
  is sealed. See the
  [postrun](docs/experiments/v0.4/v0.4-warehouse-v3-production-transfer-prod11-12stage-r1-postrun-20260809.md).
- [x] Complete the prospective research-design corrections before the longer
  rung: effect-metric measurement, optional problem-owned protected objectives,
  strictly nested expansion populations, declared bootstrap execution, the V3
  provider-history projection, phase-correct Warehouse H/C guidance, and plain
  source-content context without owner/hash self-proof. Focused review found no
  P0 issue, and the complete suite passed `2011 passed, 1 skipped`. The fresh
  Warehouse H also receives the prod-1.1 aggregate scientific prior once,
  without forcing continuation or abandonment of its prior mechanism.
- [x] Freeze prod-1.2 with the five independently fixed new validation cases,
  keep the old five as the initial population and all ten as expanded
  validation, and run one separately preregistered fresh 24-stage campaign.
  It completed 24/24 formal stages and 297/299 valid pairs, promoted a
  DestroyRebuild refinement v1→v2, and its separately preregistered replay
  passed all 12/12 fresh held-out pairs at 4/0/0 cases and 12/0/0 pairs.
  Classification: `RETAINED_PRODUCTION_IMPROVEMENT`. See the campaign
  [postrun](docs/experiments/v0.4/v0.4-warehouse-v3-production-transfer-prod12-24stage-r1-postrun-20260809.md)
  and replay
  [postrun](docs/experiments/v0.4/v0.4-warehouse-prod12-independent-heldout-v1-postrun-20260809.md).
- [x] Keep parameter/weight search disabled for this task. Warehouse structural
  continuity was demonstrated without it, and it is not part of the CVRP
  promotion experiment.

Warehouse acceptance:

**Satisfied.** Synthetic R8 and its replay establish continuous v1→v2→v3
optimization; prod-1.2 and its replay establish retained production transfer.

- one fresh campaign reaches at least v3 through two exact
  screening->validation->frozen promotions;
- no promotion depends on incomplete pairs, cached-only runtime, threshold
  changes, seed shopping or framework failure;
- final replay supports retained improvement over v1 and the immediate parent;
- production transfer is either positively promoted or negatively resolved by
  the pre-registered matched experiment.

### S5 - CVRP open research and promotion ladder

- [x] Remove the outcome-derived expand-case path so every initial and expanded
  population is selected only from the fixed Protocol. Pre-experiment
  problem-owned case configuration may remain; current candidate results may
  never alter it.
- [x] Verify the shared prospective research-design corrections on CVRP before
  launch: effect metric is `total_distance`, `fleet_violation` is the only
  explicitly protected objective, expanded populations contain their initial
  cases, and provider H history contains actionable compact evidence rather
  than repeated per-pair telemetry or self-proof metadata. The CVRP projection
  retains every formal pair while removing repeated candidate/champion mirrors.
- [x] Freeze the current B0 ALNS+VNS champion and declared ProblemSpec,
  Protocol, split and seed inputs before a new campaign. Do not globally
  disable VNS or weaken the canonical baseline. The matched 8-stage R1 inputs,
  context semantics, measurement claim limits and independent final population
  are fixed in the
  [preregistration](docs/experiments/v0.4/v0.4-cvrp-v3-open-research-8stage-r1-preregistration-20260809.md).
- [x] Deliver the complete safe CVRP cross-campaign prior through the actual H
  payload as neutral evidence. Remove the host-authored `materially different`
  instruction or Contract requirement: Contract may enforce schema,
  approved-H binding and source boundaries, but it must not demand novelty,
  rank mechanisms or reject an evidence-driven same-branch refinement.
- [x] Start a fresh campaign with the open V3 proposal path: one unconstrained,
  source-grounded H chosen by the provider, structural H Contract, one
  approved-H-bound C, structural Patch Contract, isolated materialization and
  executable Verification. Do not force SWAP*, another mechanism, surface,
  action or target. Historical SWAP* evidence is one neutral prior item only.
  R1 launched once and stopped at 5/8 on infrastructure; this checkbox records
  launch/path behavior, not completion or promotion.
- [x] Send every verified candidate directly into the existing paired
  screening Protocol and deterministic Decision. There is no assay admission,
  mechanism-support prerequisite or host algorithm-quality stop between
  Verification and Protocol. All five R1 formal candidates followed this path.
- [x] Preserve V3 same-branch research depth. After a completed screening
  observation, a non-promoted verified candidate remains the provisional
  branch source for the next H under V3 §11.2; the next H receives complete
  safe branch evidence and may refine or change direction. Do not impose a
  one-refinement cap and never retry the same provider call. R1 branch C used
  its own depth-one source and current/sibling evidence for a later refinement.
- [x] When Protocol queues expanded screening, validation, expanded validation
  or frozen, drain that stage on the same exact candidate and campaign state
  with no further H/C call. Only predeclared case/seed populations, Protocol
  statistics, Safe Features and deterministic Decision may advance, abandon
  or promote it. R1's one queued screening expansion drained exactly this way;
  validation/frozen behavior still requires a future passing candidate.
- [x] Keep mechanism activation, elapsed share, ALNS opportunity and any
  problem-owned assay output observational. They may appear in raw evidence,
  postrun analysis and safe next-H feedback, but may not stop or admit the
  current candidate, alter cases/seeds, enter Decision or create a new
  framework seam. R1 confirms that mechanism evidence informed H without
  admitting or rejecting a candidate.
- [x] Seal and analyze R1 without retroactive threshold, seed, case or source
  changes. Record the exact 5/8 terminal classification, five formal results,
  research behavior, mechanism evidence, measurement power and proposal-path
  defects in its postrun report.
- [x] Before corrected R2, implement only observed hot-path corrections:
  unique blank-line-run edit application; one typed research-rejection owner;
  neutral ejection evidence with operator-local denominators; paired-median
  case direction; exact 4-to-8 seed expansion; estimator provenance; and
  lossless removal of duplicate latest H evidence. R2 is explicitly
  uncalibrated. The 2047-test full suite, one skipped test, focused regressions,
  critical Ruff checks and diff check pass without deployment, Trust/Hash,
  mechanism or telemetry gates.
- [x] Pre-register corrected R2 as a fresh staged-measurement, claim-bounded
  campaign. Freeze its
  paired case estimator, equivalence semantics if any, seeds, structural case
  strata, screening/validation/frozen populations and formal-stage horizon
  before launch. Keep screening advancement separate from champion promotion.
- [x] Freeze and audit the provider research surface as part of that R2
  preregistration: enumerate each H/C context section, its scientific purpose,
  the complete current solver source and problem mechanics available to the
  provider, the edit/research tools it may actually use, and the minimum V3
  rules it must obey. Record provider input size, tool/edit outcomes and typed
  rejection causes for analysis only. Do not impose token top-k, novelty,
  mechanism, activation, style or algorithm-quality gates.
- [x] Run corrected R2 once in a new absent root through the same open H/C and
  V3 authority path. It completed 10 formal stages and 448/448 valid pairs,
  then stopped on a terminal-less provider C at 10/12. The sealed root is
  `RUN_INVALID_INFRA / VALID_PARTIAL_SCIENCE_10_OF_12`; champion remains B0/v1.
- [x] Separate R2 research behavior, measurement reach and framework friction
  in its postrun. The strongest elapsed-budget SA reached 6W/1L/5T cases and
  `+2.75 [0,11]`, but correctly missed the fixed 0.60 all-case win threshold.
  It is a prospective R3 lead, not a retroactive R2 pass.
- [x] Complete the observed R3 hot-path code and design prerequisites at
  `6d5be022`: lossless compact H/C framing; trace-only provider completion
  facts; intended-H versus executed-patch facts; optional descriptive
  `expected_effect`; tie-aware case quality with a loss veto; and four
  outcome-blind disjoint populations. No quality, novelty, activation,
  Trust/Hash, token or runtime gate was added. The clean fixed-source suite is
  `2081 passed, 1 skipped` in 633.04 seconds.
- [x] Run the separately pre-registered provider-free same-seed A/A/null
  calibration on quality, validation and frozen. All three stages completed
  24/24 pairs with zero pair errors or runtime-budget hits; every observed
  combined rule was false, and every 2,000-swap null had 0 passes with a
  one-sided 95% Wilson upper bound of `0.001351`. All artifacts state
  `decision_features_excluded=true`, so the calibration is acceptable under
  its preregistration. The
  [postrun](docs/experiments/v0.4/v0.4-cvrp-v3-r3-aa-null-postrun-20260809.md)
  remains diagnostic only and cannot enter Decision or establish power.
- [x] Pre-register R3 in a fresh absent root as an integrated corrected,
  promotion-seeking rung. The
  [16-stage R3 design](docs/experiments/v0.4/v0.4-cvrp-v3-quality-screen-16stage-r3-preregistration-20260809.md)
  freezes executable commit `76f3e976`, provider context/tool surface, all
  four disjoint populations, ordered seeds, dimension budgets, initial-only
  expansion and the exact net/loss/median/CI rule. R3 may establish the
  integrated configuration, not causal credit for each correction.
- [x] Launch R3 once with `gpt-5.6-terra` after the local Codex proxy became
  healthy. The one allowed campaign ran at
  `/home/clawd/research/scion-experiments/v04-cvrp-v3-quality-screen-16stage-r3-gpt56terra-20260809T194031Z-claw/campaign`
  on exact runtime `76f3e976`; it was never retried or resumed and is now
  sealed after the host reboot described below.
- [x] Let the first R3 exact candidate that met the complete quality rule drain
  its predeclared quality expansion. The route-removal candidate completed
  96/96 pairs at 7W/0L/5T cases and `+3.5 [0,6.25]`; two independent
  recomputations and the
  actual/expected `SCREENING_PASS -> queue_validate` route matched with zero
  execution, fleet or protected-objective regression.
- [x] Stop at the external reboot boundary without adjudicating the incomplete
  validation. The last durable status had 52 attempted and 51 completed/valid
  validation pairs with zero candidate, champion or total execution failures;
  Protocol retained 10 screening, zero validation and zero frozen stages, and
  champion remained B0/v1. The host rebooted at `2026-08-10 05:44 UTC`, so this
  is `RUN_INVALID_INFRA / VALID_PARTIAL_SCIENCE`, not an algorithm negative.
  Do not read the partial stage's W/L/T, deltas or gate, and do not resume,
  retry or modify the root.
- [x] Do not launch the preregistered R3 clean promotion recovery. Recovery
  required a Protocol-complete promotion and ordinary promoted snapshots; the
  reboot left neither. The completed quality result remains valid partial
  science, but it cannot select a recovery candidate or establish retained
  improvement.
- [x] Seal and classify R3 in the
  [reboot postrun](docs/experiments/v0.4/v0.4-cvrp-v3-quality-screen-16stage-r3-reboot-postrun-20260810.md),
  separating the infrastructure interruption from completed implementation,
  search, context and quality-screen evidence. Use chronological lineage,
  never a favorable-result cohort, and report `UNIDENTIFIABLE` where raw facts
  are incomplete.
- [ ] After R3 is terminal, replace the pending V8 diagnostic expansion with
  the minimal failure-only design: successful same-seed checks write no
  sidecar; a canonical mismatch writes one bounded record containing case,
  seed, comparison mode, declared objectives/feasibility and the first bounded
  differing paths. Delete the separate generic sidecar schema, duplicate
  ledgers and problem-specific telemetry projection; diagnostic write failure
  must not change the Verification verdict.
- [x] Audit every completed R3 H/C call chronologically and outcome-blind before
  reading its Protocol result. For H record the exact unique source-file set,
  context-section size, schema validity, named owner/symbol, mechanism-versus-
  meta focus and use of prior/failure facts. For C record provider finish/tool/
  argument facts when available, edit files/intents, apply result and one
  observational fidelity label: `faithful`, `partial`, `scaffolding_only`,
  `different_mechanism` or `unidentifiable`, with exact changed-symbol evidence.
  Preserve neutral implementation-status facts separately from algorithm
  outcomes: time-aware operator credit was proposed in R2 and R3, but both
  schema-valid C outputs added unused scaffolding only, so the mechanism remains
  unimplemented and untested. This audit cannot reject, rank, retry or alter a
  candidate and cannot force the next mechanism.
- [x] Freeze the terminal R3 ordinary-lineage cohort outcome-blind. Complete
  primary plus ordered `additional_changes` replay produced six chronological
  unique exact candidates with true immediate bases; all three durable branch
  heads matched their reconstructions byte-for-byte across 53 ordinary Python
  files, one research rejection was omitted, and independent review passed.
  Earlier r1/r2 materializer differences came from that analyzer omitting
  `additional_changes`, not from Scion runtime drift. The cohort lives only in
  the experiment evidence root and restores no recorder, identity or replay
  authority.
- [x] Launch provider-free R45 diagnosis R1 once, then seal it at its structural
  terminal boundary. It ended `complete=false`, accepted zero of 37 blocks and
  produced no analysis after the process disappeared during the first `MDE`
  block. The partial 46/96 raw rows are inadmissible and are not read for
  W/L/T, effect, gate or objective, resumed, completed or reused.
- [x] Run the
  [R2 replacement](docs/experiments/v0.4/v0.4-cvrp-r3-ordinary-lineage-r45-diagnosis-r2-replacement-preregistration-20260810.md)
  once as ordinary `clawd` through the input bundle's `launch-r2.sh`. It
  completed 96/96 attempted and valid MDE pairs with zero subject failures, but
  the one-off driver rejected legitimate auxiliary `routes` telemetry before
  accepting the block. Exit was `2`, status stayed zero of 37 accepted blocks
  with `last_block=null`, and no analysis exists. Seal R2
  `RUN_INVALID_EXPERIMENT_DRIVER / ZERO_ACCEPTED_BLOCKS /
  NO_ADMISSIBLE_ANALYSIS`; do not read its scientific outcome, resume it or
  reuse a pair.
- [x] Run the separately
  [preregistered R3 replacement](docs/experiments/v0.4/v0.4-cvrp-r3-ordinary-lineage-r45-diagnosis-r3-driver-replacement-preregistration-20260810.md)
  once from fresh MDE 0/96. R3 launched after explicit confirmation at
  `2026-08-10 15:21:30 UTC` and completed with exit `0`, all 37 accepted blocks,
  1,056 unique rows and terminal analysis. It copied or combined no R1/R2 pair.
  The sole driver correction accepted auxiliary objective telemetry while still
  requiring every declared finite metric and exact delta; no Scion core gate
  changed and no R4 launched automatically. The complete result is recorded in
  the [postrun](docs/experiments/v0.4/v0.4-cvrp-r3-ordinary-lineage-r45-diagnosis-r3-postrun-20260811.md).
- [x] Before the provider-free CVRP factor/budget replay or any new promotion
  campaign, make formal comparison
  evidence analysis-complete without a new runner: disable champion caching,
  run both subjects fresh, alternate AB/BA order deterministically, and persist
  scheduled/actual order. Let
  A be the immediate base and B the candidate; use AB when
  `(candidate_ordinal + block_ordinal + case_ordinal + seed_ordinal) mod 2 == 0`
  and BA otherwise. Record only block/case/seed ordinals, scheduled/actual order,
  each side's full objective mapping, feasible/success, elapsed/time limit and
  one bounded failure or exit fact. Put the provider-free/Decision-excluded
  boundary once in the experiment manifest rather than every row. The factor
  diagnosis labels immutable `Q00/Q01/Q10/Q11` blocks and executes them once in
  `all Q00 -> all Q01 -> all Q10 -> all Q11 -> all .5x -> all 2x` order.
  Aggregate statistics combine only immutable completed blocks. Reuse the
  existing runner and
  expansion state. The default-off seam landed at `c32f5b8a` with exactly 100
  net production lines and passed 46 focused/adjacent tests plus independent
  review. Do not prebuild atomic production-campaign expansion; it is considered
  only after the diagnosis proves another promotion campaign is warranted, with
  a separate 150-line ceiling.
- [x] Freeze the minimal provider-free attribution diagnosis in the
  [measurement-attribution design](docs/experiments/v0.4/v0.4-measurement-attribution-design-20260809.md).
  It reconstructs only exact candidates from ordinary lineage, then reuses the
  problem Protocol, runner and raw pair evidence; decomposes cumulative
  case/seed cells into four atomic blocks; and makes missing source/base,
  telemetry, fourth-seed or clean-CPU evidence explicitly `UNIDENTIFIABLE`. It
  restores no formal recorder and adds no runner, gate or Decision input. Its
  corrected future connecting roster, Tai budget aliases and campaign claim
  remain prospective until a separate post-diagnosis preregistration freezes
  them.
- [x] Calibrate measurement sensitivity against the exact frozen R3 roster,
  case-median estimator, eight-seed design, `1x` budgets and practical delta.
  The independent B0 A/A diagnosis gives `MDE@80%=2.0` for a homogeneous
  additive effect at 0.25 resolution. This is not power for another roster,
  another budget or heterogeneous/scoped effects, and it creates no candidate
  futility gate.
- [x] On that same frozen cohort, measure `0.5x / 1x / 2x` dimension budgets
  with fixed cases and seeds. The complete result is mixed and descriptive:
  `.5x - 1x` has 1 positive / 4 zero / 1 negative candidate directions, while
  `2x - 1x` has 2 / 3 / 1. Missing activation evidence limits mechanism
  attribution only. Because all whole arms ran in one frozen order,
  whole-budget-arm machine drift remains `UNIDENTIFIABLE`; no saturation,
  telemetry or budget result becomes a candidate gate.
- [ ] As a non-blocking measurement backlog, reanalyse the already accepted
  Warehouse cohorts provider-free: compare
  the current selector with one predeclared size/headroom/structure-stratified
  selector, nested two- versus four-seed evidence and paired-median versus the
  current seed-vote estimator. Do not rerun a Warehouse provider campaign or
  reinterpret its accepted promotions; use the result only to freeze a cleaner
  future regression population with equal modify/create case counts. Exact
  champions, full case universes, four seeds and selector arms are frozen in
  the [Warehouse reanalysis preregistration](docs/experiments/v0.4/v0.4-warehouse-measurement-reanalysis-preregistration-20260809.md);
  execution remains lower-priority than the CVRP R45/cohort diagnosis. Before
  launch, add only
  canary execution accounting for candidate/champion attempts, solver failures,
  blocking-audit failures and all-attempts-completed; the heldout consumer must
  distinguish an existing candidate safety veto from incomplete comparison
  evidence. This changes no canary pass/veto, Protocol or Decision rule and
  adds no ledger or gate.
- [ ] Use that Warehouse reanalysis, not edit action, to freeze any later
  research population. A future Warehouse epoch must use equal case counts for
  modify/create, paired effects, size-aware budgets and seed-only atomic
  expansion; selector, estimator, seed count and budgets remain undecided until
  the frozen provider-free result exists.
- [x] Do not run an H research-core context A/B on current evidence. All seven
  audited R3 H calls were schema-valid, received the complete unique source
  union, named the correct owner/symbol and stayed algorithm-focused, so the
  trigger is not met. A later matched A/B remains conditional on at least two
  independent H calls showing the same missing/truncated research fact or
  duplicated-wrapper misunderstanding. It must retain objective, invariants,
  mechanics, legal positive surfaces, complete current source and algorithm
  evidence, and may be chosen only by proposal/source-grounding measures, never
  solver W/L/T, token count or a gate.
- [x] Reduce the provider projection to the V3 research core without changing
  scientific content. H retains objective/invariants, solver mechanics, legal
  positive surfaces, complete current source, screening-level evidence and the
  latest actionable rejection while recursively excluding host/control
  metadata. C receives exactly the approved hypothesis plus the ordinary
  editable source context, whose target guidance consolidates the positive
  Warehouse/CVRP API, object-model and edit-surface facts. The complete raw
  structured context remains durable in trace; Contract owns negative path,
  import and edit rules. This is part of the R52 net deletion and adds no gate
  or provider tool loop. H history was not compressed merely for length.
- [x] Prepare and independently review the frozen C-expression A/B input bundle
  at `campaign_out/v04-cvrp-c-expression-ab-20260811-input`. It references
  exactly four historical H/C traces and their embedded ordinary 11-file
  source, freezes both terminal tool definitions and four outcome-blind
  checklists, and adds zero production lines. Its experiment-owned modules are
  203-line runner, 123-line strict diff parser and 139-line frozen-input loader
  (465 lines total). Frozen-input and `bash -n` checks plus 15 focused tests
  pass. One archived pre-driver acquisition failure made zero scientific/model-
  generation or solver calls and is not part of the later scientific run. The
  real CVRP direct outer smoke also passes `1 passed in 32.55s`; its MockLLM no-op establishes only
  local short-chain stability.
- [x] Run and close the triggered C expression A/B. One
  deterministic multi-site closure failure plus independent R2/R3
  scaffolding-only omissions meet its predeclared diagnostic trigger; this does
  not itself prove schema causality. Compare the complete current one-shot
  exact/full-file terminal tool definition with one complete one-shot
  source-bound unified-diff definition on frozen approved-H/source inputs.
  Normalize both into the same `PatchProposal` before the unchanged Contract;
  retain exact H binding and deterministic apply, with no fuzzy repair, retry,
  shell or model tool loop. Score parse/apply success and blinded
  H-obligation/source-anchor coverage only, never solver W/L/T.
  The diagnostic uses four solver/Protocol-outcome-blind frozen fixtures and
  adds zero lines to the production campaign path. Both arms reuse the exact H
  and provider context, verify approved-H value equality and run unchanged
  `validate_patch(..., approved_hypothesis=H)`. A terminal parse/apply rejection
  is fixed to both rubric scores zero without a blind packet; a Contract
  rejection retains its normalized-patch packet and two blind reviews. Both are
  measured treatment-negative cells and do not stop later cells; only a
  missing/misbound provider cell or invalid frozen binding stops.
  The run exited `0` with 8/8 terminal provider cells and no solver call. All
  four exact cells applied and passed Contract; all four diff cells failed
  strict application with context/removal mismatch and fixed `0/0` scores. Two
  blind reviewers agreed on exact scores totaling H=`5` and source-anchor=`5`.
  All four adoption conditions fail: retain exact, close strict diff and add no
  production normalizer, retry or gate. Exact fixtures, counterbalanced order,
  blind rubrics and the conservative rule are recorded in the
  [C-expression A/B preregistration](docs/experiments/v0.4/v0.4-cvrp-c-expression-ab-preregistration-20260810.md).
  The terminal interpretation is in the
  [postrun](docs/experiments/v0.4/v0.4-cvrp-c-expression-ab-postrun-20260812.md).
- [x] Replace `proposal_source_ledger` with one ordinary
  `editable_source_context`: approved target, unique canonical path/content
  pairs and target API guidance. Branch-current history/workspace source wins
  over the champion; a touched-missing helper never falls back; `content=None` denotes
  an absent create target while an empty string remains an existing empty file;
  create/modify behavior and exact selector application remain strict. Entry
  digests, owner/provenance/visibility/reason, view sets and self-rehashing
  validation are deleted. The selector digest remains only as runtime content
  binding. Across the complete R52 provider/source subtraction, nine production
  files changed by `+273/-551`, net `-278`, with no replacement authority.
- [ ] Do not add provider shell, execution, network, read/search or edit loops
  on present evidence. Reconsider a matched source-navigation A/B only if two
  independent terminal C calls fail on the same source/API/callsite fact, the
  trace proves that fact was absent rather than ignored, and complete source
  push has become the limiting context surface. Any treatment is restricted to
  list/read/search over the same already legal source and requires a separate
  V3 runtime design update; it never reads Protocol or protected evidence.
- [x] After fresh explicit authorization, run the
  [minute one-step exploratory screen](docs/experiments/v0.4/v0.4-cvrp-minute-one-step-preregistration-20260812.md)
  once from its clean `e4b6b98d` bundle and complete independent read-only
  [postrun analysis](docs/experiments/v0.4/v0.4-cvrp-minute-one-step-postrun-20260812.md).
  The run preserved H/C limits `1/1`, retry zero, two-second
  canary/Verification budgets, seed `11`, the four frozen
  `8/12/12/15`-second cases, fresh cache-off `AB/BA/AB/BA`, the 720-second
  driver wall and exactly one `CampaignManager.run_one_step()`. It terminalized
  `VALID_COMPLETED_ONE_STEP_SCREEN` at `0W/1L/3T`, median `0 [-16,0]`, no fleet
  regression and no promotion. This remains a valid negative diagnostic, not
  broad CVRP improvement or task completion.
- [x] After fresh explicit authorization, run the
  [R54 minute feedback one-step](docs/experiments/v0.4/v0.4-cvrp-minute-feedback-one-step-preregistration-20260812.md)
  once from fresh B0 on clean `e4b6b98d`, then complete independent read-only
  [postrun analysis](docs/experiments/v0.4/v0.4-cvrp-minute-feedback-one-step-postrun-20260812.md).
  H/C, canary and formal-call counts stayed `1/1/1/1`; no validation, frozen or
  promotion ran. H used R53's negative evidence well, while C left three calls
  to its deleted `cool()` method. E101/X120/X233 are three valid ties; P65 is a
  typed candidate runtime-audit failure and has no admissible delta/W/L/T.
  Decision recorded `abandon`, after which a separate canonical-context
  cardinality `ValueError` caused wrapper exit `1`. Seal the root
  `VALID_TERMINAL_CANDIDATE_RUNTIME_FAILURE / DECISION_ABANDON /
  FRAMEWORK_POST_DECISION_CONTEXT_PERSISTENCE_ERROR / NO_PROMOTION`; do not
  resume, retry or promote it.
- [x] After fresh explicit authorization, launch the
  [R56 corrected-runtime minute one-step](docs/experiments/v0.4/v0.4-cvrp-r56-minute-corrected-one-step-preregistration-20260812.md)
  exactly once, then complete independent read-only
  [postrun analysis](docs/experiments/v0.4/v0.4-cvrp-r56-minute-corrected-one-step-postrun-20260812.md).
  The wrapper exited `0` after one H/C and a passing Contract. V3 rejected all
  three recovery fixtures on residual calls to the removed `cool()` API; V4,
  canary, formal Protocol and Decision were not reached. Seal
  `VALID_TERMINAL_RESEARCH_PROCESS_OBSERVATION / VERIFICATION_LIGHT_REJECTED /
  ZERO_PROTOCOL_EVIDENCE / NO_DECISION / NO_PROMOTION`. B0/v1 remains champion;
  do not repair, retry or infer algorithm quality.
- [x] After fresh exact authorization, launch the
  [R58 expression-corrected seed-29 minute one-step](docs/experiments/v0.4/v0.4-cvrp-r58-minute-expression-corrected-one-step-preregistration-20260812.md)
  exactly once, then complete independent read-only
  [postrun analysis](docs/experiments/v0.4/v0.4-cvrp-r58-minute-expression-corrected-one-step-postrun-20260812.md).
  The wrapper exited `0` after one valid H/C and passing Contract. Although C
  saw the optional R57 line-oriented form, it used six exact edits, removed two
  of five calls and left three calls to the deleted method. V3 rejected all
  three recovery fixtures in 568 ms; V4, canary, formal Protocol and Decision
  were not reached. Seal `VALID_TERMINAL_RESEARCH_PROCESS_OBSERVATION /
  VERIFICATION_LIGHT_REJECTED / ZERO_PROTOCOL_EVIDENCE / NO_DECISION /
  NO_PROMOTION`. Do not infer seed-29 or algorithm quality, repair/retry the
  root, or launch an R59 provider experiment or long/WSL work. Pause provider
  experiments for a minimal provider-free C expression-selection redesign and
  test.
- [x] After a new exact source-send authorization, run the
  [R60 C-only tool-presentation matched pair](docs/experiments/v0.4/v0.4-cvrp-r60-c-tool-presentation-pair-preregistration-20260813.md)
  once. Hold the full R58 C turn constant and call Terra in fixed OLD
  `42535efc` then NEW `47fe81ee` order, at most one C per arm and retry zero.
  Omit explicit `prompt_cache_key` symmetrically in the experiment wrapper and
  prove the actual captured request kwargs otherwise match. Store both
  terminal responses before the provider-free production parser,
  source-bound Contract, materializer and non-skipped V3/V4 score opaque cells;
  after materialization, V3 and V4 each run independently even when V3 fails.
  Reveal the arms only after both primary records. Treat concrete edit intent,
  selector-match count and residual calls as
  descriptive diagnostics, not gates. Run no H, canary, formal Protocol,
  Decision or algorithm-quality comparison. An incomplete provider pair is
  unidentifiable and is never retried or resumed.
  The authorized run completed exit `0` with two terminal responses and two
  opaque primary scores before reveal. Both arms were fully executable and
  both selected the five-site line expression, so seal `BOTH /
  BOTH_LINE_SELECTION / NO_IDENTIFIED_PRESENTATION_ADVANTAGE`. Independent
  post-hoc source inspection keeps both implementations out of algorithm
  testing; see the
  [postrun](docs/experiments/v0.4/v0.4-cvrp-r60-c-tool-presentation-pair-postrun-20260813.md).
- [x] Run the independent provider-free
  [R61 semantic audit](docs/experiments/v0.4/v0.4-cvrp-r61-provider-free-semantic-audit-postrun-20260813.md)
  over the sealed R60 workspaces. Each cell/progress probe used a fresh
  temporary copy and subprocess with one synthetic ordinary worsening
  iteration. OLD passed deadline wiring but failed weight accounting at `2/1`;
  NEW failed deadline wiring with temperature fixed at `5.0` but passed weight
  accounting at `1/1`. Retain the two booleans separately and leave aggregate
  algorithm success undefined. This provider-free control-flow audit used no
  case, benchmark, provider, canary, formal Protocol, quality solver or
  Decision call and does not rewrite R60.
- [ ] If a new CVRP promotion campaign is required, pre-register a fresh root
  after the diagnostic inputs are frozen. Change one measurement axis at a
  time (`8x4 -> 8x8 -> 12x8`) on a four-cell connecting quality population:
  non-X `<=100`, non-X `101-200`, X `101-200` and X `>200` each contribute two
  initial cases and one added case. The existing single expansion authorization
  atomically drains added seeds and then added cases; the intermediate `8x8`
  checkpoint is diagnostic and cannot call Decision or stop early. Keep
  validation/frozen/final replay disjoint, freeze the exact H/C context
  inventory and provider tool surface, and count an epoch by at most eight
  chronological initial candidates rather than by formal stages. After
  candidate eight, stop new H calls but drain every exact queued quality/
  validation/frozen stage. Report
  consistent predeclared stratum evidence as `SCOPED_SIGNAL_ONLY` rather than
  broad advancement or null; complete family-by-size interaction remains
  `UNIDENTIFIABLE`. The roster supports fixed non-X-low versus non-X-mid
  mixture descriptions, X mid-to-large direction, and non-X-versus-X at common
  mid size. Because the non-X low and mid cells use different benchmark-family
  mixes, they do not identify a causal within-family size effect. Existing
  later splits are X/large-heavy robustness holdouts, so do not describe the
  whole campaign as population-balanced or infer a causal absolute-headroom
  effect. Use only V3
  Contract, executable Verification, fixed problem Protocol, Safe Features and
  deterministic Decision as authority.

CVRP acceptance:

- one exact candidate completes all declared pairs with no feasibility, fleet,
  candidate-runtime or champion-runtime failure;
- existing Protocol passes screening, validation and frozen without threshold,
  manifest, case-selection or budget changes made after results;
- deterministic Decision promotes to champion v2 or later;
- independent final comparison against original B0 confirms retained distance
  improvement and states the exact case-family scope.

### S6 - Close only on solver evidence

- [ ] Run the full relevant suite plus focused formatter/linter and diff check.
- [ ] Update `docs/status/current-state.md` with exact campaign roots and honest
  claim boundaries.
- [ ] Write one cross-problem report separating framework behavior,
  mechanism-level evidence, formal promotion and independent replay.
- [ ] Mark this task complete only when both Warehouse and CVRP acceptance
  blocks are satisfied.

## Experiment discipline

- Main Python: `/home/clawd/miniconda3/envs/claw/bin/python`.
- Model: `gpt-5.6-terra` through the local Codex proxy at
  `http://127.0.0.1:8080`.
- Use a fresh campaign root for each pre-registered arm. A queued stage within
  one arm must drain on the same exact candidate and campaign state.
- Every launch plan includes one compact research-input card: scientific
  question; exact source/champion; provider model; H/C context inventory and
  tool surface; case families, seeds and per-dimension budgets; estimator and
  transitions; the distinct quality/validation/frozen/final estimands;
  fresh/cache policy, deterministic subject order and atomic block reuse;
  CPU-isolation controls; minimum lineage; and the claim boundary for broad,
  scoped or underpowered negative results.
- No provider call is retried. A new implementation correction is a new H/C
  candidate with its own evidence.
- Do not change framework source while an experiment is running.
- Factor, budget, recovery and Warehouse replays run serially in a
  CPU-exclusive window. If competing solver/test work overlaps an atomic block,
  mark the whole affected block contaminated; never prune individual pairs by
  observed outcome or reconstructed timing guess.
- Poll long runs observationally at low frequency. Polling must not launch,
  retry or mutate a campaign.
- Preserve terminal roots, user documents, unrelated worktree changes and the
  overlap stash.
- The main session owns V3 architecture, TASK/current-state, experimental
  ordering and final claims. Subagents receive bounded review, implementation
  or analysis tasks.

## Status

**Active on `v0.4-dev`: S5 CVRP open research and
S6 evidence closure.** S1
is closed as a scientific negative; S2/S3 are complete. Warehouse R6 produced
one Protocol-complete synthetic promotion (`v1 -> v2`) and continued for
fourteen formal post-promotion screenings, but stopped at 17/36 on the now-
corrected proposal-rejection route. R7 added four valid formal stages and two
candidate negatives before an intermittent terminal-less provider C; it had no
promotion. R8 then completed 36/36 stages and 534/534 pairs and promoted
`v1 -> v2 -> v3` in one uninterrupted campaign. The separately preregistered
held-out replay completed 108/108 valid pairs and retained v2 over v1, v3 over
v2 and v3 over v1, so synthetic Warehouse continuity is
`CONTINUOUS_OPTIMIZATION_CONFIRMED`. The fresh prod-1.2 campaign then completed
24/24 stages, promoted v1→v2, and retained that production improvement on all
12/12 separately preregistered held-out pairs. Warehouse acceptance is fully
complete. CVRP R1 is sealed at 5/8 formal stages with 176/176 valid pairs, one
reproducible mixed-positive depth-one signal and no promotion. Corrected R2 is
also sealed: it completed 10 formal stages and 448/448 valid pairs before a
terminal-less provider C, so its classification is `RUN_INVALID_INFRA` with
`VALID_PARTIAL_SCIENCE_10_OF_12`. It exercised real ejection, asymmetric 2-opt,
SWAP* and elapsed-budget SA research, but no candidate reached validation or
frozen. The strongest SA quality screen was 6W/1L/5T cases and
`+2.75 [0,11]`; it correctly missed the pre-registered 0.60 all-case win rate
and is not a hidden pass. R3 hot-path code and outcome-blind population design
were frozen at `6d5be022`: compact lossless context, trace-only provider facts,
executed-patch attribution, optional descriptive `expected_effect`, a
tie-aware loss-veto rule, three disjoint 12-case formal blocks and a fourth
disjoint final replay block. Commit `76f3e976` then adds the missing neutral R2
SA evidence and limited A/A interpretation to fresh-H context without adding a
gate. The exact clean-source suite is `2081 passed, 1 skipped` in 639.39
seconds. The provider-free A/A/null calibration completed acceptably under its
  fixed preregistration. The 16-stage R3 campaign ran once at exact runtime
  `76f3e976` and is now sealed after the host rebooted during formal validation.
  Its terminal classification is `RUN_INVALID_INFRA / VALID_PARTIAL_SCIENCE`:
  completed quality evidence is retained, partial validation is unadjudicated,
  durable stage counts are 10/0/0 for screening/validation/frozen, and champion
  remains B0/v1. No recovery candidate exists. R51 retains exact and closes
  strict diff; R52 closes the provider/source subtraction by 278 net deleted
  production lines after 169 main and 207 independent tests. It adds no gate,
  Trust/Hash authority, ledger or provider tool loop. R53 then completed the
  clean minute one-step once with exit `0`: exactly one Terra H/C sequence,
  Contract, Verification, canary and four fresh pairs produced a valid
  analyzable screen. The `0.35` embedded-VNS cap shifted aggregate runtime
  toward ALNS, but finished `0W/1L/3T`, median `0 [-16,0]`, with one P-case
  regression and no fleet regression. Decision correctly recorded
  `SCREENING_FAIL_CASE_QUALITY / continue_explore`; champion remains B0/v1.
  R54 then ran once from fresh B0 on the same clean runtime. H correctly used
  the R53-conditioned feedback to choose elapsed-budget SA, but C removed
  `cool()` while leaving three negative-path calls and Verification did not
  cover them. Formal evidence is three valid ties plus one P-case candidate
  runtime-audit failure; P has no admissible delta/W/L/T. Decision recorded
  `abandon`, then a separate post-Decision screening-context cardinality error
  caused wrapper exit `1`. R54 is sealed
  `VALID_TERMINAL_CANDIDATE_RUNTIME_FAILURE / DECISION_ABANDON /
  FRAMEWORK_POST_DECISION_CONTEXT_PERSISTENCE_ERROR / NO_PROMOTION`.
  R58 is likewise sealed at V3 with zero Protocol evidence. R59 completed the
  provider-free typed-tool presentation correction. R60 then completed one
  exact-turn C-only OLD-then-NEW pair: both arms were fully executable and
  selected the complete five-site line replacement, yielding `BOTH /
  BOTH_LINE_SELECTION / NO_IDENTIFIED_PRESENTATION_ADVANTAGE`. Post-hoc OLD
  duplicate accounting and NEW inactive deadline progress prevent either from
  entering algorithm tests. R60 used no H, canary, formal Protocol, algorithm
  quality or Decision call. R61 subsequently audited the two normalized
  scheduler semantics provider-free: OLD has deadline wiring pass/accounting
  fail `2/1`, while NEW has deadline wiring fail at constant `5.0`/accounting
  pass `1/1`. `aggregate_algorithm_success` remains null, R60 is unchanged,
  provider experiments remain paused. R62 subsequently completed its
  provider-free static sidecar calibration: alpha's separate syntax signals are
  `TRUE/FALSE`, beta's are `FALSE/TRUE`, and both aggregate fields are null.
  It adds no provider, solver, quality, gate, prompt or repair-loop evidence.
  At R62 closeout, provider pause remained and no R63 was preregistered or
  launched. R63 subsequently completed one authorized fixed CONTROL→REVIEW
  C-message pair. Both arms passed the complete 13-field mechanical vector,
  yielding `BOTH / NO_IDENTIFIED_MESSAGE_REVIEW_ADVANTAGE`; their separate
  sidecars are both `UNKNOWN/TRUE`. The one-file boundary-delta patches are
  source-similar, but V3/V4 do not enter `_two_opt_star` and do not test all
  cut, directed or near-EPS cases. R63 adds zero algorithm-quality evidence and
  neither supports nor refutes a review benefit. Its seal does not mean the
  suffix was ineffective or the model did not review. At R63 closeout, no R64
  was preregistered, authorized or launched. R64 subsequently published one
  provider-free `TERMINAL_DIAGNOSTIC` root. Both sealed R63 arms durably
  reproduce cut/near/state `TRUE/TRUE/TRUE` and descriptive calls `0`; all 27
  cut, three near-EPS and three state fixtures equal their references with no
  exceptions. Classification and both aggregates remain null. Because exact
  candidate outcomes were already seen in temporary preparation roots, the
  formal record is durable reproduction with `outcome_blind=false` and
  `independent_confirmation=false`, not new independent evidence. R63 remains
  unchanged; R64 supplies no provider, formal solver, quality, Decision or R65
  evidence. R65 subsequently completed the exact authorized provider-free
  alpha minute calibration. All 10 fresh subprocesses and 98 declared
  subject-seconds completed. B0 and alpha tied at distance 20 on the canary,
  then tied on all seed-73 screen cases: P65=798, E101=1124, X120=14250 and
  X233=20112. Every subject was successful, feasible, runtime-audit valid and
  fleet-safe. The complete result is `0W/0L/4T`, deltas `[0,0,0,0]`, median
  `0 [0,0]`, and zero protected regressions. It seals
  `VALID_COMPLETE_EXPOSED_COORDINATE_MINUTE_CALIBRATION /
  EXPLORATORY_SCREEN_NO_SIGNAL / ORDINARY_MINUTE_RULE_NOT_MET /
  NO_GO_EFFECT_INFERENCE / NO_MORE_PROVIDER_FREE / NO_R66`. Decision and
  promotion are null; provider/H/C/Contract/V3/V4/validation/frozen/Decision/
  promotion/beta/R66 are zero. This exposed-coordinate result is neither effect
  evidence nor independent confirmation, does not pool with R1, and authorizes
  no extension or R66.
  A later, separate authorization covered one R66 H-only mechanism-frontier
  action. The action stopped at fail-closed outer preflight before acquisition
  or provider disclosure because the UTC date rollover changed the single
  time-derived canonical `calibration_age_days` value from frozen `64` to
  rebuilt `65`. R66 is terminal `PREP_INVALID / OuterPreflightFailure` with
  H/provider calls zero, all downstream counters zero, no output and no H
  observation. There is no repair, retry, same-label relaunch, C, solver action
  or R67; the result establishes neither novelty nor quality.
  After that terminal record, the user explicitly instructed removal of the
  diagnosed erroneous gate, repair and continuation. The append-only recovery
  amendment keeps original R66 immutable and prepares a separately rooted R66
  recovery1. Only the date-sensitive canonical reconstruction changes: typed
  `as_of=2026-08-14` reproduces frozen `calibration_age_days=64`; every other
  authority equality remains. At launch freeze, recovery1 was
  `RECOVERY1_PREPARED_AUTHORIZED_NOT_STARTED`. Original plus recovery1 still
  permitted at most one H call, while provider retry, C, solver, Protocol,
  Decision, promotion and R67 remained zero; the then-frozen policy authorized
  no recovery2. Recovery1 later acquired and emitted logical attempt/call `1/1`
  with `TERMINAL_HYPOTHESIS_PROVIDER_FAILURE`, but audited cause is local
  `MISSING_JITER_BEFORE_REQUEST`: no outbound model request, research payload
  or H observation occurred. Every downstream/R67 counter remains zero. Recovery2
  is now prepared provider-free with an exact vendored dependency and fresh
  roots, but remains `RECOVERY2_PREPARED_AWAITING_EXPLICIT_AUTHORIZATION`.
  Prior instructions do not authorize its launch.
  S6 final closure remains pending, and CVRP still has no Protocol-complete
  promotion.

# CVRP M32 hypothesis-candidate-bank research-effectiveness design

Status: **STUDY_DESIGN_ONLY / K2_DEFAULT_OFF_IMPLEMENTED / SINGLE_ARM_OFFLINE_SCORER_IMPLEMENTED / EXACT_FIVE_BLOCK_OFFLINE_COMPARATOR_IMPLEMENTED / INITIAL_SCREENING_BOUNDARY_IMPLEMENTED / ORDINAL_SCREENING_CELLS_IMPLEMENTED / STRICT_DECODED_ARTIFACT_STUDY_ROOT_AUDIT_IMPLEMENTED / SAFE_ROOT_LOADER_IMPLEMENTED / CONFIG_SUBSET_CONTROLS_IMPLEMENTED / CONFIG_SUBSET_MANIFEST_JOIN_IMPLEMENTED / REQUESTED_PROVIDER_POLICY_PRODUCER_IMPLEMENTED / CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_MANIFEST_JOIN_IMPLEMENTED / PROBLEM_SPEC_DECLARATION_PRODUCER_IMPLEMENTED / NO_POPULATION_SELECTION / NO_MATCHED_RESULT / NO_LIVE_AUTHORITY / NO_GO**

Date: `2026-08-25`

Telemetry carrier:
`a3b1ed9b7182fa0566283531d968e7833b22e2f8`

Current configuration-skeleton carrier:
`a2fe7c3830c84a0fc439370434636a61e8a34d47`

K=2 carrier:
`25b78037034e0f443d030c825fb84badce6513e8`

Attempt-telemetry carrier:
`b0d81ddbca0f620689b79a38d7f6702da2163dbc`

Single-arm offline-scoring carrier:
`bda346e96aec47b49e7078533ba781a47a84771a`

Exact-five-block offline-comparison carrier:
`3e97243d96df1082246d06c1440c0e2c5480fe28`

Initial-screening producer-boundary carrier:
`042da9e88d1e85eca4a0a431cd187c5eaae2e3fb`

Ordinal paired-effect-cell carrier:
`a8e483bb285fb49b3482c797e93792d013470db3`

Initial-only interruption-hardening carrier:
`8b7b59886ad0ae6b10f2f672df24ecebd66270da`

Strict decoded study-root audit carrier:
`acff2f0ac3b5f9a8a7c7d56a23f200ca4fd9449e`

Safe study-root loader carrier:
`4256c190ccf3d75c492ed81c18dcb97ef3072286`

Initial-screening configuration-subset carrier:
`f2fd0053e5cb5ed5e880c7e369b3141a9c600d2a`

Configuration-subset manifest-join carrier:
`94455954aceced50d31a943cf3185290edb813f4`

Requested-provider-policy producer carrier:
`7ad892eb303cae035edc35b1360dbb9b1d1e3b6a`

Configuration-subset plus requested-provider-policy manifest-join carrier:
`8560a892cac3e540ed4862ee209eaa2640ccba38`

ProblemSpec declaration producer carrier:
`1b967d938c1c3956a7024d0c9d0aeb35833fef52`

This is a measurement and future-study design, not a live preregistration. It
does not select, rank or materialize a case, seed, salt, population, campaign
label or output root. It grants no provider, solver, raw-body, campaign,
qualification, retry, successor or held-out access authority.

## Scientific purpose

M30 showed that the deterministic Contract, Verification, Protocol, Decision,
qualification accounting and fail-closed postrun boundary can operate, but its
three proposal attempts produced only one formal candidate in 25 provider
calls. That one candidate completed a valid initial screen and failed the
predeclared case-quality gate. M30 therefore motivates a research-efficiency
question; it does not prove that a larger H candidate bank would help.

M32 asks whether allowing the provider to stage at most two complete H values
inside one already bounded H session, then select exactly one of those values,
can improve both:

1. exact-distinct formal-candidate yield per charged provider call; and
2. the proportion of formal candidates that pass the unchanged initial
   development-quality gate.

No host ranks mechanisms, files, hypotheses or expected effects. Contract,
Verification, canary, Protocol, Safe Features and Decision remain unchanged.

## Current carrier boundary

Telemetry carrier `a3b1ed9b7182fa0566283531d968e7833b22e2f8` does exactly two
relevant things:

- bounded H/C campaigns report `proposal_runtime_mode=bounded_research_v1`
  instead of the misleading `direct_v3`; and
- their public status/summary projection includes one atomic aggregate
  provider-budget snapshot: cap, budget-admitted calls, remaining calls and
  counts for known request kinds plus `other`.

The snapshot contains no prompt, response, H, patch or provider-authored body.

Follow-on carrier `a2fe7c3830c84a0fc439370434636a61e8a34d47` added the
fail-closed configuration skeleton. Carrier
`25b78037034e0f443d030c825fb84badce6513e8` then made explicit K=2 the only
additional accepted value and implemented two private ordinal H slots inside
one existing bounded session. The slots share the original turn, read, search,
transcript and campaign provider budgets; the provider selects exactly one
existing slot to export H, or may abstain and export none. Every unselected
staged H, including both values after abstention, remains only in tainted
provider traces. K=2 construction is restricted to qualification-only
composition with its bounded proposal-attempt limit and explicit provider-call
and hardwall caps.

Carrier `b0d81ddbca0f620689b79a38d7f6702da2163dbc` adds count-only
attempt lifecycle, provider-call deltas and H/C boundary telemetry. Carrier
`bda346e96aec47b49e7078533ba781a47a84771a` adds a pure single-arm
provider-/solver-free scorer for the frozen physical, replay-adjusted and
paired-effect endpoints. Its output contains only counts, ratios and fixed
availability/status values. It does not emit H, patch, path, identity, hash,
case or seed material.

Carrier `3e97243d96df1082246d06c1440c0e2c5480fe28` adds the pure
exact-five-block comparator. It applies the same single-arm oracle to all ten
supplied arms, computes the five frozen joint signs and the cross-block
replay/`U_F` guard inside one private in-memory boundary, and returns aggregate
counts, ratios, signs and availability values only. It emits no GO token and
creates no population, command or launch authority.

Carrier `042da9e88d1e85eca4a0a431cd187c5eaae2e3fb` adds the default-off
`initial_screening_only_v1` boundary. Every returned initial Protocol and
unchanged Decision is durably recorded before the candidate is parked and its
candidate authority is cleared; the next attempt starts from fresh B0, and the
mode dispatches no expanded, validation or frozen stage. Carrier
`8b7b59886ad0ae6b10f2f672df24ecebd66270da` closes the initial-only signal,
workspace and post-return accounting races so typed interruption remains
incomplete without leaving candidate authority. Neither carrier exposes a CLI
mode or creates live launch authority.

Carrier `a8e483bb285fb49b3482c797e93792d013470db3` adds summary-only,
ordinal paired-effect cells for any canonical complete screening row, in that
row's case-major/seed-minor order. It projects only candidate and B0
`total_distance` values; it emits no case, seed, path, H, patch or raw-metric
body. Only the later strict adapter interprets those cells as initial evidence
after joining an initial-only, unexpanded row to its attempt; pre-outcome order
and control authority remain a later manifest gate. Carrier
`acff2f0ac3b5f9a8a7c7d56a23f200ca4fd9449e` adds a private strict adapter that
decodes all ten supplied roots before comparison, joins status, summary,
history, attempt telemetry, branch inventory and ordinal cells, and delegates
only structurally valid initial-only roots to the existing single-arm and
five-block oracles. Its errors remain fixed and body-free.

Carrier `4256c190ccf3d75c492ed81c18dcb97ef3072286` adds the private safe-path
adapter. It reads only literal `status.json`, `campaign_summary.json` and the
optional canonical `research_history.jsonl` from ten distinct canonical root
directories, using bounded no-follow regular-file reads, strict UTF-8/JSON and
JSONL decoding, non-alias checks and sequential revalidation. It establishes
detached captured-byte integrity; it does not establish an atomic simultaneous
ten-root snapshot, current-at-return freshness, pre-outcome control equality or
population authority. Expectations and loaded-history controls are still
private caller declarations at this boundary.

Carrier `f2fd0053e5cb5ed5e880c7e369b3141a9c600d2a` adds the package-private,
default-off `CONFIG_SUBSET_ONLY` pre-run
`initial_screening_study_controls.json` snapshot. Before other campaign-root
side effects it detaches and normalizes the bounded qualification,
code-research, resource, scheduler and Protocol subset, writes the private
snapshot, installs those same detached objects at the finite reviewed direct
seams, and gates `run` on exact publication, installed joins and pristine state
before preflight. Its 203 focused tests passed, and independent science/privacy
and red-team review reported P0/P1/P2 = `0/0/0`. This is pre-run
configuration-subset evidence only, not proof of actual execution or
enforcement throughout the run.

Carrier `94455954aceced50d31a943cf3185290edb813f4` adds one package-private,
default-off, manifest-path-only validator that returns only the fixed
`CONFIG_SUBSET_JOINED` mapping, including the exact ordered 20 limitations. The caller
supplies only the absolute manifest path; all history and root locators are
manifest-owned relative POSIX tokens resolved beneath a held manifest-parent
bundle. The manifest is the sole source of the exact five ordered block
expectations and five typed loaded-history declarations. The validator
normalizes all five declarations and reads and canonically normalizes every
available basis file before opening any outcome root. It distinguishes
known-empty available history from typed unavailable history and shares one
normalized basis between the K=1 and K=2 arms in each block.

The validator then reads ten distinct bounded six-leaf artifact surfaces:
`status.json`, `campaign_summary.json`,
`initial_screening_study_controls.json`, `code_research_limits.json`,
`resource_envelope.json` and optional `research_history.jsonl`. Each
manifest-declared controls projection exactly joins the corresponding root
snapshot; the snapshot's overlapping code-research and resource subsets exactly
join the two independent files. Common controls are exact-equal across all ten
arms, with only K and the eight manifest-declared population paths varying
across blocks. After all joins, one fresh absolute bundle pass revalidates the
manifest, history files and all ten roots, followed by a second fresh absolute
manifest-only rewalk. All ten roots then pass through the S2a structural
decoder; the ten decoded values are discarded, and the loaded bases are not
passed to S2a or treated as proof of runtime consumption. The 97 focused
manifest tests, 523 adjacent tests and 438 postrun tests passed. The wrapper
does not call or pass through the D2 scorer, D3 comparator or their endpoints
and creates no matched result, population, live authority or GO token.

Carrier `7ad892eb303cae035edc35b1360dbb9b1d1e3b6a` adds a separate
package-private, default-off, producer-only requested-provider-policy boundary.
It is valid only beside the existing S2c1 opt-in and publishes
`initial_screening_provider_policy.json` as an independent second private leaf
with scope `REQUESTED_PROVIDER_POLICY_ONLY`. It binds the exact existing
`LLMClient` shared by the reviewed Creative/ProviderCaller consumers to one
immutable capsule whose table contains exactly the five reviewed request
kinds, then gates run on both private leaf publications, the same-client joins
and pristine state before preflight. Its 313 focused and 1,036 adjacent tests
passed; the sole adjacent failure was the pre-existing hard-coded
15-versus-16 research-history count debt, and independent science/privacy and
red-team review reported P0/P1/P2 = `0/0/0`.

This is requested local-policy evidence, not a statement about the actual
remote backend, account or credential identity, served model, process
network/TLS environment, request code constants, SDK retry or timeout
enforcement, or `LLMClient` lifetime freshness. Its exact limitations retain
those boundaries as
`PROVIDER_CREDENTIAL_AND_ACCOUNT_IDENTITY_UNVERIFIED`,
`PROVIDER_PROCESS_NETWORK_TLS_ENVIRONMENT_UNVERIFIED`,
`REMOTE_PROVIDER_BACKEND_IDENTITY_UNVERIFIED`,
`PROVIDER_REQUEST_CODE_CONSTANTS_UNVERIFIED`,
`PROVIDER_TIMEOUT_AND_SDK_RETRY_ENFORCEMENT_UNVERIFIED` and
`LLM_CLIENT_LIFETIME_FRESHNESS_UNVERIFIED`; they also retain
`STUDY_MANIFEST_UNVERIFIED` and `ROOT_LIFETIME_FRESHNESS_UNVERIFIED`, while
`MATCHED_RESULT_UNAUTHORIZED`, `LIVE_EXECUTION_UNAUTHORIZED` and
`STUDY_GO_UNAUTHORIZED` remain in force.

Carrier `8560a892cac3e540ed4862ee209eaa2640ccba38` adds a wholly separate,
package-private, validation-only v2 manifest boundary. Its top-level manifest
contains one common `declared_provider_policy` intended to be frozen before
outcomes; the validator does not prove its Git, commit or write timing. Each of
the ten ordered roots must expose `initial_screening_provider_policy.json` as
its seventh private leaf. The validator independently normalizes the frozen
provider-policy v1 grammar and requires both the raw canonical bytes and the
normalized value of every leaf to equal the single declaration, with no K or
population mask. It normalizes all five typed history declarations and reads
and canonically normalizes every available basis file before any root,
preserving the distinction between known-empty available and typed unavailable
history. It reads all seven leaves for each root through one held root
descriptor, includes the new leaf in bounds, non-alias checks and the full
fresh bundle rewalk, then performs the second manifest-only rewalk. Only after
those joins and rewalks does it run all ten S2a structural decodes, whose values
are discarded.

The sole success is the fixed private
`CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOINED` mapping with its exact
ordered 25 limitations. This v2 removes only
`PROVIDER_REQUEST_POLICY_UNVERIFIED`; it retains
`STUDY_MANIFEST_UNVERIFIED`, the credential/account, process network/TLS,
remote-backend, request-code-constant, timeout/retry-enforcement and client
lifetime limitations, both runner and external-hardwall enforcement
limitations, and the matched/live/GO prohibitions. Its 85 focused tests, 405
combined v1/v2 manifest/root tests and 523 full postrun tests passed; an
independent 1,216-case producer-versus-decoder differential had zero
mismatches, and science/privacy and red-team review reported P0/P1/P2 =
`0/0/0`. The S2c1 controls v1 and S2c2 manifest/join v1 bytes and meanings are
unchanged: v1 still returns `CONFIG_SUBSET_JOINED` and retains
`PROVIDER_REQUEST_POLICY_UNVERIFIED`.

Carrier `1b967d938c1c3956a7024d0c9d0aeb35833fef52` adds another separate,
package-private, default-off, producer-only boundary. It requires both the
S2c1 controls and S2c3 requested-provider-policy opt-ins and publishes
`initial_screening_problem_spec.json` as the third private control leaf, after
the controls and provider-policy leaves. Its scope is
`PROBLEM_SPEC_DECLARATION_ONLY`. The leaf contains a canonical normalized
projection of exactly 30 of the current 31 `ProblemSpecV1` model fields:
`root_dir` is deliberately excluded. Before the first campaign-root leaf is
written, the boundary reconstructs a fresh `ProblemSpecV1`, mechanically
bridges it to a fresh legacy ProblemSpec, and constructs a fresh instance of
the already-loaded exact adapter class. The pre-first-leaf gate validates the
provisional five-object graph: controls runtime inputs, `ProblemRuntime`,
`ContractGate`, Protocol and `VerificationGate`. After the remaining services
are constructed, registration first validates the full installed reviewed
seams, including the materializer, evaluator, proposal and evidence consumers.
At run start, the gate revalidates all three publications and the full
installed joins before preflight.

The declaration's exact ordered 11 limitations are
`PROBLEM_ADAPTER_UNVERIFIED`, `RESEARCH_INPUT_UNVERIFIED`,
`RUNTIME_RESEARCH_HISTORY_CONSUMPTION_UNVERIFIED`,
`VERIFICATION_CONFIG_AND_RUNTIME_UNVERIFIED`, `SOURCE_CARRIER_UNVERIFIED`,
`B0_CONTENT_UNVERIFIED`, `STUDY_MANIFEST_UNVERIFIED`,
`ROOT_LIFETIME_FRESHNESS_UNVERIFIED`, `MATCHED_RESULT_UNAUTHORIZED`,
`LIVE_EXECUTION_UNAUTHORIZED` and `STUDY_GO_UNAUTHORIZED`. Its 42 focused and
321 combined tests passed, and independent science/privacy and read-only
consistency review reported P0/P1/P2 = `0/0/0`.

This carrier proves only that the root-dir-excluded normalized declaration was
mechanically bridged and installed at the reviewed local seams. It does not
prove adapter behavior, freshness after the run gate, research input or
runtime research-history consumption, verification behavior or runtime
enforcement, the source carrier or B0 content, manifest timing or joins, a
matched result, population, live authority or GO. The S2c1/S2c2 manifest v1
and S2c4 manifest v2 schemas, loaders, results and limitations are unchanged;
joining this new declaration and third control leaf across ten roots requires
a separate future v3 rather than an implicit upgrade of either existing
manifest boundary.

Together these carriers implement and audit K=2, telemetry, initial-only
retirement, ordinal cells, decoded study structure, safe root loading and the
pre-run configuration subset plus its first manifest/root/independent-file
join, a separate requested-provider-policy producer, the private v2 join and a
separate producer-only ProblemSpec declaration.
Tests include provider-/solver-free actual-writer roundtrips as well as
synthetic interruption and mutation matrices; they do not select a population,
execute a matched experiment or show that K=2 improves CVRP research.

## Provider- and solver-free measurement baseline

### Fixed units and notation

The experimental unit for later inference is one matched block, not a provider
call, candidate, case or case-seed pair. Every block score is computed against
the common history snapshot frozen for its two arms and outputs earlier within
that block only. An earlier M32 block never changes a later block's endpoint;
cross-block replay is a separate final guard and does not enter the sign
statistic. Within one arm of one block:

- `A_cap` is the fixed maximum number of proposal-attempt slots;
- `P_cap` is the fixed shared provider-call allowance;
- `P_charged` is every budget-admitted H, H-research, C, C-research, C-final or
  other provider request, including calls followed by invalid output,
  rejection or abstention;
- `H` is the number of complete H values selected from the session and exported
  to Hypothesis Contract;
- `D_H` is the number of those selected H values that are exact-distinct from
  that block's frozen loaded history and from earlier selected H values in the
  same arm of the same block;
- `C_ready` is the number of selected H values that produce a complete ordered
  patch which passes Patch Contract and can be materialized in an isolated
  workspace;
- `F` is the number of candidates whose selected H itself contributes to
  `D_H`, whose selected-H plus canonical ordered-patch pair is also
  exact-distinct from that block's frozen loaded history and from earlier such
  pairs in the same arm of the same block, and which pass Contract,
  Verification and canary and are actually dispatched to initial Protocol;
  and
- `G` is the number of those `F` candidates that complete the exact initial
  matrix, have zero failed-pair classes and zero fleet regression, and receive
  the unchanged `expand / expand_screening` Protocol/Decision progression.

Exact-distinct comparisons use the already ordinary selected H and ordered
patch values in a provider-/solver-free postrun computation. A loaded-history
replay may contribute to the physical `H` and `C_ready` stage counts, but it
cannot contribute to `D_H`, `F` or `G`, even if paired with a different patch.
An exact H+patch pair replay is independently disqualifying for `F` and `G`.
A value repeated within an arm's later attempt in the same block follows the
same rules. Both replay classes are counted by the fixed replay guards. The same
output in the opposing arm is scored independently against that arm's
identical frozen inputs, so arm order cannot decide novelty. The computation
emits counts only. It creates no durable candidate identity, digest, hash,
receipt or ledger. Unselected K=2 drafts never participate because they never
leave the tainted session.

### Frozen endpoints

| Class | Endpoint | Exact definition |
| --- | --- | --- |
| Throughput, primary | `T` | `F / P_charged`; define `0` when `P_charged=0` |
| Throughput, fixed-budget guard | `F / P_cap` | Prevents a favorable ratio caused only by early unused allowance |
| Attempt yield | `F / A_cap` | Distinct formal candidates per declared attempt slot |
| H productivity | `H / P_charged` | Selected exported H per all charged provider calls |
| H diversity | `D_H / A_cap` | Exact-distinct, non-replayed selected H per attempt slot |
| C readiness | `C_ready / max(H, 1)` | Contracted, workspace-ready patch rate from selected H |
| Quality, primary | `Q` | `G / max(F, 1)`; an arm with no formal candidate has `Q=0` |
| Quality-bearing yield | `G / A_cap` | Joint diagnostic, not a substitute for separate `T` and `Q` |
| Replay guards | fixed-denominator rates | loaded-history and within-block same-arm exact selected-H replay and exact H+patch replay divided by `A_cap` |
| Failure guard | fixed-denominator rate | candidates with any candidate-only runtime failure divided by `A_cap` |

After all five blocks terminate, a separate study-wide guard computes, for
each arm, exact selected-H and exact H+patch repeats against earlier M32 blocks.
Each rate uses the sum of that arm's five declared `A_cap` values as its fixed
denominator. The audit also computes `U_F`, the number of exact-distinct formal
H+patch pairs across all five blocks after excluding each pair against its own
block's frozen loaded-history basis.
These quantities do not alter any block score. A GO additionally requires both
cross-block replay rates for K=2 to be no higher than K=1 and
`U_F(K=2) > U_F(K=1)`. Thus one exact candidate repeated across blocks cannot
by itself produce GO.

Every formal candidate also retains candidate-level case win/loss/tie, pair
win/loss/tie, paired-effect median/interval, completeness and failure-class
facts. For the frozen paired-effect guard, compute each complete initial cell as
`(candidate_total_distance - B0_total_distance) / B0_total_distance`; lower is
better. A nonpositive or nonfinite B0 distance or a nonfinite candidate
distance makes the block unscorable rather than being imputed. For a sorted
finite multiset, its median is the middle value when its size is odd and the
arithmetic mean of the two middle values when its size is even. Take that
median across cells for each candidate, then apply the same rule across all
`F` candidate medians in an arm. A candidate with any candidate-only failure,
incomplete initial matrix or fleet regression receives `+infinity`; if either
middle value in an even median is `+infinity`, the result is `+infinity`; an
arm with `F=0` also has `+infinity`. Call the resulting scalar `E`. K=2 is not
worse only when `E_2` is finite and either `E_1` is `+infinity` or
`E_2 <= E_1`. This median-of-candidate-medians diagnostic is not a claim about
the full paired-effect distribution and never enters Decision.

Analysis must not flatten case-seed cells into independent replicates, omit a
failed candidate or select the best candidate after outcomes.

An abstention, research rejection or invalid H/C consumes its charged calls
and attempt slot but contributes no `H`, `F` or `G`. A loaded-history or
within-block replay consumes its charged calls and attempt slot and may reach
the physical `H` or `C_ready` boundary, but contributes no `D_H`, `F` or `G`.
A candidate-only failure contributes to its guard and cannot contribute to
`G`. A shared infrastructure failure is not converted into a candidate-quality
failure.

### M30 calibration row

A synthetic golden fixture reproduces the published ordinary/sanitized M30
accounting row without reading or rescoring the preserved M30 root:

- `A_cap=6`, `A_used=3`, `P_cap=60` and `P_charged=25`, with 19 H-research
  turns, five C-research turns and one independent C-final call;
- `H=1`, `C_ready=1`, one physical candidate reached initial Protocol and no
  candidate earned `G`;
- physical formal dispatch was `1/3` per used attempt and `1/25` per charged
  provider call, while its fixed-envelope diagnostics were `1/6` and `1/60`;
- within-campaign selected-H and H+patch duplicate counts are zero because only
  one value reached each boundary; history-relative replay is unavailable from
  the frozen aggregate terminal and must not be inferred;
- initial quality rate is `0/1`; and
- the sole formal candidate completed `6/6` valid pairs with zero failed-pair
  classes and zero fleet regression, then failed
  `SCREENING_FAIL_CASE_QUALITY` and continued exploration.

Because history-relative replay is unavailable, the M32 endpoint values
`D_H`, `F` and the associated distinct-yield ratios are not recoverable for
M30; the physical formal count must not be substituted for them. This
resource-incomplete row checks charged-call, attempt and physical-stage
denominators only. It is not a K=1 matched control, a population estimate, a
K=2 counterfactual or evidence that a candidate bank works. No missing
historical draft or replay count may be inferred from provider traces or
reconstructed from raw bodies.

### Offline implementation status

Provider-/solver-free tests now prove:

- absent K configuration and explicit `K=1` preserve the current bounded H
  path wherever its public schema is unchanged;
- `K=2` is default-off and the only additional accepted value;
- two slots share one H-session turn/read/search/transcript/provider budget,
  and staging a second slot resets or enlarges none of them;
- a slot accepts one complete immutable structured H, and the terminal result
  must be either an explicit typed abstention or a selected ordinal that
  exactly equals one existing slot;
- only the selected H reaches Contract; unselected slots disappear without a
  StepRecord, lineage, history, workspace, public body or candidate authority;
- provider request-kind totals sum exactly to `P_charged` at intermediate and
  terminal projections;
- invalid payloads, duplicate staging, attempted overwrite, a terminal result
  that is neither typed abstention nor valid selection, transport interruption
  and every resource boundary fail closed;
- synthetic postrun fixtures reproduce every implemented single-arm endpoint
  and reject double-count, replay-denominator, missing-row and
  candidate/shared-failure mutations; and
- the exact-five-block comparator applies that same single-arm oracle to all ten
  supplied arms, fails closed on incomplete or unscorable blocks, and emits
  only the frozen aggregate block signs and cross-block guards.

The exact-five-block comparator now supplies the previously missing offline
reducer. The body-free single-arm reports remain intentionally insufficient to
reconstruct cross-block replay or `U_F`; the comparator receives already-decoded
ordinary H and ordered-patch evidence for all ten supplied arms at once,
compares those values only transiently, and never emits an identity, hash,
digest, path or body. Its implementation and independent review establish only
offline accounting, claim fencing and non-persistence. Later study-root tests
exercise actual campaign artifact writers without a provider, solver, raw case
population or live study; they remain implementation evidence, not a real
matched study or research-effectiveness evidence.

## Future matched development study

### Fixed repeated-block gate

The minimum confirmatory design is exactly five matched blocks. Each block has
one explicit `K=1` arm and one explicit `K=2` arm. All five blocks are frozen
before any outcome and analyzed once after all five pairs reach their declared
terminal.

Five strict same-direction wins are the smallest exact sign gate below 0.05:
under independent exchangeable block signs and a no-advantage null, the one-sided probability is
`1/2^5 = 0.03125`. Four or fewer blocks cannot meet that boundary. This is a
conservative internal advancement rule, not a global population-inference or
generalization claim.

There is no interim analysis, success stop, optional extension, favorable-block
selection or post-outcome endpoint substitution. A later decision to tolerate
one inconsistent block would require a new pre-outcome design with at least
eight blocks and at least seven joint wins; it cannot amend this five-block
rule after any M32 outcome.

### Exact arm match

Within each block, the two arms must have the same:

- source carrier, model and provider settings;
- safe problem/source context, frozen starting observation/history snapshot,
  prompts and current cross-attempt feedback behavior;
- `A_cap`, `P_cap`, H/C turn, read, search, token and tool limits;
- development-action, Contract, Verification, canary, formal-stage, solver and
  outer-hardwall limits;
- development cases, seeds, time bands and comparison baseline; and
- stop, cleanup, artifact and claim rules.

The only study variable is `max_hypothesis_candidates=1` versus `2`. Unused
allowance never transfers between arms or blocks. K=2 receives no additional H
turn, transcript, read, search, C or provider budget for its second slot.

Exact numeric solver and hardwall limits cannot be computed until a future
implementation and metadata-only population rule are frozen. The live
preregistration must derive worst-case arithmetic mechanically and give both
arms byte-equal resource controls. M30's six-attempt/60-call envelope is a
historical reference, not inherited launch authority or a silently chosen M32
budget.

Arm order must be outcome-blind and as balanced as five blocks allow. Both arm
commands and their order must be frozen before the first call, and no result
may be inspected between paired arms. Each arm may see its own ordinary prior
attempts, exactly as the current bounded path does, but neither arm may see the
other arm's outcomes or any earlier M32 block outcome.

### Avoiding a success-cost confound

A candidate that earns `expand_screening` must not consume resources that make
later proposal attempts unreachable only in the more successful arm. Two
candidate shapes were considered:

1. an initial-development diagnostic boundary that records the unchanged
   Protocol and Decision result and stops without dispatching expansion; or
2. an envelope that reserves the full worst-case initial-plus-expanded cost for
   every possible formal candidate in every attempt.

M32 selects the first shape. Carrier
`042da9e88d1e85eca4a0a431cd187c5eaae2e3fb` implements the default-off
initial-development diagnostic boundary: after initial Protocol and the
unchanged Decision are durably recorded, it parks and clears that candidate and
continues the next declared attempt from fresh B0. It never dispatches expanded
screening, validation or frozen stages, and a favorable initial result does not
reduce later proposal-attempt opportunity. Carrier
`8b7b59886ad0ae6b10f2f672df24ecebd66270da` hardens its asynchronous terminal
cleanup. These are production-boundary implementations and tests, not a live
study or promotion authority. The second shape is not the M32 design; adopting
it would require a new pre-outcome review. A stage or resource cap that lets
strong candidates crowd out later attempts is not an acceptable matched design.

### Terminal and replacement rules

Abstention and ordinary research rejection are research outcomes and are never
replaced. Provider, H/C turn, solver or hardwall exhaustion after scientific
delegation remains typed incomplete; it is not scored as a scientific negative
or silently imputed as zero. Any incomplete paired arm prevents an M32 positive
claim. Selective retry, resume or replacement is forbidden.

If a future preregistration permits reserve blocks, it must freeze their count
and outcome-blind selection before launch. Only a typed integrity or
infrastructure failure before scientific delegation may replace an entire
pair. No reserve identity or rule is materialized by this design.

## Outcome-blind population rule

This design selects nothing. A later preregistration may materialize a
population only after the final K=2 implementation carrier exists and has
passed independent provider-/solver-free review. That rule must ensure:

- five mutually disjoint fresh-at-start development populations;
- exact equality of cases, seeds and time bands between the two arms of each
  block;
- metadata-only selection from a declared universe with canonical path and
  seed handling;
- exclusion of prior outcome-exposed development cells and every
  validation/frozen/retained/reserved held-out cell;
- distinct development and canary seeds, with canary evidence unavailable to
  H/C and never used as a quality endpoint;
- no cross-block outcome ingestion during the study; and
- one frozen selector replay and independent review before any authorization.

No case, seed, rank, digest, salt, identity, label or reserve is created here.
Validation, frozen and retained stages remain zero for M32.

## Joint acceptance rule

For block `b`, let subscripts `1` and `2` denote K=1 and K=2. A block is a
strict joint win only when all of the following hold:

1. `F_2 > F_1` and `T_2 > T_1`;
2. `Q_2 > Q_1`;
3. the frozen median-of-candidate-medians paired-effect scalar `E` is not worse
   for K=2;
4. exact selected-H replay, exact H+patch replay and candidate-only failure
   rates are each no higher for K=2; and
5. K=2 introduces no feasibility or fleet regression.

A tie on either primary endpoint is not a win. Repeated output of one exact
candidate cannot increase `F` within a block; repetition across blocks is
caught by the separate study-wide guard. Because `Q_2 > Q_1` is required
independently of `F_2 > F_1`, producing more weak formal candidates cannot
satisfy the joint gate.

M32 advances only on `5/5` completed, valid strict joint wins **and** the
study-wide cross-block replay/diversity guard. The global guard only makes the
`5/5` sign gate stricter; it does not redefine a block sign or create an
additional replicate. One favorable candidate, a pooled-only improvement,
throughput-only uplift, quality-only uplift, one tied block or any guardrail
regression is `NO_GO`. Five completed valid blocks without the `5/5` joint wins
and global guard are a bounded valid negative and block M33. An incomplete
study is inconclusive and also grants no advance.

## Claim boundary

1. **Framework.** Offline tests may establish exact accounting, shared-budget
   enforcement, default preservation and unselected-draft non-persistence.
2. **Research direction.** A `5/5` result would support only repeated bounded
   development research-effectiveness evidence for K=2 under the exact frozen
   model, prompt, history, population rule and resource envelope. It may permit
   preparation of M33.
3. **Algorithm and acceptance.** M32 cannot establish algorithm improvement,
   mechanism causality, validation or frozen performance, promotion, retained
   improvement, production readiness, global CVRP generalization, CVRP
   acceptance or v0.4 completion.

Throughput-only uplift is research-throughput evidence, not effective-research
evidence. This design does not authorize M33, M34, M35, M36 or any new CVRP
qualification; every later rung remains conditional on its own reviewed
preregistration and explicit authorization.

## Completed audit prerequisites and remaining gates

The default-off initial-development boundary, ordinal-only initial-cell
producer, strict decoded ten-root audit, private safe root loader and private
configuration-subset snapshot are now implemented and independently reviewed
in carriers `042da9e8`, `a8e483bb`, `8b7b5988`, `acff2f0a`, `4256c190` and
`f2fd0053`. Carrier `94455954` adds the first strict manifest/root/independent
file join for that configuration subset. The manifest loader remains private
and validation-only: its ten S2a decodes are discarded and it never invokes D2,
D3 or either endpoint. There is no public audit or GO export, population,
matched result, CLI or live authority.

Carrier `7ad892eb` adds the separate producer-only
`REQUESTED_PROVIDER_POLICY_ONLY` leaf, same-client immutable capsule and
pre-run gate; it does not upgrade either earlier schema or join. Carrier
`8560a892` adds the separate validation-only v2 described above, reads the
seventh leaf from every root and requires one exact common policy before
returning `CONFIG_SUBSET_AND_REQUESTED_PROVIDER_POLICY_JOINED`. The S2c1
controls v1 and S2c2 manifest/join v1 remain byte- and meaning-compatible,
continue to return their old status and retain
`PROVIDER_REQUEST_POLICY_UNVERIFIED`; only the separate v2 removes that one
limitation.

Carrier `1b967d93` adds the separate producer-only
`PROBLEM_SPEC_DECLARATION_ONLY` leaf. It projects 30 of the exact current 31
`ProblemSpecV1` fields, excluding `root_dir`, then installs a fresh mechanical
legacy bridge and a fresh already-loaded exact adapter at the reviewed local
seams. Its pre-first-leaf gate validates the provisional five-object graph;
post-construction registration first validates the full installed seams; and
the run gate revalidates all three leaf publications and those full joins.
This is not a manifest join and does not upgrade the v1 or v2 schemas. A
separate future v3 must declare and join the ProblemSpec leaf across all ten
roots. The exact 11 declaration limitations continue to
exclude adapter behavior, post-gate freshness, research input and runtime
history consumption, verification, source/B0, manifest, matched, live and GO
claims.

Before any live preregistration, the remaining gates are to:

- commit and independently review the actual ordinary manifest in Git, and
  separately freeze and externally review its five private history bases before
  the first outcome. The bases remain private/transient and are referenced only
  through manifest-owned relative POSIX locators, with no caller history-path
  injection and no claim that their body-bearing files are Git-tracked. The
  validator does not prove Git identity, commit timing, absence of M32 outcome
  ingestion, population freshness or actual arm launch order;
- extend the generic controls beyond the now-joined bounded qualification,
  code-research, resource, scheduler, Protocol and requested-provider-policy
  subset. The normalized root-dir-excluded ProblemSpec declaration now has a
  producer-only local installation boundary, but it is not joined by either
  manifest version and does not prove adapter behavior. A separate v3 must
  join it. Actual research-input/history consumption, normalized
  requested/resolved solver and verification configuration, declared
  hardwall cap and launcher configuration, and source/B0 content and order
  remain unproved; source revision remains an external ordinary fact, not
  Scion authority.
  Runner/backend runtime enforcement and external hardwall enforcement remain
  unverified under
  `PROTOCOL_RUNNER_BACKEND_AND_RUNTIME_ENFORCEMENT_UNVERIFIED` and
  `EXTERNAL_HARDWALL_ENFORCEMENT_UNVERIFIED`. Remote backend/account/credential
  identity, network/TLS environment, request code constants, timeout/retry
  enforcement and client lifetime freshness also remain unproved; there is no
  actual-backend, served-model or enforcement claim;
- preserve the implementation order: after the completed seventh
  provider-policy leaf and all-ten exact-common join, finish source/B0,
  requested/resolved solver and verification,
  declared-hardwall/launcher and other full-control joins; then add a gated
  comparator schema exercised only on synthetic inputs; then select an
  outcome-blind metadata-only population; and only then mechanically freeze the
  study-specific cases, seeds, time/resource arithmetic, actual ordinary
  manifest and launch order before
  independent review and any separate live authorization. Implementing
  comparator code before metadata-only population selection does not freeze
  those missing values or the actual study manifest, and none of the generic
  joins proves runtime enforcement;
- keep the control snapshot unreachable from H/C prompt, read and search
  surfaces, and keep the manifest/control postrun loader private. Body-bearing
  history bases remain private/transient and are not Git-tracked;
  identity-bearing manifest/control data is confined to the reviewed private
  manifest and in-memory loader. This carrier projects no manifest, control or
  history identity/body into its fixed return/error and adds none to status,
  prompt or history; the existing ordinary ProtocolResult/summary case/seed
  projections remain unchanged. Add no self-hash, receipt, nonce, GO token,
  preauthorization or claim that Scion proves preregistration timing;
- freeze exact numeric resources from the final implementation and population
  metadata;
- freeze an outcome-blind five-block population and arm order without exposing
  held-out data;
- obtain independent science/privacy and runtime/resource reviews; and
- obtain separate explicit live authorization.

Until all gates pass, M32 remains design-only and no live command exists.

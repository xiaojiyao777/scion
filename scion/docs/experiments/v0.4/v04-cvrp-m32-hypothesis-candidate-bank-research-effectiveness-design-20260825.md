# CVRP M32 continuous-research and history-effectiveness reset

Status: **DESIGN ONLY / NO MATCHED RESULT / NO CVRP PROMOTION**

Revised: `2026-08-28`

This document replaces the abandoned S2c authority/manifest plan. Those
controls, private leaves, study roots, qualification-only mode and carrier
reconstruction have been deleted. They are not prerequisites for this study.
Historical detail remains available in Git.

## Why the question changed

M30 made 25 charged provider calls and exported one formal candidate. The
candidate completed 6/6 initial pairs but had median delta `-5.5` and failed the
fixed quality rule. Earlier CVRP campaigns contain useful positive and negative
research branches, yet no candidate has survived the full held-out funnel.

The immediate question is therefore not whether another local proof layer can
certify a short run. It is whether Scion's agent can use ordinary prior research
to produce more distinct, testable and useful algorithm proposals without
increasing invalid, infeasible or timeout-prone candidates.

K=2 remains a legitimate optional Creative strategy, but comparing K1 with K2
at the same time as changing history would confound two mechanisms. The first
causal study fixes K=1 and varies history only. K2 can be studied later or used
in the long campaign if independent proposal-yield evidence supports it.

## Architecture boundary

- CVRP enters through its problem adapter. Scion core contains no CVRP target
  ranker or mechanism selector.
- The agent receives the complete current safe source inventory and, in the ON
  arm, the complete ordered canonical H-only history inventory.
- `search_history` and `read_history` are optional agent actions. The host does
  not select a nearest record, force a read, force a citation or reject H merely
  because history was not used.
- A history ref included in `nearest_prior_refs` must have been read in that
  session and must also occur in `read_refs`.
- History is proposal context only. It cannot enter Contract outcomes,
  Verification, Protocol, Safe Features, Decision or scheduling.
- Validation/frozen/final evidence is not included in proposal-visible history.
- H and C remain tainted and pass through the unchanged Contract, isolated
  workspace, Verification, paired Protocol and deterministic Decision path.
- Provider SDK retries are zero. Every deliberate research turn is charged to
  the shared provider-call cap.

No manifest closure, object identity, lease, issuer, registration, receipt,
freshness proof, candidate carrier or GO token is part of the design. Each run
uses a fresh ordinary output directory and records status, campaign summary,
research history, traces and raw Protocol metrics through the existing path.

## Study question

For a bounded CVRP development attempt using `gpt-5.6-sol`, does exposing the
agent to complete ordered prior H-only research improve:

1. distinct formal-H throughput per charged provider call; and
2. the chance that a formal candidate reaches the unchanged initial development
   quality outcome,

without materially worsening candidate-only timeouts, invalid output or
infeasibility?

All-deliberation history search/read counts are a manipulation check. History
refs and citations in the ordinary summary basis of the selected formal H are
the matched causal utilization endpoints; bases attached only to unselected
candidate slots never count for the executed H. Neither class is a success
endpoint, and reading or citing history alone proves no benefit.

## Matched design

Use exactly five blocks. Each block contains one `history OFF` arm and one
`history ON` arm.

Fixed within each block:

- original CVRP B0 source;
- problem adapter and all Contract/Verification code;
- local endpoint `http://127.0.0.1:8080`;
- model `gpt-5.6-sol` and the same reasoning effort;
- K=1;
- research question and source visibility;
- H/C turn, read, search, transcript, test and response limits;
- provider-call cap and outer hardwall;
- screening cases, seeds, order and solver time limits;
- Protocol and Decision configuration.

Every screening solver call has the same resolved 30-second limit. The study
protocol has no dimension-based time-limit rules; provider-/solver-free
preflight recomputes all 30 resolved limits and rejects any other value.

The sole arm difference is:

- OFF: no `--research-history` inputs;
- ON: the complete ordered canonical CVRP H-only corpus is supplied through the
  existing repeatable `--research-history` option.

Use all 16 current canonical history inputs in chronological order, spanning
M9 through M30 and omitting campaigns that produced no canonical history.
Together they contain 45 ordered records and fit the existing
file/record/byte limits. M28 and M30 are concatenated into one ordinary JSONL
input only to remain within the existing 16-file loader limit; record order is
preserved.
The exact paths must be frozen as ordinary study input before the first arm.

Arm order is counterbalanced before outcomes:

- blocks 01, 03 and 05: ON then OFF;
- blocks 02 and 04: OFF then ON.

Within a block both arms use the same development population. Across blocks use
fresh disjoint development populations where available, and record any
unavoidable reuse as a limitation. Populations cannot use validation, frozen or
reserved final cases.

The existing-case freeze is invalid. There are 10,344 local CVRPLIB cases:
the old full-result table covers 10,330, and all 14 remaining paths occur in
`reference_validation_bad.csv`. Literal fresh existing cases therefore equal
zero; none are eligible for this development study.

The replacement population is generated under the ordinary problem-data
namespace `scion_generated/cvrp_history_matched_v1`. Its generator is closed
over 30 fixed specifications and reads no historical source, solver output,
quality metric, gate, Decision or failure outcome. Each specification fixes
block, position, uniform/clustered/radial geometry, coordinate seed, dimension,
capacity, demand pattern and allowed routes. `bks` and `bks_routes` are null and
the namespace contains no solution file. A provider-/solver-free exact byte
regeneration check rejects missing, extra or changed inputs; every path must
also load through the CVRP adapter.

Capacity is 80. Each complete ten-customer constructive group has demands
`12,4,12,4,12,4,12,4,12,4`; a shorter tail repeats `(12,4)` and uses 8 for an
odd final customer. `allowed_routes=ceil(customer_count/10)`. Consequently the
declared id-order witness respects capacity and route count, best-fit-decreasing
packs the same fixed multiset within the cap, and the total-demand capacity
lower bound equals the cap. This prevents either arm from trading extra routes
for distance without a fleet-first penalty, without using a solver run to tune
or select an input.

Positions 0, 2 and 5 are respectively small, medium and large. The remaining
positions are fixed expansion cases. The table lists
`basename (dimension, structure)`; every basename is relative to the namespace
above.

| Block | 0 small | 1 expansion | 2 medium | 3 expansion | 4 expansion | 5 large |
|---|---|---|---|---|---|---|
| 01 | `block_01_pos_0_uniform_n0061_s41001` (61, uniform) | `block_01_pos_1_clustered_n0126_s41002` (126, clustered) | `block_01_pos_2_radial_n0241_s41003` (241, radial) | `block_01_pos_3_uniform_n0361_s41004` (361, uniform) | `block_01_pos_4_clustered_n0481_s41005` (481, clustered) | `block_01_pos_5_radial_n0721_s41006` (721, radial) |
| 02 | `block_02_pos_0_clustered_n0067_s42001` (67, clustered) | `block_02_pos_1_radial_n0137_s42002` (137, radial) | `block_02_pos_2_uniform_n0257_s42003` (257, uniform) | `block_02_pos_3_clustered_n0377_s42004` (377, clustered) | `block_02_pos_4_radial_n0497_s42005` (497, radial) | `block_02_pos_5_uniform_n0737_s42006` (737, uniform) |
| 03 | `block_03_pos_0_radial_n0073_s43001` (73, radial) | `block_03_pos_1_uniform_n0149_s43002` (149, uniform) | `block_03_pos_2_clustered_n0273_s43003` (273, clustered) | `block_03_pos_3_radial_n0393_s43004` (393, radial) | `block_03_pos_4_uniform_n0513_s43005` (513, uniform) | `block_03_pos_5_clustered_n0753_s43006` (753, clustered) |
| 04 | `block_04_pos_0_uniform_n0079_s44001` (79, uniform) | `block_04_pos_1_clustered_n0161_s44002` (161, clustered) | `block_04_pos_2_radial_n0289_s44003` (289, radial) | `block_04_pos_3_uniform_n0409_s44004` (409, uniform) | `block_04_pos_4_clustered_n0529_s44005` (529, clustered) | `block_04_pos_5_radial_n0769_s44006` (769, radial) |
| 05 | `block_05_pos_0_clustered_n0083_s45001` (83, clustered) | `block_05_pos_1_radial_n0173_s45002` (173, radial) | `block_05_pos_2_uniform_n0307_s45003` (307, uniform) | `block_05_pos_3_clustered_n0421_s45004` (421, clustered) | `block_05_pos_4_radial_n0547_s45005` (547, radial) | `block_05_pos_5_uniform_n0787_s45006` (787, uniform) |

Each arm uses `requested_rounds=2` in a fresh campaign root. This permits the
engine to spend multiple proposal attempts while exposing exactly two formal
screening-stage opportunities. If the first result is `expand_screening`, the
second opportunity evaluates the exact same candidate on the expanded screen;
otherwise the second opportunity may be a new formal hypothesis. The fixed
protocol requires expanded screening before a pass, so two opportunities can
never dispatch validation or frozen evidence. The study does not park or
reconstruct a candidate.

## Observations

The provider/solver-free postrun evaluator consumes ordinary decoded values:

- `status.json`;
- `campaign_summary.json`;
- the current run's `research_history.jsonl` when present;
- ordered hypothesis-research trace JSON values.

It reports separate endpoints only:

- charged provider calls;
- distinct formal H per charged provider call as an explicit descriptive ratio;
- formal proposal episodes;
- observed/distinct/replayed H episodes;
- observed/distinct/replayed H+patch episodes when ordinary summary/history
  order can be aligned;
- proposal-episode Contract and Verification pass/fail counts;
- screening, validation and frozen stage reach;
- Decision counts and promotions;
- maximum research depth by branch;
- first observed rounds for H, gates, stages and promotion;
- all-deliberation history search/read actions and references, separately from
  selected-H basis history refs/citations; selected-H basis coverage is explicit
  and incomplete coverage yields unavailable causal aggregates rather than zero;
- screening gate and statistical-status counts;
- total/attempted/valid/failed pair counts, candidate/champion/shared/bilateral
  attribution and explicit accounting/attribution/WLT completeness counts;
- two fixed screening-opportunity slots containing round, gate-outcome and
  statistical-status one-hot indicators, median delta, CI and case/pair W/L/T
  values, with unavailable values represented as `null`;
- standardized protected-objective-regression reason counts, including a fixed
  per-slot fallback flag when median/CI quality is unavailable;
- pair-level candidate-only timeout, invalid-output and infeasible counts, plus
  three separate rates over the same complete attempted-pair denominator;
  missing legacy numerators/denominators and a zero denominator yield `null`,
  with observed/missing opportunity counts exposed;
- diagnostic candidate failure-event classes: timeout, OOM, crash, process,
  invalid output, operator, policy, construction, portfolio, surface-contract
  and other; these event counts are not safety-rate numerators;
- normal solver `time_limit` stops separately from failed-process `timeout`;
- fixed terminal campaign status, requested/evaluated/scheduled counts, Protocol
  stage counts, typed execution outcomes, unknown outcomes, requested-round and
  outcome-accounting completeness, and ordinary run-validity projection.

Advancing the same exact candidate through expanded screening or a held-out
stage is not a new H replay. Re-proposing the same H after `continue_explore`
is a replay. If H+patch alignment is unavailable, the evaluator reports those
endpoints unavailable instead of guessing.

For each block, compare ON with OFF endpoint by endpoint. For each aggregate
endpoint, use only blocks where both arms are observable and report ON mean,
OFF mean, mean ON-minus-OFF delta and observed matched-pair count while
retaining the by-block values and `null`s. Do not collapse results into a
composite score or GO conclusion.

Primary derived ratios:

```text
T = distinct formal H episodes / charged provider calls
Q_expand = initial expand-screening outcomes / formal proposal episodes
Q_pass = initial queue-validate outcomes / formal proposal episodes
```

`Q_pass` may be structurally zero in this one-round design when the fixed
Protocol requires an expanded screen before validation. In that case
`Q_expand`, paired quality observations and failure classes are the meaningful
development endpoints; the analysis must state the limitation rather than
reinterpret the gate.

Safety observations remain separate:

- candidate-only failed-process timeout per attempted pair;
- candidate-only invalid solver output per attempted pair;
- candidate-only infeasibility per attempted pair;
- Contract or Verification rejection;
- reference/champion/shared failure class.

## Interpretation

Evidence favors history use only if the matched observations jointly show
better proposal throughput or development quality and no material safety
regression. Actual history use should be visible in at least some ON-arm traces;
if the agent never uses history, the study estimates availability rather than
the effect of consumed historical evidence.

A null or negative result does not justify forced history routing. It selects
`history OFF` for the next long campaign and motivates investigation of history
representation, search ergonomics or agent reasoning as separate hypotheses.

A positive result selects `history ON` for the next long campaign. It still does
not authorize promotion or expose held-out evidence.

## Long continuous campaign after the study

After the five blocks are terminal and analyzed, launch one fresh normal CVRP
campaign:

- same adapter, B0, fixed Protocol and Decision;
- `gpt-5.6-sol` through the local proxy;
- explicit provider-call cap and outer hardwall;
- history policy selected by the matched study;
- K=1 or K=2 chosen separately from proposal-yield evidence;
- up to three ordinary branches;
- multiple evaluated rounds, not a one-shot H/C cycle.

The scheduler must automatically reuse the exact candidate through
`screening -> validation -> frozen`. Only deterministic `PROMOTE` changes the
champion. If promoted, the exact snapshot then enters a separate no-LLM,
reserved-population comparison with original B0. CVRP acceptance requires that
independent retained result, not merely a positive development screen.

## Preconditions for spending budget

- adapter-only real CVRP composition passes;
- provider/solver-free regression passes from the local package root;
- the proxy credential can enumerate `gpt-5.6-sol`;
- the repository-local `vrp` data root is readable;
- all five block inputs, arm order and fresh output roots are frozen;
- no output root already exists.

Until these conditions hold, this document records design only and makes no
claim about history effectiveness, K2 effectiveness or CVRP improvement.

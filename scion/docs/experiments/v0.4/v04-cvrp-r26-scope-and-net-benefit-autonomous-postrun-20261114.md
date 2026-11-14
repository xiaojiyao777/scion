# CVRP R26 terminal audit: stronger executable research, no stable final advantage

Date: 2026-11-14. Profile: Experiment Analysis. This bounded audit supports the
requested framework-level retrospective; it proposes no support patch or new run.
The canonical entry pack, experiment index, runbook, postrun handoff, R26 frozen
design and R24/R25 postruns were read. Entry checkout was clean `c82b77ef`, equal
to local `origin/v0.4-dev`. All experiment tmux carriers were dead; R26's blank
exit-status field is not its scientific terminal evidence.

## Scope and terminal

Exact root:
`/home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028`.
[Status](/home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028/campaign_summary.json)
establish **completed / valid / requested_rounds_completed**, with final update
2026-10-29 06:30:25.896623 UTC / **October 29 14:30:25 Beijing**. Elapsed time
from the recorded launch is about 17h56m45s. This supersedes the startup wording
in the [frozen preregistration](v04-cvrp-r26-scope-and-net-benefit-autonomous-preregistration-20261028.md),
whose launch provenance and inputs remain unchanged.

- Twelve requested/evaluated screening stages; no validation or frozen stage.
- Thirteen scheduled steps: nine distinct evaluated H/C candidates, three
  expansions of those candidates, and one proposal-phase Code abandonment.
- Champion remains v1; no promotion or retained-improvement conclusion.
- All 324 executed pair rows / 648 solver sides are valid, with no recorded
  solver error, invalid solution or fleet violation.
- All 162 provider traces succeed on attempt 0: 83 H turns, 78 C turns and
  one C finalization. The 600-call envelope has 438 remaining calls; no quota,
  provider, global-resource, infrastructure or interruption outcome is recorded.
- Recorded formal elapsed times sum to 58,320.292 seconds, excluding canaries
  and development probes. This is not campaign duration.

No provider, solver or test was run by this audit. Original JSON/JSONL, traces,
source trees and SQLite were not changed; original SQLite was not opened. There
is no continuous host-load record proving absence of all external contention.
The frozen launch record supplies operator non-overlap evidence, not a complete
retrospective resource-isolation proof.

## Comparative science

Every stage compares its complete cumulative branch with **unchanged R22 C3**,
preserved as the R23 candidate and copied into R26 champion v1. It does not
compare directly with the preceding branch head, R23 A, or original B0.
Positive delta is comparator final distance minus candidate final distance.
Effect is the median of case medians; intervals below are the recorded 95%
bootstrap intervals.

|Step|Candidate/stage|Pairs|Case W/L/T|Pair W/L/T|Effect [CI]|Recorded result|
|---:|---|---:|---|---|---|---|
|1|A1 initial|20|1/0/4|2/0/18|0 [0,0.5]|fail practical-effect evidence|
|2|B1 initial|20|0/1/4|2/2/16|0 [-4,0]|fail case quality|
|3|C1 initial|20|0/1/4|2/2/16|0 [-1.5,0]|fail case quality|
|4|A2 initial|20|1/0/4|3/0/17|0 [0,21]|expand|
|5|A2 expanded|48|0/0/6|6/5/37|0 [0,0]|fail case quality|
|6|B2 initial|20|0/1/4|0/2/18|0 [-5.5,0]|fail case quality|
|7|C2 initial|20|1/0/4|3/1/16|0 [0,28]|expand|
|8|C2 expanded|48|0/2/4|6/11/31|0 [-4.25,0]|fail case quality|
|9|A3 initial|20|1/0/4|2/2/16|0 [0,13]|expand|
|10|A3 expanded|48|0/1/5|9/5/34|0 [-2.25,0]|fail case quality|
|11|B3 proposal|0|—|—|—|CODE_RESEARCH_ABANDONED|
|12|C3 initial|20|1/1/3|2/3/15|0 [-7.5,9]|fail case quality|
|13|A4 initial|20|1/1/3|3/4/13|0 [-30,7.5]|fail case quality|

The audit independently checked all declared Cartesian case/seed grids, valid
pair counts, raw final objective differences, pair signs, per-case medians,
aggregate medians and equality of recorded pair/side time limits. It reconciled
the summary's stage results with all twelve metric files. It did not rerun the
bootstrap procedure or independently execute Contract, Verification or Decision.
All evaluated proposals have recorded passing Contract/Verification/canary
results; expansion stages reuse their accepted candidate.

All twelve aggregate effects are zero. The descriptive total is 40 wins,
37 losses and 247 ties. This is **not** a pooled independent experiment:
expanded 6×8 stages rerun initial 5×4 cells, and ordinary autonomous execution
is champion-first rather than counterbalanced. Among the twenty repeated cells,
comparator outcomes change on 5, 4 and 8 cells for steps 4→5, 7→8 and 9→10;
candidate outcomes change on 1, 5 and 7. Fixed seeds therefore do not make these
wall-clock-bounded trajectories identical. No matched noise/power calibration
was collected; the existing diagnostic reports missing calibration, not a new
reason to override the recorded scientific decisions.

The three initial tai100a case signals (+21, +28 and +13) become 0, -8 and -4.5
on expansion. C2 also loses A54 by a median 0.5. Final C3 has tai100a +9 and
X513 -7.5; final A4 has tai100a -30 and X513 +7.5. B34, X351 and X190 have zero
case median at every stage. These observations give no stable whole-population
advantage; they do not establish that every individual mechanism is ineffective.

All 648 recorded progress rows return no worse than their own initial
post-local-search checkpoint. All 1,023 recorded best updates are retained or
improved upon at final return. No positive initial relative lead becomes a final
negative delta in this run. All 60 X513 pairs have zero ALNS iterations in both
arms. These are recorded solver-trajectory facts, not independent reconstruction
of every route or attribution to the exact changed kernel. They provide no basis
for another production best-return repair.

## Actual research and source continuity

Branch labels are local to this run:

|Branch|Cumulative research|Final complete head|
|---|---|---|
|A / `687315f3`|A1 exact solve-local SWAP* geometric ranking-record cache; A2 capacity-first lazy two-opt-star variants; A3 demand-compatible supplemental exchange candidates; A4 exact directed reversal-delta screening for ordinary intra-route two-opt|`candidate_workspaces/candidate-o2h39ri_`|
|B / `a67dafee`|B1 late best-depot-break cyclic rotation; B2 late relocate-and-reverse transition; B3 proposed moving extensions after SWAP*, then abandoned|`candidate_workspaces/candidate-5zsmyk1w` (B2)|
|C / `fe35fb40`|C1 late exchange of two two-customer blocks; C2 replaces that extension with two-route order-preserving interleaving/repartition fallback; C3 capacity-sparse DP for the same fallback|`candidate_workspaces/candidate-_3oqlabz`|

The initial 100 ordinary source files equal the declared complete R22 C3 source
at `/home/clawd/research/scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018/input_snapshots/candidate`.
Each final head contains those 100 ordinary files plus ten generated bytecode
files, which were left untouched. A differs from champion in local_search.py and
scheduler.py; B/C differ in local_search.py only.

All 395 non-null editable source bodies across 79 C contexts match the actual
session base. Approved H text matches the corresponding summary hypothesis.
Read-only in-memory application of the nine exported drafts reproduces all
three surviving 100-file heads exactly; all 48 Python files parse at each
candidate state. This is ordinary source comparison, not a new identity record
or executable historical candidate. The audit initially assumed every companion
edit was an exact replacement; handling the supported full-file scheduler edit
corrected that audit assumption without changing any experiment artifact.

A4/B2/C3 are **FULL_SOURCE_IDENTIFIED**. The six superseded evaluated candidate
trees do not survive in `candidate_workspaces/`; `archive/` and `workspaces/`
are empty. Their ordinary patch fallback is **PATCH_FALLBACK_IDENTIFIED**,
not a claim that original complete stage workspaces remain available. No new
executable fallback tree was created. Read-only/public-support bodies were not
independently compared in every C context in this audit, so the editable-source
check must not be generalized into a full public/private projection audit.

H actions comprise 38 source reads, 10 searches, 16 history reads, nine frontier
reviews and ten final hypotheses. All sixteen explicit history reads address
R26's current-run records, `history-0230` or later. Cross-campaign history was
available, and previous evidence also appears in the long question, so this does
not establish that earlier knowledge was ignored. H generally identifies the
actual inherited branch and distinguishes exact evaluator savings, added
neighborhoods, local gains and full-solver outcomes. C performs substantive
algorithm work; these are not merely commentary or no-op patches.

## Probe progress and limits

Fifteen submitted probes yield nine passes and six assertion failures. Every
evaluated candidate ends with a passing probe. All fifteen host development
check sets pass 5/5, a separate fact from optional falsifier success. Three tool
errors are recorded in terminal C contexts: one invalid empty query and two
missing exact-edit selectors. These are corrected or abandoned within the
research session; no formal candidate failure is hidden by the counts.

Step 11 consumes its local C turns, reaches finalization after a changed but
untested second draft, and explicitly chooses abandonment. Its explanation
correctly distinguishes unverified code from evidence that the hypothesis is
false. Global provider capacity remains available. This is useful evidence of
the current attempt boundary, not global resource exhaustion or a mandate to
extend that particular attempt after termination.

There is real progress beyond the deficiencies highlighted in R24/R25:

- A1's passing probe uses the real `baseline_algorithm.solve` on a four-customer
  synthetic instance, observes function frames without replacing callable
  identities, and explicitly asserts nonempty cache publications **and later
  hits**, repeated ordinary VNS calls and one solve-local map. Independent
  ranking-record comparisons and final feasibility/cost assertions also pass.
  This supports real integration/reuse on that fixture, not net performance.
- B1 corrects a failed short-string-closure expectation and passes an independent
  directed fixed-start rotation reference plus real full-registry VNS transition.
  Its final test uses a directed stand-in object; this is useful algorithm
  arithmetic evidence, not a complete symmetric production-solver gain claim.
- C2 independently enumerates tiny order-preserving interleavings and tests
  actual SWAP* behavior, singleton priority and interruption. C3 then compares
  capacity-sparse computation with independent tiny references and observes
  completed real no-winner fallback work. These establish local semantics at
  their tested scales; the large 0.2-second examples check deadline/feasibility,
  not completed large-scale fallback gains.
- A4's final passing probe calls the real solver on an 80-customer synthetic
  instance. Identity-preserving observation asserts actual new delta-screening
  execution, a nonempty live completed improving two-opt transition, subsequent
  completed ordinary work, feasibility and final distance no worse than the
  observed improved values. Earlier A4 probe failures are preserved. The final
  test establishes a real changed-path/retention witness; it does not compare
  net timed advantage against the inherited evaluator or explain formal-case
  performance. An exact faster evaluator can intentionally preserve local moves.

Therefore **absence of a nonempty real-path or retained-gain probe is no longer
an adequate general explanation of R26's negative science**. Stronger executable
diagnostics coexist with unchanged formal aggregate effects. This does not prove
the diagnostics have no value; it narrows what they can establish. Caches,
neighborhood changes and scheduling changes still interact with real time costs,
trajectory changes and instance distribution.

Exact representative trace files, all under this run's `llm_traces/`:

|Evidence|Trace|
|---|---|
|A1 passing real publication/hit probe|`20261028T124545541064_code_research_turn_81ebeb35.json`|
|B1 failed closure expectation|`20261028T135543959073_code_research_turn_5894a1f5.json`|
|B1 corrected directed reference|`20261028T135745808541_code_research_turn_31a9e1e2.json`|
|C2 interleaving reference|`20261028T210321938385_code_research_turn_d57dfd5e.json`|
|B3 explicit abandonment|`20261029T040501607611_code_research_finalize_ba9b0ec5.json`|
|C3 final sparse/reference probe|`20261029T041202498586_code_research_turn_d902ceef.json`|
|A4 final real gain/downstream/retention probe|`20261029T052532017823_code_research_turn_78049f12.json`|
|A4 terminal passing tool feedback|`20261029T052551543698_code_research_turn_96f5d30a.json`|

## Research-interface cost

Provider-reported trace usage sums to 16,358,748 H input tokens and 5,116,229 C
input tokens: **21,474,977 reported input tokens**, across repeated dispatches.
Median H request input is 196,667 tokens (range 177,280–210,101); median C input
is 64,039 (61,572–76,262). These are provider-reported usage values, not an
independent tokenizer or billing audit. Reported cache-read input sums to 28,928;
that field alone cannot establish the provider's actual caching or charges.

The [first H trace](/home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028/llm_traces/20261028T123353743482_hypothesis_research_turn_35f4251f.json)
has a 826,553-character `hypothesis_research` structure, alongside the
46,995-character research question. Character counts below use Python
`len(json.dumps(value, ensure_ascii=False))`, including JSON syntax/default
spaces; they are not token counts. Top-level field sizes are:

|Field|Serialized characters|
|---|---:|
|`history_index` (229 records)|817,300|
|`source_index` (30 records)|8,847|
|`failure_frontier`|148|
|`max_action_bytes`|6|
|`remaining_research_turns`|2|
|`tool_results`, `visible_history`, `visible_sources` (each initially empty)|2 each|
|`remaining_read_calls`, `remaining_search_calls`, `turn_index`|1 each|

The history index contains 224 prior-research rows and five observation rows.
Summed serialized field-value sizes across rows are: `hypothesis` 639,633,
`outcomes` 122,950, `sections` 22,039, `kind` 5,521, `ref` 3,206, `ordinal` 569
and `patch_change_count` 224 characters. Within the hypothesis dictionaries,
the largest field-value sums are `text` 428,525, `expected_effect` 95,884 and
`target_weakness` 70,783. Dictionary keys and container punctuation explain why
these field-value sums do not equal the enclosing serialized sizes.

Thus the index already carries extensive old hypothesis prose and outcomes
before any explicit history read. The top-level prior-history fields are compact
index markers; the large value is inside `hypothesis_research.history_index`.
It would be incorrect to infer that not calling `read_history` on old rows means
not seeing old research knowledge. After the first current-run history read,
the [next trace](/home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028/llm_traces/20261028T135050690077_hypothesis_research_turn_c0d944e4.json)
contains both an 822,296-character index and a 17,680-character `visible_history`
list with the requested full record. These are measurements of saved projections,
not unique scientific knowledge or evidence that all provider input is history.

The repeated context cost is observable; its causal effect on research quality
is not identified by this run. These measurements do not authorize silent
truncation, ranking or summary replacement of source/history.

## R24–R26 bounded comparison

R24/R25 values below come from their linked checked-in terminal audits; this
turn did not reopen those complete raw runs.

|Run|Evaluated candidates|Formal stages / pair rows|Provider calls|Strongest recorded stage fact|Research interpretation|
|---|---:|---|---:|---|---|
|[R24](v04-cvrp-r24-stable-advantage-autonomous-postrun-20261026.md)|6|12 / 384|86|A2 expanded +12.75 [0,83.25]; validation +40 [-35.25,606.25], insufficient|Real cumulative screening signal; no promotion; one stronger extra-gain witness weakened|
|[R25](v04-cvrp-r25-counterfactual-evidence-autonomous-postrun-20261028.md)|10|12 / 296|137|All stage effects 0; expanded C2 and A4 fail|Better independent tests; scope and nonempty-caller evidence gaps remain|
|R26|9|12 / 324|162|All stage effects 0; three expanded candidates fail|Nonempty real reuse and real gain/retention witnesses now exist; no stable formal advantage|

All use complete R22 C3 as local comparator. The 1,004 executed pair rows and
25 evaluated candidates across these three reports are descriptive work volume,
not an independent pooled trial. Seeds, adaptive choices and support differ;
expanded grids overlap earlier stages; R24 includes a distinct validation
population. This sequence cannot isolate the causal effect of a support change,
model, hypothesis family, memory design or budget.

The supported checkpoint is narrower and more useful: the runtime repeatedly
executes substantive source-grounded research with valid comparative evidence,
and research diagnostics have improved, yet that progress has not established
stable complete-solver advantage in these runs. No observed source-delivery,
provider or best-return failure explains R26. Neither “the model cannot research
algorithms” nor “one more probe/example will unlock retained gains” follows from
this evidence. Original-B0 superiority and retained CVRP improvement remain open.

## Exact raw metric references and audit boundary

All files below are under the exact R26 root's `metrics/`, reached from ordinary
summary references:

|Step|Metric file|
|---:|---|
|1|`7331e71b-89e8-40fb-a8a1-ca17a173d350.json`|
|2|`d99b2be4-36b8-458f-b98c-807086dec3c4.json`|
|3|`988ea635-c41c-45e8-8d2e-c304e73415dd.json`|
|4|`d7cbd634-745c-4e36-a931-649601ce0835.json`|
|5|`731039d9-79f9-433c-bfd9-270b042e6044.json`|
|6|`82ab1959-4e98-41f5-8d3a-fe46cfb2c871.json`|
|7|`d05a469a-f62d-417a-b7ca-23d3e090a5a4.json`|
|8|`34f9e79b-cb28-4830-985c-d6788b8d8749.json`|
|9|`ca0f46ca-df6d-4aa0-892c-19e9d09504d4.json`|
|10|`64d05527-08d7-4692-a194-a9d9b001030f.json`|
|12|`ff0ca3cc-713e-43d5-a225-c9929ba2e038.json`|
|13|`6a8c6300-1d04-43ed-87f5-c5c0bed45b2b.json`|

Read-only Python calculations parsed these twelve metrics and all 162 traces,
compared ordinary source bytes and applied patches in memory, parsed Python ASTs,
and checked recorded progress/best-update inequalities. No production or test
suite pass is claimed. The only file authored by this subtask is this postrun;
no original experiment artifact, existing document, input, code or index was
changed, and no Git action or new experiment was performed.

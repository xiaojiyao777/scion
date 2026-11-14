# CVRP R24: valid completion, promising cumulative candidate, no stable promotion

State: **completed / valid / requested_rounds_completed**, 12/12 evaluated
stages, no promotion. Terminal `status.json.updated_at` is October25
08:54:22 Beijing /00:54:22 UTC, about19h47m57s after launch. The October26 request
authorizes completion checking, analysis and optimization, not another launch,
terminal resume, budget expansion or Git publication. This report supersedes the
startup snapshot in the [frozen design](v04-cvrp-r24-stable-advantage-autonomous-preregistration-20261024.md).

## Scope and operating validity

Exact root:
`/home/clawd/research/scion-experiments/v04-cvrp-r24-stable-advantage-autonomous-20261024`.
Ordinary evidence below is relative to this root:

- `status.json`, `campaign_summary.json`, `research_history.jsonl`;
- `llm_traces/` for all86 requests, their responses, code drafts and tool results;
- `champions/champion_v1`, three surviving `candidate_workspaces/` heads;
- the twelve exact metric references in the stage table below.

Entry checkout was clean5a27803e, equal to the local origin tracking ref on
v0.4-dev. Mandatory ordered handoff, Experiment Analysis profile, runbook and
postrun handoff were read. All experiment carriers are dead; R24's tmux pane
has exit0. Filtered process inspection found no active campaign/solver/test
before local support tests. Launch provenance remains a4476ecc plus the then
uncommitted R23 support/analysis and R24 inputs; later Git publication does not
retroactively change the launch source.

All12 scheduled stages evaluated:11 screening and1 validation, zero frozen.
There are **six H/C candidates**, not eleven: the summary's
`formal_screened_candidates=11` counts screening stages, including expansions.
All86 provider calls succeeded on attempt0 with gpt-6.1-sol:46 H and40 C;
514 of600 calls remain unused. No provider, quota, resource, solver-error,
infrastructure or interrupted execution outcome is recorded. The48-hour guard
was not exhausted. No additional budget is needed to explain this terminal.

Prelaunch and Git-only lifecycle records show no competing operator test/solver
work during the run. There is no continuous host-load record, so absence of all
external interference cannot be proven. This turn changed no original experiment
file, did not open original SQLite, call a provider, or rerun a formal candidate.

## Framework correctness and source identification

The complete local comparator remains **R22 C3**, preserved as R23's candidate,
not R23 A/R19 A3 and not original B0. Champion version remains1. Each surviving
tree contains100 ordinary files/48 Python files; its only change relative to
champion is `policies/baseline_modules/local_search.py`.

Labels below follow first branch appearance, with branch prefixes for lookup:

|Candidate / branch|Evaluated stages|Implementation and source status|
|---|---|---|
|A1 /3850d790|1–2|Delete only ordinary registry Or-opt-1; PATCH_FALLBACK_IDENTIFIED|
|A2 /3850d790|6–8|A1 plus exact positional regret-2/3 insertion cache and deadline checks; PATCH_FALLBACK_IDENTIFIED|
|B1 /fc486c43|3|Early exact ordering for routes of at most8 customers; PATCH_FALLBACK_IDENTIFIED|
|B2 /fc486c43|11–12|Move inherited exact ordering to the existing late short-route boundary, restore ordinary early reversal; FULL_SOURCE_IDENTIFIED, `candidate_workspaces/candidate-t3oni1jc`|
|C1 /81b3b374|4–5|Completed no-improvement certificates for unchanged two-opt-star route pairs; FULL_SOURCE_IDENTIFIED, `candidate_workspaces/candidate-eyyrfs4e`|
|D1 /3c04b84b|9–10|Insertion-edge-directed third candidate phase for post-sweep SWAP*; FULL_SOURCE_IDENTIFIED, `candidate_workspaces/candidate-8j40vomv`|

A's abandoned heads and B1's superseded tree do not survive as complete workspace
directories; `archive/` and `workspaces/` are empty. Their ordinary final C drafts,
base-source references and complete champion source allow patch fallback, not a
claim that their original stage directories still exist. Read-only in-memory
application of each final exact-replace/full-file draft reproduces all three
surviving heads byte-for-byte across48 Python files. Every visible C source body
matches its actual branch base, and every resulting Python file parses. The
remaining unchanged files come from the same complete champion tree. No executable
fallback tree, recorder, hash authority or new campaign artifact was created.

The relevant ready traces, in candidate order A1/B1/C1/A2/D1/B2, are:

```
20261024T051050789259_code_research_turn_ed9821ea.json
20261024T084224404947_code_research_turn_03a50719.json
20261024T095644215318_code_research_turn_a7e739e9.json
20261024T132344705610_code_research_turn_66b9330d.json
20261024T180453852382_code_research_turn_0f6e59df.json
20261024T213222129264_code_research_turn_b06b774a.json
```

All six Contract/Verification checks pass; all recorded canaries pass. Expanded
stages reuse accepted code rather than claiming a fresh H/C/Verification session.
All384 executed pair rows/768 solver sides are valid, with zero failed pairs,
invalid solutions, solver errors or fleet violations. Every declared Cartesian
case/seed grid, equal per-pair limit, raw objective difference, comparison sign,
case median and1000-bootstrap CI reconciles. Recorded formal elapsed sum is
67858.243seconds, excluding canaries and development probes.

The ordinary autonomous path is champion-first, not counterbalanced; no AB/BA
balancing claim is available. Expansions rerun the original20 cells inside the48,
not just28 additional cells. The same champion's final objective changes on
9/5/5/5/7 of those20 repeated cells at stages2/5/7/10/12, respectively; candidate
counts are9/4/6/4/5. Fixed seeds therefore do not make wall-clock-bounded search
trajectories identical. Initial and expanded results must not be pooled as
independent samples or interpreted solely as the effect of adding cases/seeds.

Recomputing the existing gates with problem-bound practical deltas2.0/1.0,
unchanged case-quality rules and raw typed statistics reproduces all12 recorded
gate outcomes/reasons. No historical Decision is rewritten. An initial audit
loaded unbound config defaults; binding the problem-owned measurement corrected
the audit and left every reproduced outcome unchanged. Source audit also had to
exclude lazy `content=null` entries and handle both supported patch forms;
those were audit-script assumptions, not campaign failures.

The safe history has11 screening rows and excludes validation. No validation
case-name or metric-reference match was found in any H/C structured context.
This is a bounded negative leakage check, not a proof about every possible
information channel. Operator-only validation details below must not be copied
into future H/C input/support. Framework verdict: **no exercised correctness
defect found**, with the order, timing and source-retention limits above.

## Complete stage results

Positive delta means champion final distance minus candidate final distance.
Effect/CI are the median of case medians and its95% bootstrap interval, not the
pooled seed median. Initial screening is5 cases×4 seeds; expanded is6×8;
validation is a different6-case×4-seed population. These are separate estimands.

|Stage|Candidate|Pairs|Case W/L/T|Pair W/L/T|Effect [CI]|Recorded outcome|
|---:|---|---:|---|---|---|---|
|1|A1 initial|20|2/1/2|7/2/11|0 [-3.5,126.5]|expand|
|2|A1 expanded|48|2/0/4|17/7/24|0 [0,15]|unclear; continue|
|3|B1 initial|20|1/1/3|3/5/12|0 [-560.5,25]|fail case quality|
|4|C1 initial|20|2/0/3|4/2/14|0 [0,257]|expand|
|5|C1 expanded|48|1/0/5|10/5/33|0 [0,67.25]|fail case quality|
|6|A2 initial|20|3/0/2|8/1/11|14.5 [0,90]|required expansion|
|7|A2 expanded|48|4/0/2|20/5/23|12.75 [0,83.25]|pass; queue validation|
|8|A2 validation|24|4/1/1|10/7/7|40 [-35.25,606.25]|fail insufficient evidence; abandon|
|9|D1 initial|20|1/0/4|3/2/15|0 [0,27]|expand|
|10|D1 expanded|48|1/0/5|11/6/31|0 [0,1.75]|fail case quality|
|11|B2 initial|20|2/0/3|4/2/14|0 [0,20]|expand|
|12|B2 expanded|48|1/1/4|10/9/29|0 [-1.25,.25]|fail case quality|

Exact metric filenames under `metrics/`, in stage order:

```
1  94235dff-e72c-4501-b5bf-6328d5e9e371.json
2  87aae056-5fbd-4fd1-8d01-6815dc7d9455.json
3  cd416c25-76a6-44c2-8947-aeef0b0bcde1.json
4  5e43d59c-318f-4ab6-ad5a-5eb37b6881f9.json
5  618bb29d-a7b9-4a7c-8caf-a103b431e6cb.json
6  ced50329-085a-4d5d-b29c-dfd08e2924dc.json
7  e57ab54f-b973-4b10-8d4c-8ced45f43646.json
8  d5d34b33-f6f6-4038-b6df-b9e096b728c8.json
9  335d9c7d-0f5e-408d-99ae-97b91c83d00e.json
10 48c91832-7bb4-4d36-b195-24ddce8946c1.json
11 f10bb480-33c0-4d83-b76a-c91c5d388719.json
12 430c5564-336c-4eab-9acf-6d8e3e62a587.json
```

All final available screening case medians, including negative and zero cases:

|Case|A1 expanded|A2 expanded|B1 initial only|B2 expanded|C1 expanded|D1 expanded|
|---|---:|---:|---:|---:|---:|---:|
|B-n34-k5|0|0|0|0|0|0|
|tai100a|24|25|25|-2.5|0|3.5|
|X-n351-k40|0|134.5|-560.5|0|134.5|0|
|A-n54-k7|0|.5|not sampled|.5|0|0|
|X-n190-k8|0|0|0|0|0|0|
|X-n513-k21|15|32|0|0|0|0|

B1's four X351 deltas are-299,-1015,-822,-66: early exact ordering is harmful
on that sampled case despite independently correct tiny-route optimization.
B2 no longer shows that uniformly adverse initial result, but its expanded
X351 vector is127,19,0,0,316,0,-343,0 and tai100a155,-5,-23,0,-24,-15,10,0.
Changing the timing boundary did not establish stable superiority. These are
separate cumulative-versus-champion contrasts, not a paired B1/B2 ablation.

### A2: the positive screening signal and its limits

Screening seeds in order:300007,300017,300023,300043,300073,300089,300109,300119.

|Case|All eight final deltas|
|---|---|
|B-n34-k5|0,0,0,0,0,0,0,0|
|tai100a|-2,-3,77,50,-32,58,0,122|
|X-n351-k40|476,294,0,0,269,0,374,0|
|A-n54-k7|-1,1,0,-3,1,1,1,0|
|X-n190-k8|0,0,0,0,0,0,0,0|
|X-n513-k21|32,32,32,32,47,32,32,32|

A2 is the complete A1-plus-cache candidate, not an isolated cache experiment.
No same-run A1/A2 matched comparison isolates the new patch. More ALNS work is
observable: total iterations16687 versus13733 for champion, and best updates
92 versus77. B34 nevertheless remains all ties; X190 remains all ties. Every
X513 arm has zero ALNS iterations and returns its post-initial-search objective;
its gains cannot be credited to subsequent regret-repair ALNS throughput.

Operator-only validation seeds:300137,300149,300151,300163. Do not export this
table or its case-specific implications to autonomous development prompts.

|Case|Four final deltas|Median|
|---|---|---:|
|B-n39-k5|0,0,0,0|0|
|X-n106-k14|-27,-114,0,-118|-70.5|
|tai385|379,-378,305,-31|137|
|A-n62-k8|16,-7,-1,3|1|
|X-n228-k23|1064,1073,1091,1078|1075.5|
|X-n627-k43|189,0,158,0|79|

Case net score.5 and loss rate1/6 meet the unchanged case-quality thresholds;
effect40 exceeds practical delta1. The CI lower bound-35.25 does not meet0.
Validation already uses all6 configured cases (`expand_to=6`), so
`VALIDATION_EXPAND_EXHAUSTED_INSUFFICIENT_EVIDENCE` is the correct recorded
terminal, not an infrastructure failure or a request to add seeds after seeing
the result. The mixed signs and wide interval mean **insufficient stable
comparative evidence**, not proof that all A2 gains are fictitious.

Across all768 sides, final distance equals recorded final progress and is no
worse than its own post-initial-search distance. All1350 recorded best updates
are retained or improved upon at return. Every pair satisfies
`final(A-B)=initial(A-B)+(B_initial-B_final)-(A_initial-A_final)`; no positive
initial lead reverses to a negative final delta in R24. This differs from R23
but does not turn R24's negative cases/ties into wins. No best-return production
repair is supported. Family-level telemetry still does not identify the exact
new kernel's causal contribution to complete-solver quality.

## H/C research quality and the remaining testing issue

|Candidate|H/C calls|Grounding, implementation and probe scope|
|---|---|---|
|A1|10/3|Reads actual relocate/Or-opt/controller source. Faithful one-entry deletion;1152 independent tiny closure cases, real dispatch/state/return checks and large deadline fixture. No direct improving transition is expected from deleting redundant work.|
|B1|8/9|Reads prior A1 evidence without inheriting that sibling. Faithful short-route DP/cache; independent exhaustive optima, every counted cutoff, real-entry completed calculations. Correct local optimization does not establish favorable basin/time effects.|
|C1|7/12|Reads B1's negative screen, preserves champion rather than sibling DP. Faithful completed-pair certificates, original restart order, invalidation and bounded lifetime. Two passing probes cover exact transitions, reuse/cutoffs and actual-entry certificate publication.|
|A2|6/3|Correctly recognizes retained A1 registry change and sibling C1 as not inherited. Faithful positional top-k repair-local cache, not route-distinct regret. Independent transition/cache-reuse tests and poll cutoffs pass; custom probe has no real `solve` entry. Host smoke passing does not fill exact changed-path attribution.|
|D1|9/5|Source-grounded edge-directed supplement. Second revision restores positional nomination tie order and independently rescored precommit costs. One failed, then one passing custom probe; the stronger extra-gain witness was weakened, as detailed below.|
|B2|6/8|Explicitly reads failed B1 and sibling D1 evidence; recognizes actual inherited DP. Faithful early-to-late substitution, not a sibling merge. Independent brute-force/cutoff checks, real VNS accepted late move/reclosure and unforced solve completion; positive fixed-start VNS witness is not a retained changed-kernel gain witness from real construction to final return.|

No recorded H/C tool-error result was found. All8 `test_patch` submissions pass
the five host checks;7 custom falsifiers pass and1 fails. This separation is
intentional: optional falsifiers inform research and do not become new formal
quality gates. Final C generation sees its tool results. Passing source checks,
references, probes and real entry establish different facts, not final benefit.

D1's first probe
`20261024T180244391267_code_research_turn_d8f614e5.json` fails at line135:
`assert stronger>0`. The preceding40 synthetic cases compare the proposed and
inherited candidate sets with independent full-route scoring; no strictly better
supplemental winner is witnessed in that bounded fixture. This does not prove
that no such winner exists anywhere.

Its final probe
`20261024T180435162076_code_research_turn_5b22c949.json` changes the fixture and
checks `assert additions > 0` over16 cases. It still computes an extra-gain flag,
but discards it. The final probe therefore supports additional nominations,
reference agreement and path completion, **not restored evidence of extra gain**.
There were real code improvements between drafts, so this is not described as
only deleting a test; however, those changes do not logically repair the missing
stronger witness. D1's expanded outcome0 [0,1.75] does not rescue that inference.

Research verdict: meaningful source-grounded implementations and stronger
isolated diagnostics, one promising cumulative screening signal, but **no
confirmed stable final advantage**. Remaining weaknesses are counterfactual
test claims, full-entry changed-path benefit coverage, and whole-source
attribution/stability—not provider access or a missing generic cache service.

## Evidence-backed optimization and next falsifiable rung

This turn adds an executable, optional problem-owned reference worksheet to
`PUBLIC_PROBE_EXAMPLE` in `scion/scion/problems/cvrp/tests/test_solver.py`:

- Independently rescore complete feasible inherited/proposed trial solutions at
  the same start; report own gain separately from additional gain over inherited
  best, retaining zero and negative outcomes.
- Use a public symmetric fixture with independently known22/4 costs: adding a
  distinct equally good route increases trials without improving inherited best.
  Include genuine extra gain, a worse trial set and no-trial controls.
- Explicitly state that an exact cache may intentionally yield identical local
  results; this worksheet is not a mandatory positive-gain requirement. Enumeration
  correctness, real-entry reachability, timed speed and final quality remain
  separate claims. A weakened passing test must not be reported as the original
  stronger claim succeeding.

Five new framework regressions exercise the worksheet, falsify three weakened
interpretations (own gain, trial count, clamped-away losses) and reject incomplete
solutions in either arm. **132 focused tests pass in37.18seconds**, covering
reference support, probe diagnostics, public dependencies, Contract/source
provider and R24 inputs. The full26,049-character optional example passes on
both the repository and an isolated copy of unchanged R24 champion C3 under the
existing10-second sandbox. The two collected candidate tests have identical
executable AST to HEAD. No full-suite claim is made.

Production algorithms, Scion core/prompts, formal tests, Contract/Verification/
Protocol/Decision, frozen inputs and all experiment evidence remain unchanged.
This support improvement has not yet been tested on new autonomous research;
it is not evidence that future H/C will necessarily use it correctly.

Next authorized work should keep the complete C3 comparator and all whole safe
history/screening evidence, including losses and the failed stronger probe.
Let H/C choose algorithms and tests. A fresh research question can distinguish
exact evaluator savings from added search capability, and ask for a matching
reference claim plus actual changed-path behavior; do not prescribe a mechanism,
phase split, required positive fixture or favorable case exception.

If independently confirming A2 is selected instead, first prepare and verify its
complete fallback source in a fresh destination, without altering R24, then
preregister an equal-budget, counterbalanced fixed contrast with fresh seeds and
unchanged gates. Do not silently call the current B2 head A2, merge siblings,
pool A2 with A1, repeatedly resample validation until success, or use private
validation failures to steer the algorithm. Original-B0 retained improvement
remains a separate open claim. The initial analysis request did not authorize a
launch or Git. The subsequent October26 request now explicitly authorizes
optimization/design/launch and commit/push; see the separate
[R25 design and lifecycle](v04-cvrp-r25-counterfactual-evidence-autonomous-preregistration-20261026.md).
It chooses fresh whole-C3 autonomous research, not an A2 reconstruction or resume.

# CVRP R20 postrun: valid improvement signal, incomplete stability evidence

## Terminal and scope

R20 completed normally as **NOT_CONFIRMED at validation**, with terminal JSON
written October8 at19:05:39.756101 UTC /October9 at03:05:39 Beijing. Started
October8 at15:36:28 UTC /23:36:28 Beijing. The dead tmux pane has exit0; the
scientific verdict comes from terminal and raw metrics, not that exit code.
Read-only analysis followed the Experiment Analysis profile and runbook. No
original SQLite, provider call, extra solver run, source reconstruction, terminal
resume or post-outcome sample extension was used.

Evidence root:
`/home/clawd/research/scion-experiments/v04-cvrp-r20-r19-final-b0-fixed-20261008`.
Read `input.json`, `terminal.json`, the two exact metrics below and the two
`input_snapshots` only. The [frozen design](v04-cvrp-r20-r19-final-b0-fixed-preregistration-20261008.md)
remains unchanged. The October8 commit/push is3d2123e3; runtime is unchanged
from6380a59e, with only inputs/tests/docs committed during measurement and no
operator tests, solvers or maintenance initiated. Host noise cannot be excluded.

All72 formal pairs are valid, zero failed comparisons, infeasible solutions or
fleet violations. Canary passes both arms on seed260209/10seconds. There are146
solver processes including canary,16100 nominal and20480 guarded subject-seconds,
below the frozen338/40580/50720 limits and24-hour guard. Provider calls are zero.
No service, quota, constructor failure or global resource exhaustion caused this
terminal. Frozen/retained and promotion outputs are absent and remain unopened.

## Source and execution audit

Both100-file snapshots (48 Python files each) byte-equal their declared ordinary
source files (excluding pre-existing Python caches):
A is R13 `input_snapshots/baseline` (B0-fixed); B is R19
`candidate_workspaces/candidate-560r6jum` (complete A3). Their exact differences
remain destroy_repair, local_search and scheduler in `policies/baseline_modules`.
Both keep the identical independent constructor repair. FULL_SOURCE_IDENTIFIED;
no sibling merge, original-B0 edit or new H/C proposal. R19's old candidate
directory additionally has10 bytecode files dated October6; no ordinary file
differs or is missing, and no cache cleanup was performed. R20 cannot assess new
agent behavior because it contains no agent calls.

Every matrix cell, scheduled/actual AB/BA order, ordinal parity and resolved
per-solve limit matches the frozen design. Screening is24AB/24BA, four of each
per case; validation12AB/12BA, two of each per case. Every arm is active and
valid. Absolute-distance subtraction reproduces every delta; case medians,
aggregate medians and the configured case-level bootstrap reproduce both stored
confidence intervals. These are audits of recorded outcomes, not a new Decision.
The canary metadata's coarse `raw_metrics_unavailable_reason` string mentions
veto even though both passed flags are true and the formal funnel ran; it is not
evidence of an actual veto or missing formal pair.

## Screening — public research evidence

Metric: `metrics/ffb0888f-b2ca-43b4-a719-fd1a36a145e4.json`.
All48/48 valid; case W/L/T **5/0/1**, median of case medians **+135.25**, CI
**[1,6115.5]**. SCREENING_PASS /queue_validate. Pair W/L/T36/1/11.
Positive delta is B0-fixed distance minus candidate distance. Seed order:
260003,260009,260011,260017,260023,260047,260081,260089.

| Case | Complete paired deltas | Median |
|---|---|---:|
|B-n34-k5|0,0,0,0,0,0,0,0|0|
|tai100a|97,216,280,325,50,137,228,173|194.5|
|X-n351-k40|12618,11977,12031,12243,11977,11923,11979,12357|12005|
|A-n54-k7|4,2,3,0,5,0,0,-2|1|
|X-n190-k8|3,124,76,76,76,129,76,76|76|
|X-n513-k21|226,226,226,226,198,226,226,226|226|

This confirms a fresh-seed, counterbalanced screening signal for the cumulative
bundle against B0-fixed; not the isolated R19 A3 edit or unchanged original B0.
It is a different contrast from R19's R12-A-fixed comparison. No pooling.
Median runtime ratio1.0000714 and median delta4.5ms show a near-equal budget,
not measured end-to-end speedup.

X351 candidate initial VNS takes103.2–109.8 seconds versus137.8–138.6 for A;
candidate post-initial distance31776 for all seeds. Its1–3 ALNS iterations versus
zero baseline yield further421/434 distance reductions in two seeds only.
X190 candidate initial VNS takes4.3–5.0 seconds versus2.6–3.0; post-initial17800
improves48/53 in two seeds. X513 final26764 always equals post-initial; seven
seeds have zero ALNS, one has one iteration. Its initial VNS is134.9–137.0 seconds
versus96.8–103.8. Phase/family telemetry is not component causality. A small
negative A54 pair remains despite the positive case median.

## Validation — operator-only, forbidden in H/C input

Metric: `metrics/52b49618-30fa-4857-9357-751edfb5f7d5.json`.
All24/24 valid; case W/L/T **4/1/1**, median **+1389.75**, CI
**[-20.5,6526]**. Pair W/L/T18/3/3. Decision abandon, reason
`VALIDATION_EXPAND_EXHAUSTED_INSUFFICIENT_EVIDENCE`.
Seed order260111,260137,260171,260179:

| Case | Complete paired deltas | Median |
|---|---|---:|
|B-n39-k5|0,0,0,1|0|
|X-n106-k14|-84,10,-26,-56|-41|
|tai385|4694,4605,9911,13197|7302.5|
|A-n62-k8|10,14,15,14|14|
|X-n228-k23|2759,2772,2747,2787|2765.5|
|X-n627-k43|5750,5812,5749,4940|5749.5|

Win rate, median practical margin, net case score and loss rate pass their
thresholds, but the CI lower bound is negative. Validation already has its six
configured cases, so no expansion remains. The reason denotes exhausted
**prespecified evidence expansion**, not exhausted token/CPU/call budget. The
bootstrap resamples six case medians, not24 independent case-seed observations;
more seeds do not remove cross-case heterogeneity or establish generalization.
No posthoc relaxation, adaptive seed addition or best-subset verdict is justified.

The X106 candidate initial26931 is worse than baseline26874; final values are
26931/26864/26900/26930 versus26847/26874/26874/26874. Candidate30–35 ALNS
iterations versus18–27 do not guarantee recovery. Both arms have zero ALNS on
tai385/X228/X627; gains there belong to the initial phase, not demonstrated later
ALNS learning. These observations do not isolate the cause or authorize a host
algorithm patch. Runtime ratio0.9999786, median delta-2ms. The formerly failing
shared construction completes this whole validation matrix, a narrower claim
than universal constructor correctness.

## Interpretation and next falsifiable rung

Framework execution is sound on the exercised paths. Algorithm quality has a
substantial but uneven B0-fixed signal; the full confirmation requirement is
**not met**, no promotion and no retained improvement. R19's independent-reference
probes are useful, but timeout/entry-only tests still do not establish accepted
large-case transitions or retention in the returned best. There is no new shared
runtime defect supported by R20, and no causal ablation of bundled support/model
changes. No shared-code repair or new Warehouse control is warranted this turn.

October9 user authorizes analysis, optimization and another run. Prepare
[fresh R21](v04-cvrp-r21-source-grounded-autonomous-preregistration-20261009.md)
from the exact complete R20 candidate snapshot, not the older starting tree and
not a synthetic sibling merge. This is a selected local development baseline,
not scientific promotion. Optimize research continuity and current-source
grounding: clearly distinguish current source from complete archived question
and history, expose all R19 safe records and the entire R20 screening matrix,
and distinguish independent references, real entry, completed transitions,
acceptance and retained best. H/C still choose algorithms and tests.

Do not feed this validation section, terminal outcome, private cases/seeds or
metrics paths to H/C, nor derive a required mechanism from them. Keep R20's denser
sampling prospectively with new seeds and unchanged gates/resources. Autonomous
R21 is champion-first development, not a counterbalanced B0-fixed confirmation;
even a promising R21 result will still need an exact independent retained test.
Original evidence stays unchanged; R19 and R20 are never resumed. No Git action
is requested by the October9 message.

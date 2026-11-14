# CVRP R23: final gains repeat, but relative advantage is not consistently retained

State: **completed / NOT_CONFIRMED at expanded screening**. Terminal artifact
written by October18 13:30:25 Beijing /05:30:25 UTC, about2h17m31s after launch.
The file modification time supplies this upper-bound completion timestamp;
`terminal.json` itself does not contain a completion-time field. October24 user
requests completion checking, analysis and optimization, not another launch or
Git publication. This report supersedes the startup snapshot in the
[frozen design](v04-cvrp-r23-r22-final-local-fixed-preregistration-20261018.md).

## Scope and source identification

Exact root:
`/home/clawd/research/scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018`.

- [Terminal](../../../../../scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018/terminal.json)
  and [input](../../../../../scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018/input.json).
- Sole formal metric:
  `metrics/1cd0df7a-75d2-4460-824f-ced17adc7c03.json` under that root.
- Complete ordinary sources: `input_snapshots/baseline` (A, unchanged R22
  champion/R19 A3) and `input_snapshots/candidate` (B, exact complete R22 C3).

Entry checkout is clean `a4476ecc`, equal to the local origin tracking ref on
`v0.4-dev`. Mandatory handoff, Experiment Analysis profile, operations runbook
and postrun handoff were read. All experiment tmux panes are dead; R23 exit0.
Filtered process inspection found no active campaign/fixed driver/test before
local support verification. No original SQLite, source or experiment artifact
was changed, no historical-root scan, provider call, terminal resume or formal
solver rerun. The later Git publication does not rewrite launch provenance.

Both100-file/48-Python snapshots still exactly equal their declared R22 sources;
all Python parses, all snapshot files are read-only. The file sets are identical
and differ only in `policies/baseline_modules/local_search.py`.
Candidate status: **FULL_SOURCE_IDENTIFIED**. No sibling merge or reconstructed
executable candidate is involved. This is a whole-source local-comparator
contrast, not original B0, B0-fixed, or an isolated C2-versus-C3 ablation.

## Framework correctness and operating validity

There are no new H/C sessions or provider calls in this fixed run. Prior R22
Contract/Verification accepted the unchanged complete C3; R23 did not rerun or
fabricate that proposal pipeline. Its existing fixed driver performs source
scope checks, complete-pair canary, Protocol/runtime/feasibility checks, Safe
Features and deterministic Decision, using disposable per-arm copies.

Paired canary passed in both arms. Expanded screening contains all48 unique
declared cells: six cases, eight prospective seeds each,96 successful feasible
solver sides, zero failed pairs, zero solver errors or protected fleet violations.
All actual orders equal scheduled parity order:4AB/4BA per case,24AB/24BA total.
Every arm has its declared equal60/90/180-second limit and exits inside the
additional30-second subprocess guard. Raw objectives, paired differences,
comparison signs, case medians and bootstrap CI reconcile with the terminal.

Resources consumed:98 solver processes including canary,10580 nominal and13520
guarded subject-seconds, below the338/40580/50720 maximum conditional envelope.
Formal arms' recorded elapsed sum is8226.367seconds. The24-hour outer guard was
not exhausted. There is no provider/service/quota dependency in this run, and
no recorded formal execution failure. Prelaunch checks and subsequent Git-only
handoff record no competing test/solver work; there is no continuous host-load
record from which to prove absence of every external source of interference.

Recorded `SCREENING_FAIL_CASE_QUALITY` -> `continue_explore` is consistent with
the unchanged rule. The fixed funnel therefore stops `NOT_CONFIRMED`, with no
validation/frozen/retained stage or promoted snapshot. This is valid negative
comparative evidence, not incomplete execution or permission to resume.
No exercised source, aggregation or Decision defect was found.

## Complete quality result

Positive delta = A final distance minus B final distance; smaller distance wins.
Seeds in every row:290011,290021,290023,290027,290033,290039,290041,290047.

|Case|Eight paired final-distance deltas|R23 median|R22 C3 median|
|---|---|---:|---:|
|B-n34-k5|0,0,0,0,0,0,0,0|0|0|
|tai100a|-51,-20,-2,-9,19,11,1,-58|-5.5|-.5|
|X-n351-k40|180,180,180,180,180,-42,-312,180|180|180|
|A-n54-k7|2,0,1,-3,-2,1,-2,-5|-1|-.5|
|X-n190-k8|67,88,67,67,67,67,273,50|67|67|
|X-n513-k21|110,95,110,110,110,110,110,110|110|110|

R23 pair W/L/T is28/11/9; case W/L/T is3/2/1. Median of the six case medians is
**+33.5**,95% bootstrap CI **[-3.25,145]**. This is not a pooled seed median.
Net case score(3-2)/6=.1667 falls below.25; loss rate2/6=.3333 exceeds.20;
CI lower bound is below0. Positive aggregate distance alone cannot override
these predeclared conditions or justify waiving small-case losses.

The earlier [R22 discovery](v04-cvrp-r22-retained-path-autonomous-postrun-20261018.md)
had the same aggregate+33.5 and3/2/1 distribution, CI[-.5,145], but26/10/12 pair
W/L/T. R23 repeats all three positive case medians, not uniformly positive seeds:
X351 now loses twice, X190 now wins all eight, X513 again wins all eight. The
two adverse case medians remain adverse. These separate adaptive-discovery and
fixed-repetition populations are not pooled or described as causal improvement
from one experiment to the next.

Post-hoc order summaries do not reverse the case-median signs: AB/BA medians
are0/0, -14.5/-.5,180/180,-1.5/-.5,67/67,110/110 respectively. Each subgroup
contains different seeds and only four pairs; these are descriptive checks,
not estimates proving absence of execution-order effects.

## Own-trajectory retention is not relative-advantage retention

All96 final distances equal the recorded progress final values and are no worse
than their own initial values. All138 recorded best updates, and the matching
138 ALNS new-best rows, are no better than the final returned objective.
81 arms contain ALNS iteration traces. The shared scheduler copies initial to
best, updates best only after feasibility/fleet checks and a strict improvement,
and returns best. No observed best-return loss needs a production repair.

Crucially, this scheduler records its initial distance **after initial local
search**, not immediately after construction. At that checkpoint B leads by4
on tai100a,180 on X351,67 on X190 and95/110 on X513. Seven pairs turn an initial
lead into a final loss: five tai100a and two X351 pairs. Both algorithms still
retain their own gains. For each pair, independently checked against all48 rows:

`final(A-B) = initial(A-B) + (B_initial-B_final) - (A_initial-A_final)`

Examples, using actual distance values:

- tai100a/290011: A2410->2100, B2406->2151. B retains255 of own improvement,
  but A improves310: initial lead4 becomes final delta4+255-310=-51.
- X351/290039: A31776->31467, B31596->31509. B improves another87, but A
  improves309: initial lead180 becomes180+87-309=-42.
- X351/290041: A31776->31284, B31596->31596. B preserves its initial solution;
  A improves492, producing final delta-312. This is not B discarding a good move.
- X513: every B final equals its own post-initial-search distance; all eight B
  arms have zero ALNS iterations. Its final95/110 gains are retained at that
  boundary, but cannot be credited to subsequent ALNS work.

The changed `_vns` attempts the added short-string descent after ordinary
closure, optionally recloses ordinary search after a gain, then permits the
inherited one-shot SWAP*. It is reachable in initial and embedded local search.
The inherited `_swap_intra` helper remains unregistered. Existing family-level
telemetry does not identify exact short-string entry/completion/gain or prove
that this one mechanism caused a complete-solver difference.

There is an observable resource/trajectory tradeoff worth researching. Median
initial-VNS time A->B is103.607s->109.987s on X351 and4.739s->7.111s on X190.
Median ALNS iteration count A->B is1405->1288.5 on B34,66.5->60.5 on tai100a,
373.5->344 on A54 and1.5->1 on X351. X190 nevertheless improves and B34 ties.
Thus fewer iterations or more local-search time is not itself a defect or a
prescription to minimize local search. Timing, route basins and later stochastic
choices all change together; the current run does not isolate their causes.

## Evidence-backed optimization

The research objective is now sharper: **preserve independently checked
within-run gains while producing a stable final advantage over the declared
complete comparator under equal budgets**. A passing no-loss test alone answers
only the first part. R23 contains no new agent work and cannot validate whether
the improved optional examples actually change H/C research behavior. R22's
mocked positive late-string probe and real no-gain control still leave a genuine
changed-path gain witness missing.

This turn makes a deliberately narrow research-support change: extend the
problem-owned `PUBLIC_PROBE_EXAMPLE` explanation with a synthetic two-trajectory
counterexample, the paired decomposition above, non-additivity of medians, and
the exact initial-checkpoint meaning. Explain equal-budget independent paired
confirmation and the limits of throughput/phase observations. No formal case
identifier, private result or mechanism prescription is added to public support.
Executable AST of the example and the two collected candidate tests is unchanged;
production algorithms, shared core/prompts, Contract/Verification/Protocol/
Decision, all existing inputs and original evidence are unchanged.

Next separately authorized experiment should return to autonomous research,
not repeatedly resample unchanged C3 until it passes:

1. Prefer the complete preserved C3 tree as a fresh research starting point,
   with whole ordered safe history, all R22 screening outcomes and the complete
   R23 screening matrix. Do not select only favorable seeds/cases or merge B's
   cache. Under the existing CLI this makes C3 the new local champion; a local
   improvement over C3 is **not** automatically improvement over R23 A or B0.
2. Let H/C choose the algorithm and optional tests. Ask them to investigate
   whole-solver opportunity costs and seed/case stability, and distinguish
   independently recomputed real changed-path gains from mock wiring or counters.
   Keep the full population, limits and gates; no case-name exceptions, required
   mechanism, deadline extension or mandatory telemetry-based candidate gate.
3. If new complete-source evidence warrants confirmation, freeze the new tree
   and use the existing balanced fixed funnel against the preserved R23 A with
   prospective seeds. Keep this contrast separate from local C3 development;
   original-B0 retained confirmation remains a further distinct requirement.

No next scientific inputs, provider invocation or formal experiment are created
in this turn. Preserve adverse results and both complete R23 snapshots; never
resume either terminal R22 or R23. No Git commit/push is requested.

## Verification

Read-only checks cover all48 cells,96 sides, actual AB/BA order, limits, safety,
objective arithmetic, all six case medians, bootstrap CI and gate interpretation;
all96 progress rows and138 best updates; both complete100-file source snapshots,
their declared-source equality, read-only modes, Python AST and one-file contrast.
Only existing statistic/config functions were imported; no solver was invoked.
The public-support explanation changes no executable AST, and its synthetic
counterexample arithmetic is checked independently.129 focused regressions pass
in36.31seconds: optional CVRP reference/probe support, development-probe safe
diagnostics, public read-only dependency context, solver-design Contract/provider
support and R23 inputs. The optional example is now22,735 characters; only
comments changed. Targeted Ruff F/E9 and `git diff --check` pass. No new full-suite
claim or formal-candidate rerun; all checks occur after R23 terminal.

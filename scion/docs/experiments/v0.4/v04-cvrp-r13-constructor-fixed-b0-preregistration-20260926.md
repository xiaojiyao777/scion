# CVRP R13: R12 A plus common construction repair versus B0-fixed

State: launched once at `2026-09-26T01:13:23Z`, driver PID 242261, tmux
`scion-r13-constructor-fixed-b0-20260926`. The user explicitly authorized
an independent GPT-6-Astra constructor-repair subagent, concurrent remaining
optimization design, and launch only after all checks pass. A subsequent
September 26 request authorizes commit/push of this frozen work without
changing the running algorithm or scientific inputs. R12 is terminal; see its operator-only
[postrun](v04-cvrp-r12-post-r11-autonomous-postrun-20260926.md).

Startup: both ordinary 100-file input snapshots equal their declared repaired
sources. The paired canary completed sufficiently to enter screening; an actual
B-n34-k5 / seed 120011 arm was observed with `--time-limit 60`. No formal stage
result exists yet. Runtime, algorithm sources, data and scientific inputs are
frozen; only launch-status documentation is updated. The chat-service interruption
did not stop the driver, and no second launch was made.

## Two distinct questions

1. Engineering correctness: can a generic bounded construction recovery remove
   the known greedy packing dead end without relaxing capacity, coverage, fleet,
   output consistency or runtime audit? Synthetic regressions and isolated
   diagnostics address this; their distances are not comparative effect evidence.
2. Comparative science: does the complete R12 A bundle, with that same repair,
   outperform **B0-fixed**, under equal existing wide budgets and unchanged
   gates? Conditional on all earlier passes, does it retain benefit on the
   separate untouched population?

The second question is not superiority over unchanged B0. A successful outcome
does not retroactively promote R10/R12, prove constructor component causality,
or close the original retained-B0 project objective. Repair is a user-authorized
engineering intervention, not a Scion H/C discovery. This fixed comparison
uses no provider calls and creates no fictional H/C exports.

## Complete source values and common repair

Selected candidate is R12 A `candidate-32jstm92`, steps 9/10: six-case expanded
W/L/T 3/0/3, median +2.25, CI [0,11.25], against R11 B. The other surviving
branches fail or remain uncertain. Selection follows screening, not validation
effect ranking; do not merge their code or make another performance patch.
Its inherited bundle includes best-improvement SWAP* and lazy marginal-saving
worst removal. Large-case zero-ALNS results do not establish the latter's effect.

Create two new ordinary complete copies (100 files each, excluding caches):

- Original B0 remains untouched at
  `/home/clawd/research/scion-experiments/v04-cvrp-r6-minus-2for1-b0-20260921/input_snapshots/baseline`.
- Original R12 A remains untouched at
  `/home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/candidate_workspaces/candidate-32jstm92`.
- New B0-fixed:
  `/home/clawd/research/scion-experiment-inputs/v04-cvrp-r13-constructor-fixed-b0-20260926/b0-fixed`.
- New R12-A-fixed:
  `/home/clawd/research/scion-experiment-inputs/v04-cvrp-r13-constructor-fixed-b0-20260926/r12-a-fixed`.

The identical minimal repair changes construction.py plus remaining-time
passthrough in scheduler.py, route_first_heuristic.py and route_first_seeding.py,
all under `policies/baseline_modules/`. Preserve each arm's unrelated scheduler
research; apply call-site hunks, never replace it with the repository baseline.
Between repaired arms only destroy_repair.py, local_search.py and scheduler.py
differ, as before the common repair. Verify complete file values, not just names.

Recovery begins only when the old descending-demand best-fit packing gets stuck.
It progressively groups least-loaded bins, using sparse subset-sum to pack each
group without recursion or allocation indexed by numeric capacity. It commits
only a complete packing; original successful greedy results are unchanged.
One construction call shares at most 1,000,000 recovery work steps, a two-second
local monotonic bound, and the caller's tighter remaining time. These are
problem-algorithm resource bounds, not a new Scion research gate or wider solve
budget. Failure remains explicit. This heuristic is not globally complete and
must not declare mathematical infeasibility when it fails to find a packing.

The engineering lane may inspect the already exposed constructor failure and
test it as a regression. None of its private case/seed/outcome diagnostics is
fed into autonomous Scion H/C. Common repaired source has an acknowledged
operator-assisted origin. Original B0/R10/R12 evidence is never overwritten.

## Populations, freshness and unchanged science

Use the unchanged [R7 split](inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml):
six known screening, six already exposed validation, twelve unopened frozen
cases. Keep the failing case; do not replace it after seeing failure. Validation
is now a development/completeness gate, not independent confirmation. New seeds
do not make exposed cases unseen. The separate pre-R3
[retained block](inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml) remains
unopened and opens only after screening, validation and frozen pass.

The [Protocol](inputs/v04-cvrp-r13-constructor-fixed-b0-protocol.yaml) differs
from R10 only in version and safety-canary seed. All complete-pair, runtime
audit, feasibility/fleet, practical effect, CI, net case score/loss and
deterministic Decision rules are unchanged. No new telemetry/novelty gate.
Formal dimension bands remain 60/90/120/180/240 seconds for both arms;
canary 10 seconds, subprocess guard 30 seconds, memory 4096 MiB. Algorithm
fraction 0.80 and 3% reserve are unchanged. No maintenance/test/solver overlap.

First eleven primes above 120,000, chosen before outcomes:

| Stage | Cases | Seeds | Pairs |
|---|---:|---|---:|
| expanded screening | 6 | 120011,120017,120041,120047 | 24 |
| exposed validation | 6 | 120049,120067 | 12 |
| unopened frozen | 12 | 120077,120079 | 24 |
| independent retained | 12 | 120091,120097 | 24 |
| safety canary | 1 | 120103 | 1 |

[Main seeds](inputs/v04-cvrp-r13-constructor-fixed-b0-seeds.yaml) and
[retained seeds](inputs/v04-cvrp-r13-constructor-fixed-b0-retained-seeds.yaml)
are disjoint from previous ledgers. Existing fixed-driver parity AB/BA order
is unchanged, A=B0-fixed, B=R12-A-fixed: 12 AB / 12 BA screening pairs. No
adaptive extension, case removal, post-outcome patch, or terminal retry.
Preserve negative and incomplete outcomes; repair does not promise improvement.

## Prelaunch correctness and resource checks

Checkout `v0.4-dev`, HEAD `841de42b`, with prior R10–R12 docs/inputs/tests and
this new uncommitted work. Generic runtime, adapter and gates stay unchanged.
The four problem-algorithm files and focused tests are the only implementation
changes. A separate Warehouse control or shared-core full suite is not required.

Before formal launch:

- Review the independent repair and synthetic regressions, including unchanged
  successful packing, multi-bin fragmented slack, infeasible inputs, sparse
  large capacity, deterministic output and explicit deadline/work exhaustion.
- Run focused CVRP runtime, adapter/solution, deadline, scheduler, fixed-funnel
  and prospective-input tests. Finish all tests before measurement.
- Independently check complete source copies and identical repair application.
  Do not use successful tests as performance proof.
- In an isolated engineering diagnostic, run the two repaired complete solvers
  on the already exposed failed case using old seeds and 30-second limits.
  Inspect active intended algorithm, zero errors, coverage/capacity/fleet and
  independent objective recomputation. Do not compare diagnostic distances or
  use them to choose/tune a candidate. Keep outputs separate from R13.
- Run existing fixed-funnel `--check`, including all 37 case inputs and exact
  source difference; it invokes no solver/provider and creates no output.
- Verify no active competing job, fresh output/tmux and sufficient disk, then
  freeze sources/runtime/data/inputs and launch once.

Maximum conditional work: 85 pairs, 170 solver subprocesses, 20,300 nominal /
25,400 guarded subject-seconds. Canary plus screening: 50 subprocesses,
5,300 nominal / 6,800 guarded seconds. Outer guard 43,200 seconds (12 hours).
Engineering diagnostics are separate and are not counted as formal evidence.

Prelaunch evidence: [independent engineering verification](v04-cvrp-constructor-repair-diagnostic-20260926.md).
The primary-agent suite passed 136 tests in 71.21 seconds; all four complete
solver diagnostics passed coverage/capacity/fleet/objective and runtime-audit
checks. Both 100-file copies have exactly the same four-file repair, preserving
their unrelated algorithms. Ruff F/E9 and diff checks pass. Existing read-only
`--check` returns `PREPARED`, parses all 37 case inputs, validates the exact
three-file arm difference and 170-subprocess envelope, without creating output
or invoking a provider/solver. Final no-overlap/fresh-output checks precede launch.

Final checks found only dead older experiment panes, no competing solver/tests,
fresh output/session and 62 GiB available disk. The exact launch above was the
only invocation. A subsequent read-only check confirmed PID 242261 still active,
input.json present and no terminal.json. Startup is not a scientific verdict.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926`.
Tmux: `scion-r13-constructor-fixed-b0-20260926`.

## Frozen invocation (executed once after checks)

```bash
/usr/bin/env -i \
  PATH=/home/clawd/miniconda3/envs/claw/bin:/usr/bin:/bin \
  LANG=C.UTF-8 LC_ALL=C.UTF-8 PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  /home/clawd/miniconda3/envs/claw/bin/python -S -B \
  /home/clawd/research/or-autoresearch-agent/scion/run_fixed_candidate_funnel.py \
  --label v04-cvrp-r13-constructor-fixed-b0-20260926 \
  --baseline-source /home/clawd/research/scion-experiment-inputs/v04-cvrp-r13-constructor-fixed-b0-20260926/b0-fixed \
  --candidate-source /home/clawd/research/scion-experiment-inputs/v04-cvrp-r13-constructor-fixed-b0-20260926/r12-a-fixed \
  --problem-spec /home/clawd/research/scion-experiment-inputs/v04-cvrp-r13-constructor-fixed-b0-20260926/b0-fixed/problem-v1.yaml \
  --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r13-constructor-fixed-b0-protocol.yaml \
  --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
  --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r13-constructor-fixed-b0-seeds.yaml \
  --retained-split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r6-minus-2for1-b0-retained-split.yaml \
  --retained-seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r13-constructor-fixed-b0-retained-seeds.yaml \
  --changed-file policies/baseline_modules/destroy_repair.py \
  --changed-file policies/baseline_modules/local_search.py \
  --changed-file policies/baseline_modules/scheduler.py \
  --selected-surface solver_design --time-limit-sec 60 --timeout-guard-sec 30 \
  --outer-hardwall-sec 43200 --memory-mb 4096 \
  --output-dir /home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926
```

Append `--check` for read-only preparation. After launch verify ordinary input
snapshots and actual solver limits using lightweight reads, not more solver
tests. When terminal, analyze complete paired evidence before another rung.

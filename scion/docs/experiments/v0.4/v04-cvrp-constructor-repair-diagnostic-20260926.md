# CVRP constructor recovery: independent engineering verification

This is the user-authorized GPT-6-Astra subagent repair and primary-agent
review, not an autonomous Scion H/C experiment or comparative quality result.
The source implementation is under
`scion/scion/problems/cvrp/policies/baseline_modules/`; no generic core,
adapter, Contract, Verification, Protocol, Decision or objective rules changed.
The repaired solver is not claimed complete for the underlying packing problem.

## Defect and bounded repair

R10/R12's old constructor greedily commits descending-demand customers to the
feasible bin with least remaining space. At a dead end it immediately raises.
The operator-exposed X-n627-k43 example has capacity 110 and 626 customers,
total demand 4713, against 43 * 110 capacity. At the final demand-5 customer,
the old packing has eleven bins with slack two, all others full. Any two-bin
repacking has insufficient combined slack; a generic multi-bin recovery is
needed. Aggregate capacity alone is not a proof that a heuristic finds a packing.

The independent repair preserves every successful greedy path. Only at a dead
end does it expand a group of least-loaded bins, using sparse subset-sum to
fill one bin at a time. Failed attempts do not mutate the bins. One recovery
budget is shared across multiple dead ends and subsequent route ordering:
1,000,000 counted work steps, two seconds local monotonic time and the caller's
tighter remaining time. There is no recursion, capacity-sized array, case-name
or seed special case, external solver, relaxed fleet limit or swallowed failure.
Explicit work/no-packing failure remains ValueError and deadline remains
TimeoutError; neither implies proof of mathematical infeasibility.

Remaining-time passthrough is limited to scheduler.py, route_first_seeding.py
and route_first_heuristic.py. Existing route-first ValueError fallback is not
expanded; timeout/context errors propagate. Unrelated scheduling/search code
is preserved. New files are not introduced into the ordinary algorithm tree.

## Verification evidence

The subagent's 25 focused tests passed in 0.24 seconds. The main agent's wider
CVRP adapter/solution/runtime/deadline/scheduler/fixed-funnel/R7–R13 input suite
passed **136 tests in 71.21 seconds**. New constructor tests include old-path
equality, deterministic repair, three-bin fragmented slack, aggregate-insufficient
and aggregate-sufficient infeasibility, oversized customer, work/deadline limits,
uncommitted failed repair, caller passthrough and 10^12-scaled sparse capacity.
Ruff F/E9 (excluding preexisting star-import rules) and diff checks pass.

The constructor-only real-case check covered all 626 customers exactly once,
43 routes, maximum load 110, and independently recomputed objective equal to
the internal value. Its approximately 0.093-second construction time is a
diagnostic observation, not a performance effect estimate.

The primary agent applied identical minimal repair hunks to two new complete
100-file copies. For three files, original contents equal repository HEAD and
new contents equal the reviewed repair. In scheduler.py, replacing the new
call-site hunk with the old call restores each respective original file exactly.
All other ordinary bytes and file sets are unchanged. Between arms only the
three original research files differ. All Python files parse. No original B0,
R10/R12 source, metric, history or campaign state is modified.

### Independent full-solver diagnostic

Four serial, provider-free checks ran on the already exposed failed instance,
using old R12 seeds and a 30-second external limit (60-second subprocess guard).
Each invocation used its own repaired complete source and actual solver.py CLI,
with `SCION_SELECTED_SURFACE=solver_design`, a clean single-threaded environment,
and a separate JSON output. No tests or competing solver overlapped these checks.
One preceding command used an unsupported `--instance` flag and exited during
argument parsing, before any solve/output. It was corrected to the positional
instance syntax; this is not a failed algorithm result or formal retry.

| Arm | Seed | Wall seconds | Routes / fleet violation | Result |
|---|---:|---:|---|---|
| B0-fixed | 110059 | 23.804 | 43 / 0 | All checks pass |
| B0-fixed | 110063 | 23.621 | 43 / 0 | All checks pass |
| R12-A-fixed | 110059 | 23.626 | 43 / 0 | All checks pass |
| R12-A-fixed | 110063 | 23.626 | 43 / 0 | All checks pass |

All four loaded and kept the intended algorithm active, reported zero algorithm
errors and valid solutions, and terminated on the normal algorithm time limit,
not constructor exception/fallback. The problem-owned independent checks
verified customer coverage/uniqueness, capacity and recomputed distance/fleet
objectives against actual route outputs. No diagnostic distance comparison is
used to choose, tune or claim superiority of an arm. Different wall-clock
search outputs are not a deterministic-construction test.

Raw outputs, separate from formal R13:

- [B0-fixed / 110059](/home/clawd/research/scion-experiment-inputs/v04-cvrp-r13-constructor-fixed-b0-20260926/engineering-diagnostics/b0-fixed-110059.json)
- [B0-fixed / 110063](/home/clawd/research/scion-experiment-inputs/v04-cvrp-r13-constructor-fixed-b0-20260926/engineering-diagnostics/b0-fixed-110063.json)
- [R12-A-fixed / 110059](/home/clawd/research/scion-experiment-inputs/v04-cvrp-r13-constructor-fixed-b0-20260926/engineering-diagnostics/r12-a-fixed-110059.json)
- [R12-A-fixed / 110063](/home/clawd/research/scion-experiment-inputs/v04-cvrp-r13-constructor-fixed-b0-20260926/engineering-diagnostics/r12-a-fixed-110063.json)

## Remaining risk and next question

Recovery is a bounded max-fill heuristic, not a complete packing solver. Other
feasible instances can still fail; preserve those failures. No held-out frozen
or retained solve was used for repair. These private diagnostics must not enter
Scion H/C inputs. The known validation block is development evidence now.

The independently preregistered
[R13 comparison](v04-cvrp-r13-constructor-fixed-b0-preregistration-20260926.md)
tests complete R12-A-fixed against B0-fixed, with unchanged gates/budgets and
conditional unopened frozen/retained stages. Neither engineering success nor
that new comparator can silently establish superiority over unchanged B0.

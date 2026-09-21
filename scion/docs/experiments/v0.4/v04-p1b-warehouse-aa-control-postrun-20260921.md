# P1b Warehouse A/A wiring control

Runtime: `e405bfd2`, the same frozen runtime used for R6. These runs are
provider-free diagnostics over the real Warehouse solver, not algorithm
research, promotion or retained-improvement evidence. H/C, provider, Contract
and Verification counts are zero; the fixed driver invokes complete-pair
canary, Protocol, Safe Features and deterministic Decision where comparable.

## First control: incomplete comparator evidence

[Prospective design](/home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-20260921/PREREGISTRATION.md),
[input](/home/clawd/research/scion-experiments/v04-p1b-warehouse-aa-control-20260921/input.json),
[terminal](/home/clawd/research/scion-experiments/v04-p1b-warehouse-aa-control-20260921/terminal.json),
[metrics](/home/clawd/research/scion-experiments/v04-p1b-warehouse-aa-control-20260921/metrics/9c99f82d-dd50-4638-8f91-eaad22517510.json).

Canary passed. On small_1/small_2 at seeds 30011/30013, only 2/4 pairs were
valid. Both source arms returned infeasible on small_2 at both seeds, despite
successful process exits. Protocol correctly classified two shared failures,
and the fixed driver returned `completed_incomplete /
INCOMPLETE_COMPARATOR_EVIDENCE` with `decision=null`. No frame/schema exception
occurred. This is not a complete control pass, nor evidence of candidate harm.
The exact solver infeasibility cause was not repaired or claimed resolved.

## Second control: complete wiring evidence

[Prospective fixture-change record](/home/clawd/research/scion-experiment-inputs/v04-p1b-warehouse-aa-control-r2-20260921/PREREGISTRATION.md),
[input](/home/clawd/research/scion-experiments/v04-p1b-warehouse-aa-control-r2-20260921/input.json),
[terminal](/home/clawd/research/scion-experiments/v04-p1b-warehouse-aa-control-r2-20260921/terminal.json),
[metrics](/home/clawd/research/scion-experiments/v04-p1b-warehouse-aa-control-r2-20260921/metrics/f025e458-b392-457a-ad53-4c62079102bb.json).

The second run was explicitly preregistered as outcome-informed wiring
diagnosis, replacing only small_2 with the public instance_development fixture
already covered by `surrogate/tests/test_development_solver.py`. Code, source
arms, gates, seeds, canary and resource limits were unchanged. The two source
arms differ only by a comment in `operators/change_vehicle_type.py`.

Canary passed; all 4/4 pairs were valid, with zero failures and case W/L/T
0/0/2, median 0 and CI [0,0]. The unchanged Protocol returned
`SCREENING_FAIL_WIN_RATE`; deterministic Decision returned `CONTINUE_EXPLORE`.
The terminal was `completed / NOT_CONFIRMED`. This expected A/A negative
confirms the complete wiring path, not a solver improvement. No held-out stage
was opened. Each run consumed ten subprocesses, 20 nominal and 170 guarded
subject-seconds under its own fresh output root.

Both outputs are retained unchanged. No scientific gate was relaxed and no
Warehouse result was used to select or alter R6's candidate or population.

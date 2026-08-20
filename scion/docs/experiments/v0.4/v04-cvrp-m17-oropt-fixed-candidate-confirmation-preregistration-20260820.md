# CVRP M17 `_or_opt` fixed-candidate confirmation preregistration

**State:** `TERMINAL_CONFIG_INVALID_BEFORE_FORMAL_POPULATION`

## Scientific object

Does the exact M16 candidate-2 `_or_opt` implementation retain a
Protocol-qualified total-distance advantage over exact M16 B0 on a new
outcome-blind-to-this-candidate six-case/four-seed population?

This is one fixed-candidate expanded screening, not another Agent adaptation.
Provider, H, C, patch generation, repair, retry, resume, promotion and automatic
next-round counts are zero. The result stops after one current Protocol, Safe
Feature and Decision call whether positive, negative or incomplete.

The candidate is copied byte-for-byte from M16 candidate workspace
`candidate-f3tttc0t`. Its 98-file source tree differs from B0 in exactly
`policies/baseline_modules/local_search.py`: B0 SHA256
`714fd09a6160bcad55f2f6590a7d4c3a267a85588a96955731ee29e2716124e5`,
candidate SHA256
`932779e82656f65135246ebb3606812b90e750c1758ea488703d337fdb6843f8`.
The exact source already passed M16 public development checks, formal Contract,
Verification and canary. M17 reruns the canary but does not mint or infer a new
Contract/Verification result.

## Outcome-blind population

Before any M17 solver call, all CVRPLIB paths mentioned by prior v0.4
experiment records or the current CVRP package were excluded. With salt
`v04-cvrp-m17-oropt-confirmation-20260820|population-v1`, remaining regular
parseable instance/solution pairs were ranked by
`sha256(salt + NUL + relative_path)`. The first member was selected from each
of A, B and P, and from X dimension strata 200-349, 350-499 and 500-699:

- A-n37-k5, B-n51-k7, P-n50-k8;
- X-n237-k14, X-n351-k40, X-n627-k43.

The same rule with salt suffix `seeds-v1` ranks unused integers 4001-4999; the
first four are 4212, 4351, 4758 and 4843. No candidate output was observed in
selection. The independently ranked canary seed is 4770. Input files are
private read-only copies, not paths into the mutable dataset. The Protocol uses
paired-effect case medians, protected
`fleet_violation`, total-distance practical delta 2, the R3 numerical gates and
`require_expanded_for_pass=true`.

## Resources, stops and claims

There are 24 formal pairs / 48 formal solver subprocesses plus one strict
B0-then-candidate canary pair, for 50 subprocesses. Exact nominal solver time
is 2,660 seconds; adding the 15-second per-process guard gives 3,410 seconds.
The outer hardwall is 5,400 seconds, concurrency is one, and all provider
budgets are zero. Any source/data/config mismatch stops in read-only check;
canary invalidity, hardwall, interrupt or incomplete execution writes one typed
terminal and stops. There is no substitution or third arm.

A positive result means only that the exact outcome-known M16 candidate is
supported on this declared confirmation population under the current carrier.
It does not establish independent candidate discovery, isolated causal effect
of `_or_opt`, validation/frozen success, promotion, retained champion,
production readiness or global CVRP generalization.

## Frozen invocation

The launch binds the clean carrier that contains this preregistration, config
and driver, verifies the unchanged input summaries in
`campaign_out/v04-cvrp-m17-oropt-confirmation-20260820-input`, and requires the
fresh output root
`/home/clawd/research/scion-experiments/v04-cvrp-m17-oropt-confirmation-20260820`.

```bash
cd /home/clawd/research/or-autoresearch-agent/scion
PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion:/home/clawd/.local/lib/python3.12/site-packages:/home/clawd/miniconda3/envs/claw/lib/python3.12/site-packages \
PYTHONDONTWRITEBYTECODE=1 \
/home/clawd/miniconda3/envs/claw/bin/python -S -B \
  /home/clawd/research/or-autoresearch-agent/scion/run_fixed_candidate_screen.py \
  --config /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-m17-confirmation-population.json \
  --input-root /home/clawd/research/or-autoresearch-agent/campaign_out/v04-cvrp-m17-oropt-confirmation-20260820-input \
  --output-dir /home/clawd/research/scion-experiments/v04-cvrp-m17-oropt-confirmation-20260820
```

## Terminal record

M17 ran once from clean carrier
`4c35323c5270dbfdfce6b27f2866273315e13808`. The strict B0-then-candidate
canary consumed two 10-second solver subprocesses and passed. Before the first
formal population pair, `ExperimentProtocol` rejected the configuration
because `n_cases_modify/create=6` was not strictly smaller than
`expand_to_modify/create=6`. The driver wrote
`failed / UNHANDLED_EXCEPTION / expanded case population must be larger than
the initial population` and exited 2.

There is no raw metrics file and no ProtocolResult, Safe Feature, Decision or
candidate-quality observation. Provider, H, C and patch calls are zero. The
preserved root contains only `input.json`, the empty subject-workspace
directory and `terminal.json`. It is not deleted, resumed or retried under the
M17 label.

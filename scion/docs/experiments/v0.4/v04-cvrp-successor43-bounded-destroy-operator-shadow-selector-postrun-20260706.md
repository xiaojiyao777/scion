# CVRP Successor43 Destroy-Operator Shadow Selector Postrun

Date: 2026-07-06

## Run

- Run root: `/home/clawd/research/scion-experiments/v04-cvrp-successor43-bounded-destroy-operator-shadow-selector-server-claw-2r-gpt55-2r-gpt55-20260706T114850Z-claw`
- Launcher commit: `52131c59`
- Model: local `gpt-5.5`
- Resume source: successor42b prompt-contract retry campaign
- Status: valid, complete, postrun-ready
- Stop reason: `max_rounds_exhausted`
- Effective rounds: 2

## Purpose

Successor43 tested `bounded_destroy_operator_shadow_selector`, a CVRP-owned
ALNS destroy-choice shadow selector in
`policies/baseline_modules/destroy_operator_selector.py` with minimal
`scheduler.py` wiring. It compared the adaptive-weight default destroy choice
against one alternate existing destroy operator using the same repair and q
before embedded VNS.

## Protocol Evidence

Row 1 screened 48/48 pairs with zero failed pairs. Pair W/L/T was `28/15/5`.
The branch was marginal: median delta `2.25`, CI `[-2.25, 8.25]`, below the
CVRP 9.9 MDE.

Row 2 expanded to 64/64 pairs with zero failed pairs. Pair W/L/T was
`33/22/9`. The branch remained marginal: median delta `2.25`, CI `[-3.5, 8.0]`,
again below MDE. Runtime evidence was sufficient but not a promotion feature:
median runtime ratio was `1.000338`, median runtime delta `15ms`.

Mechanism telemetry was not fake-active. Row 2 observed shadow activation on
all 64 candidate pairs with `3047` attempts, `1387` accepted alternate
selections, `242555ms` shadow-selector runtime, and positive pre-VNS selector
delta sum. The local pre-VNS selector signal did not translate into
promotion-grade or protected-case-safe solver evidence.

## Case Pattern

Stable positives:

- `A-n64-k9`: `4/0/0`, sum delta `50`
- `A-n80-k10`: `3/0/1`, sum delta `74`
- `E-n101-k14`: `3/1/0`, sum delta `19`
- `E-n101-k8`: `3/1/0`, sum delta `29`
- `M-n151-k12`: `4/0/0`, sum delta `48`
- `tai150c`: `2/0/2`, sum delta `12`

Stable losses and unsafe cases:

- `B-n63-k10`: `1/3/0`, sum delta `-52`
- `B-n67-k10`: `1/3/0`, sum delta `-54`
- `P-n65-k10`: `0/3/1`, sum delta `-21`
- `P-n101-k4`: `1/3/0`, sum delta `-22`
- `CMT2`: `1/2/1`, sum delta `-35`
- `CMT4`: `2/2/0`, sum delta `-12`

All inspected negative pairs preserved feasibility and route count and did not
fail by timeout. The failure mode is search trajectory quality, not route
count, fleet violation, or infra failure.

## Trace Audit

The target-intent and hypothesis prompts were adequately grounded. The accepted
proposal matched the intended target file, mechanism id, exact
`material_difference` schema, and CMT2/CMT4 protection commitment.

Generated code stayed within the CVRP solver boundary and was compact: one new
selector module plus minimal scheduler import/call wiring. It did not create
helper sprawl or move CVRP semantics into generic core.

The design was incomplete in four important ways:

- Shadow trials reused the main RNG, so rejected or no-op trials still changed
  later stochastic trajectory.
- The selector returned only a candidate solution, not the selected destroy
  index/name. Scheduler adaptive weights and ALNS traces still credited the
  default destroy operator even when the alternate candidate was used.
- Telemetry did not record enough default-versus-alternate metadata: selected
  label, reject reason, default/alternate route count, and feasible/max-route
  status were missing or not directly auditable.
- The acceptance condition proved only pre-VNS local improvement, not post-VNS
  or simulated-annealing trajectory safety.

## Judgment

Successor43 is valid active marginal evidence, not a long-run candidate. Treat
unchanged `bounded_destroy_operator_shadow_selector` as reviewed/default-avoid
for v0.4.

One protected same-line follow-up is justified because the mechanism had direct
local signal and the failures are specific design-contract gaps, not absence of
activation. That follow-up must not be threshold tuning or a raw rerun. It must
repair RNG isolation, selected-operator attribution, and diagnostics while
preserving the CVRP-owned selector module and minimal scheduler wiring.


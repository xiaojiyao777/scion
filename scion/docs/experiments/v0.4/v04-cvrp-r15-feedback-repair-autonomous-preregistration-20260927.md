# CVRP R15: actionable development feedback and broader initial screening

Terminal update (2026-09-28, original preregistration below unchanged): completed
at `2026-09-27T22:04:54.956555+00:00`, twelve evaluated stages / 136 valid
pairs, no promotion. Expanded screening passes; complete validation fails
quality. The final fresh initial-screen positive is unexpanded. See the
[read-only postrun](v04-cvrp-r15-feedback-repair-autonomous-postrun-20260928.md).

State: launched once at `2026-09-27T13:54:37Z`, driver PID 289227,
tmux `scion-r15-feedback-repair-autonomous-20260927`. September 27 user explicitly
authorizes coordinated subagent repairs followed by one fresh experiment.
R14 remains terminal; original sources, metrics and Decisions stay unchanged.
No new commit/push was requested at launch. The subsequent September 27 user
request authorizes committing and pushing the frozen change set without
changing the running runtime or scientific inputs.

Profile: Code Repair Or Feature Work, with the required complete V3/addendum,
operations/runbook/postrun handoff and linked R14 postrun/preregistration.

## Repairs and claim boundaries

The shared runtime repairs two research-support defects, not algorithm quality:

- Development preflight exposes bounded typed check/reason and an eligible
  patch-relative location to C, rather than opaque rejection. Import/API,
  editable/frozen boundaries, isolated tests and four-test accounting remain.
  No raw exception, private diagnostic, arbitrary checker text or new gate.
- H/C system guidance distinguishes current cumulative source, inherited
  behavior and the formal champion comparator. A replacement must be actual
  code; cumulative whole-candidate evidence does not isolate a latest edit.
  Untested populations/unexecuted mechanisms bound claims. No required read,
  ablation, automatic rollback, novelty test or host-selected mechanism.

Prompt coverage includes direct H/C and bounded H/K2/C. Guidance cannot
guarantee the model's reasoning: postrun must inspect actual H, code and paths.
Protocol/Decision implementations and problem algorithms are unchanged.

Because shared research boundaries changed, focused regressions, full suite
and an independent Warehouse H/C control on the same frozen runtime must
finish before this run. A valid negative control is not a quality failure;
a framework defect blocks launch until repaired and retested.

## Ordinary source and evidence

Use exactly the same complete starting source as R14:
`/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate`.
It is R12-A-fixed, 100 files, with the separately authorized operator-assisted
constructor repair. No R14 final branch was confirmed better, so no final
sibling is selected or merged; no host algorithm patch is applied. This is
a fresh baseline selection, not restoration of a terminal/live branch.
Version 1 does not confer promotion or superiority over either B0 variant.

[Research input](inputs/v04-cvrp-r15-feedback-repair-autonomous-research-input.json)
retains all five R4/R5/R6/R8/R13 observations and the preceding question, then
adds R14 screening-only facts and this prospective population/comparator.
The full R14 safe history is appended, not ranked or success-selected.
Fourteen explicit ordered files: R3–R3i, R7, R9, R11, R12, R14.
147 raw / 124 H-visible scientific/Contract rows; 5,887,465 bytes.
The 23 operational rows stay excluded. No private validation/frozen case,
failure, regression recipe or metric enters H/C.

Question: can autonomous H/C improve distance quality and stability relative
to this local champion under unchanged solver budgets and scientific gates?
All local effects compare cumulative candidate versus current champion,
not latest patch versus preceding branch or retained improvement over B0.
Do not pool R13, R14 and R15 effects.

## Prospective population and resources

[Protocol](inputs/v04-cvrp-r15-feedback-repair-autonomous-protocol.yaml)
changes only version, canary seed and initial screening coverage from R14.
Initial 5 cases × 2 seeds: B-n34-k5, tai100a, X-n351-k40, X-n190-k8,
X-n513-k21. This includes the previously unmeasured X190/X513-targeted
mechanisms without choosing an algorithm for H/C.
Expansion adds A-n54-k7, then all 6 cases × 4 seeds are evaluated again.
The existing runtime requires strict case-population expansion; therefore
6 initial / 6 expanded is not valid merely by adding seeds. R15 keeps that
boundary and `require_expanded_for_pass=true`; it does not change core
selection or weaken the final scientific thresholds.

The [R7 split](inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml)
is unchanged. These are outcome-known adaptive development cases. More initial
coverage changes R14's initial estimand and cost, not independence.
Validation 6 × 2 is already exposed development/completeness evidence;
frozen 12 × 2 is conditionally unopened and reuses the exact candidate.
The separate retained block is not executed. No case drop after outcomes.

First nine primes above 140,000 selected prospectively:
[ledger](inputs/v04-cvrp-r15-feedback-repair-autonomous-seeds.yaml).

| Stage | Seeds |
|---|---|
| screening | 140009,140053,140057,140069 |
| validation | 140071,140111 |
| frozen | 140123,140143 |
| canary | 140159 |

Scientific gates, full pairs, runtime audit, feasibility/fleet protection,
practical effect, case quality, CI and deterministic Decision are unchanged.
Dimension limits remain 60/90/120/180/240 seconds; canary 10.
Algorithm-local fraction/reserve unchanged. Autonomous arm order remains
champion-first, a limitation requiring independent counterbalanced confirmation.

Fresh K=1 / maximum three branches / 12 formal evaluated stages.
Model gpt-5.6-sol, high; H 180 s / C 300 s. SDK retry zero; at most two charged
typed-transient redispatches. Explicit 600 physical-call cap and 172800-second
outer guard. Existing R3i C limits: 12 turns, eight reads, eight searches,
four tests, no transcript-character cap. Parameter search disabled.
No cap increase or attempt-limit relaxation is introduced.
An initial candidate now has ten formal pairs rather than six; all-stage
per-subprocess limits remain equal across both arms. Screening-only worst
nominal envelope at twelve expanded stages is below 17.7 hours (including
twelve canaries); held-out stages, proposal time and guards share the 48-hour
outer limit. This is a stop guard, not an assurance of completion.

## Verification and frozen invocation

Runtime checkout `v0.4-dev`, HEAD `964a9622`, with uncommitted repairs,
tests and R13–R15 documentation/inputs. Focused feedback/security/session tests:
144 passed in 12.93 s; prompt/context/session tests: 195 passed in 2.54 s;
CVRP/Warehouse prospective-input tests: 6 passed. These sets overlap and must
not be summed. Independent read-only review found no blocking issue. Full
suite: 2471 passed, 1 skipped in 430.51 s. The first Warehouse control input
was rejected before output/provider/solver creation due to public-test/formal
case overlap. The boundary remains intact. Its input-only correction is
separately preregistered as [control r2](v04-r15-warehouse-feedback-control-r2-20260927.md):
7 input regressions and full composition prechecks pass. It completed normally
at 13:51:19 UTC: two valid negative screening stages, actual H/C and source
fidelity checked, one safely abandoned Code attempt, 48 successful calls,
no framework blocker or promotion. Sibling-inheritance miswording remains a
model reasoning limitation, not source contamination. Runtime is unchanged
and frozen for both runs. CVRP public/formal closure also passes; all final
tests and other solver jobs finished before launch. Final provider credential /
model-catalog and absent output/session checks passed without secret output.

Startup verification: [status](/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/status.json)
is running, initial champion v1. All 100 initial snapshot files exactly equal
the selected R12-A-fixed source. The first two actual H calls succeeded at
attempt index zero on gpt-5.6-sol; the exact 6688-character question, five
observation / 124 prior-history indexes and repaired cumulative-source guidance
are present. This proves startup/input delivery, not attention, compliance or
algorithm improvement. No formal result yet. Only status documentation changes
during this run; do not resume any terminal predecessor.

Read-only application of the repaired static projection to exact R14 draft 2
and draft 3 reproduces respectively C9/sensitive_api_rejected and
C8/import_whitelist_rejected, both locating
`policies/baseline_modules/scheduler.py`. Original traces/source are untouched;
no candidate was executed or rerun. This directly checks the motivating
failure feedback without claiming the final untested R14 draft would pass.

Read-only preparation passes: all 100 complete source files, 25 case inputs,
source/fresh-output/expansion checks, 14-file ordinary history and exact H
question (6688 characters), 124 history rows and five observations.
No solver, provider dispatch or output directory was created.
Prospective input tests: 4 passed. No private later-stage diagnostics in input.

Completed before launch: all agents finish, inspect diffs, focused and full suites,
Ruff/diff checks, independent control, provider credential/model catalog
without secret output, no competing tests/solver/cleanup, fresh output/tmux.
Runtime/source/data/inputs were frozen and this command was launched once.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927`.
Tmux: `scion-r15-feedback-repair-autonomous-20260927`.

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-5.6-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  SCION_MODEL=gpt-5.6-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem-v1.yaml \
    --source-tree /home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r15-feedback-repair-autonomous-research-input.json \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3-normal-k1-sol-20260828-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3b-normal-k1-sol-20260829-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3c-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3d-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3e-normal-k1-sol-20260830-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3f-normal-k1-sol-20260831-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3g-normal-k1-sol-20260901-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3h-normal-k1-sol-20260902-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r3i-normal-k1-sol-20260903-r1/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r7-autonomous-source-continuation-20260921/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r9-post-b0-autonomous-20260922/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r11-wide-budget-autonomous-20260923/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r12-post-r11-autonomous-20260924/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r14-post-r13-autonomous-20260927/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r15-feedback-repair-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r15-feedback-repair-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927
```

At startup compare all 100 initial source files and inspect only bounded actual
H context/call fields: exact question, five observations, 124 prior rows and
one successful dispatch. Do not force research actions or infer scientific
success from startup. During measurement only launch-status docs may change.
After terminal completion audit H/C reasoning, preflight feedback use,
complete source continuation and raw paired evidence; preserve any negative
or incomplete result. Never resume this terminal campaign.

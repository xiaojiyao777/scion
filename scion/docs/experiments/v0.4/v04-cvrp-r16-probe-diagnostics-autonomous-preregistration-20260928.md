# CVRP R16: bounded self-test hints and real-entry research support

State: preregistered, not launched. User's September 28 follow-up approves
the R15 analysis direction, a fresh experiment, Git commit and push.
Profile: Code Repair Or Feature Work; canonical entry, full V3/addendum,
runbook and linked R15 postrun/preregistration read. R15 is terminal and is
not resumed; all original evidence and Decisions are preserved.

## Intervention and boundaries

Shared development feedback adds one optional, untrusted first-failure hint:
phase (collection/setup/call/teardown), exception category, and an optional
one-based line **in the exact submitted self-authored probe**, never a path,
exception message, traceback, locals or test data. Collection wrappers are
unwrapped only structurally; skip/xfail do not replace a real failure.
Normal child stdout/stderr is discarded. An anonymous output descriptor is
read at most 513 bytes; reports over 512 bytes or outside the exact schema
are dropped. The consumer independently rechecks enums and line bounds.
The hint does not change pytest exit semantics, host checks, exact-patch
failed-falsifier rejection, four-test accounting, or immediate passing ready.
It can be spoofed by tainted candidate/probe code and is not formal evidence.
Missing/invalid hints leave the original outcome intact.

H/C guidance distinguishes helper execution from real-entry reachability,
and mock wiring from real collaborator compatibility. The problem-owned
public test source adds an optional copyable PUBLIC_PROBE_EXAMPLE: real solve,
a wrapping observer around real construction, and real route/state/operators.
Its tiny synthetic shape and lightweight timing/context fixture are explicitly
not the production context, activation proof for an arbitrary new mechanism,
or a scientific quality result. It is a string example, not another collected
public/Verification test. There is no mock ban, required probe/read, forced
target/mechanism, novelty/activity gate or algorithm patch.

These are research-support changes, not guaranteed improvement in reasoning.
Postrun must inspect actual H/C use and test claim fidelity.
Contract/Verification/Protocol/Safe Features/Decision remain unchanged.

## Complete source, population and evidence

Starting tree is the exact same **100-file R12-A-fixed source** as R14/R15:
`/home/clawd/research/scion-experiments/v04-cvrp-r13-constructor-fixed-b0-20260926/input_snapshots/candidate`.
No R15 sibling selection, merge or host solver modification. Its earlier
constructor repair remains operator-assisted engineering, not autonomous
discovery. Fresh champion v1 is not promoted or retained-superior to B0-fixed
or original B0. Public development references come from the problem package;
the added example does not alter these 100 algorithm-workspace files.

[Research input](inputs/v04-cvrp-r16-probe-diagnostics-autonomous-research-input.json)
retains the five complete R4/R5/R6/R8/R13 observations and preceding question,
then adds R15 screening/Verification facts only. Fifteen complete ordered
H-only histories: R3–R3i, R7, R9, R11, R12, R14, R15.
R15 contributes all twelve ordinary rows, not just successful candidates.
Read-only loading confirms 159 raw / 136 H-visible rows, 6,670,053 bytes;
the exact 8502-character question and all five observations reach H projection.
No private later-stage case/outcome, validation diagnosis or repair recipe is
supplied. No algorithm is prescribed; localized pair-bound/oracle findings and
the last sampled-SWAP signal remain distinct, uncertain leads.

[Protocol](inputs/v04-cvrp-r16-probe-diagnostics-autonomous-protocol.yaml)
equals R15 except version and canary seed. Same R7 split: initial five cases
(B34, tai100a, X351, X190, X513) × two seeds; expansion adds A54 and uses
all six cases × four seeds. Strict expansion required. Six-case validation ×
two is already operator-exposed, not independent confirmation; twelve frozen
cases × two remain conditionally unopened. Separate retained block not run.
All original case-quality, effect/CI, feasibility/fleet, runtime and exact-candidate
reuse gates stay intact. No case drop or outcome-selected fresh candidate.

[Seeds](inputs/v04-cvrp-r16-probe-diagnostics-autonomous-seeds.yaml):
first nine primes above 160000, selected before outcomes.

| Stage | Seeds |
|---|---|
| screening | 160001,160009,160019,160031 |
| validation | 160033,160049 |
| frozen | 160073,160079 |
| canary | 160081 |

Dimension limits 60/90/120/180/240 seconds, canary 10, algorithm fraction/reserve
unchanged; champion-first order still requires later balanced confirmation.
Adaptive screening is not an independent effect estimate. This is not a
controlled causal comparison of prompting against R15.

K=1, at most three branches, twelve evaluated stages; gpt-5.6-sol high,
H 180 s / C 300 s, SDK retries zero, at most two charged typed redispatches.
600 physical calls, 172800-second outer guard; existing R3i C limits of
12 turns/eight reads/eight searches/four tests, no transcript character cap.
Parameter search disabled. No global or local budget relaxation.

## Verification and launch conditions

Focused diagnostics/security/session/prompt/input tests passed (176 before
the skip/xfail regression was added); all 37 dedicated probe tests pass after
that correction. Ruff F/E9, formatting and diff checks pass. Read-only checks
pass for all 100 unchanged source files, 25 parsed case inputs, full declared
public/formal closure, strict expansion, resource/production/Verification setup
and exact H projection. No provider, solver or output directory is created by
that preparation. Full suite: **2514 passed, 1 skipped in 426.78 s** on the
final runtime. Independent Warehouse control remains pending.
Two final ephemeral development checks on the exact selected R12-A-fixed
algorithm also pass all D1/D1b/D2/D3/D4 checks: the public example passes its
probe; an intentional missing-attribute probe returns failed/call/attribute_error
at probe line 2. This checks end-to-end feedback separately from scientific
quality. Scratch is cleaned; selected source and old campaigns are untouched.
The same frozen runtime must complete
[Warehouse control](v04-r16-warehouse-probe-control-20260928.md) before CVRP.
A valid negative control is acceptable; a framework defect blocks launch.
No concurrent tests, solvers or maintenance during either formal run.

Runtime checkout: v0.4-dev, approved P12 repair/tests plus R15 analysis and
R16 inputs/docs, to be committed before the control. Exact commit/launch
status will be recorded below; the CVRP run has not yet started.

Output: `/home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928`.
Tmux: `scion-r16-probe-diagnostics-autonomous-20260928`.

## Frozen invocation (not yet executed)

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928
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
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r16-probe-diagnostics-autonomous-research-input.json \
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
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r15-feedback-repair-autonomous-20260927/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r16-probe-diagnostics-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r16-probe-diagnostics-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928
```

Before dispatch verify provider credentials/model catalog without secret output,
absent output/session and no competing work. After startup compare every initial
source file and inspect actual H question/history/prompt delivery and successful
provider calls. Startup is not algorithm success. Freeze implementation/input
files; only status docs/Git work during measurement. Terminal analysis must
separate framework correctness, reasoning/test quality, valid scientific
evidence and retained improvement.

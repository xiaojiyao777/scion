# CVRP R25: counterfactual evidence and stable whole-solver advantage

State: **completed/valid12/12; no promotion**. See the
[October28 terminal analysis](v04-cvrp-r25-counterfactual-evidence-autonomous-postrun-20261028.md).
Startup observations below are historical, not current process state.
The subsequent October26 request explicitly
authorizes next optimization, experiment design, launch, Git commit and push.
The [R24 terminal analysis](v04-cvrp-r24-stable-advantage-autonomous-postrun-20261026.md)
and its optional test-support repair precede this fresh campaign. Never resume
R24 or reinterpret its no-promotion terminal as resource exhaustion.

## Complete source and bounded intervention

Use the exact complete100-file R22 C3 source preserved as R23's candidate:
`/home/clawd/research/scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018/input_snapshots/candidate`.
It is also R24 championv1, not any R24 branch or original B0. No algorithm edit,
reconstruction, sibling merge or state restore. Choosing this comparator keeps
the complete source already preserved; A2's favorable screening does not justify
silently promoting or reconstructing its absent original workspace as champion.

Only the research-support and ordinary-input intervention changes:

- Optional independently rescored counterfactual worksheet and five regressions
  distinguish additional trials, retained own gain and gain over inherited best.
  Correctness/coverage tests remain useful even without a positive witness.
  The two collected candidate checks, production algorithms and core stay unchanged.
- Retain the entire historical R24 question and all five observations unchanged;
  prepend a current-source frame and append every R24 screening case/seed cell
  from all11 screening stages, without favorable-case selection.
- Supply all22 chronological whole history files: R24's21 plus its complete
  safe research_history. Public development-probe limitations are research facts,
  not operational failures or formal gate conditions.
- Let H/C choose algorithms/tests. No forced file, mechanism, time allocation,
  positive fixture, telemetry quota or additional quality gate. Exact evaluator
  changes may correctly preserve local optima; added capability and comparative
  final quality are separate hypotheses.

No shared core, adapter, generic prompt, Contract, Verification, Protocol or
Decision modification; no Warehouse control is required. Private validation
identities/results from the operator report are excluded. The R24 screening
A2 result describes its cumulative registry-plus-cache source, not cache-only
causality. B2 includes its branch history, not inherited A/C/D work.

## Preregistered scientific and resource bounds

[Research input](inputs/v04-cvrp-r25-counterfactual-evidence-autonomous-research-input.json),
[Protocol](inputs/v04-cvrp-r25-counterfactual-evidence-autonomous-protocol.yaml),
[seeds](inputs/v04-cvrp-r25-counterfactual-evidence-autonomous-seeds.yaml).

Exactly R24 Protocol except version/canary seed: initial5 cases×4 seeds;
mandatory expanded6×8; conditional validation6×4 and frozen12×4 on the same
R7 split. Same zero equivalence band, feasibility/fleet constraints, case-net/
loss-rate/CI gates, practical deltas2/1 and dimension limits60/90/120/180/240s,
canary10s. No extra sampling after observing outcomes and no case exceptions.

Prospective seeds are the first17 primes above310000:

|Stage|Seeds|
|---|---|
|Screening|310019,310021,310027,310043,310049,310081,310087,310091|
|Validation|310111,310117,310127,310129|
|Frozen|310169,310181,310187,310223|
|Canary|310229|

gpt-6.1-sol high; K1/max3 branches;12 evaluated stages/600 physical calls;
two charged typed redispatches/SDK retry0;172800-second48-hour outer guard;
H180/C300-second transport; unchanged12-turn/8-read/8-search/4-test Code limits,
no transcript-lifetime character cap; parameter search disabled.

Ordinary autonomous pairs remain champion-first, not counterbalanced.
Known cases are adaptive research populations; new seeds do not make them
globally unseen. Expanded screens rerun the initial cells, so overlapping stages
must not be pooled as independent evidence. New source changes may alter timed
trajectories even when isolated local outputs are equivalent. A future balanced
fixed-source confirmation and original-B0 retained comparison remain separate.

## Prospective analysis and launch boundary

Separate framework correctness, research fidelity, diagnostic claim strength,
real changed-path entry/completion/gain and complete-solver final advantage.
Audit all losses, negative controls and missing evidence. A passing weaker test
does not repair a failed stronger claim. Do not infer unique mechanism benefit
from new nominations, family telemetry, more iterations or phase timing.
Retained own progress is not superiority over a comparator; the initial checkpoint
is post-initial-local-search. No mandatory research style is introduced.

Entry HEAD/local origin5a27803e on v0.4-dev, with this turn's analysis/support/
inputs/tests/handoff uncommitted. User explicitly requests Git publication after
launch. Record actual startup provenance; do not retroactively call it a clean
commit. Runtime and scientific files freeze before dispatch; after launch only
read-only startup checks, lifecycle docs and Git, no tests/maintenance/solver
competition or scientific/source edits.

Prelaunch: complete source equality and Python parse; all25 data cases and
public/formal closure; unchanged resources/gates; fresh seeds; all22 whole
histories and exact H question/history/source projections; C editable/public
separation; focused regressions and full optional example in an isolated C3 copy;
model listing and one bounded health inference; no active campaign/test/solver,
sufficient disk and fresh root/session.

Output:
`/home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026`.
Tmux: `scion-r25-counterfactual-evidence-autonomous-20261026`.

## Direct invocation used once (historical; never resume a terminal)

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-6.1-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/scion-experiment-inputs/v04-cvrp-r6-minus-2for1-b0-20260921/data \
  SCION_MODEL=gpt-6.1-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/scion/problems/cvrp/problem-v1.yaml \
    --source-tree /home/clawd/research/scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018/input_snapshots/candidate \
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r25-counterfactual-evidence-autonomous-research-input.json \
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
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r16-probe-diagnostics-autonomous-20260928/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r17-quota-aware-autonomous-20261003/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r18-research-context-autonomous-20261004/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r19-reliable-probes-autonomous-20261005/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r21-source-grounded-autonomous-20261009/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r22-retained-path-autonomous-20261011/research_history.jsonl \
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r24-stable-advantage-autonomous-20261024/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r25-counterfactual-evidence-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r25-counterfactual-evidence-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026
```

## Verification and actual execution

Prelaunch139 focused regressions pass in39.08seconds; targeted Ruff F/E9,
diff check and CLI help pass. The full26,049-character updated optional example
passes on repository and an isolated unchanged C3 copy in the10-second sandbox;
the two collected candidate tests remain AST-identical. No full-suite claim.

All100 selected source files are read-only and byte-equal to R24 champion C3;
48 Python files parse. All25 declared data cases parse and public/formal closure
passes. The initial data audit mistakenly resolved the public canary under the
external benchmark root; using its declared source-tree path corrects that
audit-only locator. No runtime/data change was needed.

All22 whole histories load235 normalized records; the H projection retains212
safe records plus five observations,217 history entries and30 source entries.
The exact39,150-character current question survives projection. C has19 read-only
bodies (17 support/two public tests) and11 editable bodies, each byte-equal to
its owner, with no overlap. Private-case sentinels are absent. All360 appended
screening cells match their exact original R24 metrics. Context-only diagnostic
H is never dispatched or injected into research.

Model listing and one gpt-6.1-sol high health inference succeed October26
16:01:40.346898 UTC /October27 00:01:40 Beijing,3.730seconds, one physical call,
SDK retry0. No credential is printed or saved. Disk has about66GiB available;
all prior experiment carriers are terminal. Final fresh-root/session/process
checks and startup verification follow. Runtime/support/scientific inputs are
frozen before dispatch; only read-only checks, lifecycle docs and Git afterward.

Launched once October26 16:03:24.960546 UTC /October27 00:03:24 Beijing,
tmux foreground PID1361573. The carrier sets remain-on-exit for its own pane;
all preceding experiments are terminal, the fresh root/session were absent and
no competing campaign/test/solver was found. Entry is5a27803e with this12-file
analysis/support/R25 set uncommitted, explicitly authorized for publication.

Actual initial champion matches all100 C3 files; saved research input, Code
limits and600-call/two-redispatch/172800-second envelope match. Whitelisted
non-secret process environment confirms gpt-6.1-sol high, H180/C300 ceilings and
single-thread numerical settings. No credential was printed or saved.

First H succeeds at16:03:35.155463 UTC /October27 00:03:35 Beijing, attempt0:
`llm_traces/20261026T160335155224_hypothesis_research_turn_2a60958d.json`.
Exact39,150-character question,217 history and30 source indexes match the
independently assembled context after ordinary JSON serialization. Initial
audit compared tuple-valued adjacency fields with JSON lists; normalizing that
representation corrects the audit without any runtime/artifact edit. Private
case sentinels are absent. At the earlier startup snapshot nine completed H
requests had succeeded, zero errors, first proposal and zero evaluated stages.

Runtime/support/scientific files remain frozen after dispatch. Only read-only
startup checks and lifecycle documentation precede the requested Git publication;
Git records its actual result. Startup success is not quality, promotion or
completion of the research objective.

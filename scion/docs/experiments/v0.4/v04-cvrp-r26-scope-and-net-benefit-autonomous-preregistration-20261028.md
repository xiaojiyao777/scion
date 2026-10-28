# CVRP R26: matched diagnostic scope and whole-solver net benefit

State: **running; startup verified, no quality claim**.
The initial October28 request authorizes analysis, optimization and a fresh
experiment, not Git publication or terminal resume. The subsequent Git request
is recorded below; it does not alter the frozen launch inputs.
The [R25 terminal audit](v04-cvrp-r25-counterfactual-evidence-autonomous-postrun-20261028.md)
shows valid negative science, not provider or best-return failure.

## Complete source and intervention

Use unchanged100-file R22 C3 preserved at
`/home/clawd/research/scion-experiments/v04-cvrp-r23-r22-final-local-fixed-20261018/input_snapshots/candidate`.
This equals R25 championv1, not any R25 branch (including its separately named
C3), R23 A or original B0. No host algorithm edit, sibling merge, reconstructed
candidate, source promotion or mutable state restore.

Only problem-owned optional support and ordinary research input change:

- Add a fixed-start eligibility worksheet with independently known24→6 costs,
  full/empty/partly active controls and wrong-scope mutation regressions.
- Clarify non-vacuous specific-path observations, publication versus real reuse,
  independent values, and helper-work versus whole-call overhead. Existing
  real-entry/target-bypass/retention examples remain; no prescribed test style.
- Supply all23 chronological whole histories: the same22 plus all12 R25 safe rows.
  Preserve the entire R25 question and all five observations; prepend the current
  source/net-benefit frame and append all296 R25 screening cells. No cherry-picking,
  private later-stage facts, operational-error history or forced mechanism.

Production solver/core/adapter/generic prompts, Contract/Verification/Protocol/
Decision and the two collected candidate checks remain unchanged. No shared
boundary repair is made, so no Warehouse control is required.

## Prospective science and resources

[Input](inputs/v04-cvrp-r26-scope-and-net-benefit-autonomous-research-input.json),
[Protocol](inputs/v04-cvrp-r26-scope-and-net-benefit-autonomous-protocol.yaml),
[seeds](inputs/v04-cvrp-r26-scope-and-net-benefit-autonomous-seeds.yaml).

Same R25 gates, populations and limits: R7 split; initial5×4, mandatory
expanded6×8, conditional validation6×4/frozen12×4; practical deltas2/1,
zero case-equivalence band, existing case-net/loss-rate/CI gates and
protected feasibility/fleet. Solver dimension bands60/90/120/180/240seconds,
canary10seconds. No new samples after observing outcomes or selective case removal.

First17 primes above320000, disjoint from prior checked-in ledgers:

|Stage|Seeds|
|---|---|
|Screening|320009,320011,320027,320039,320041,320053,320057,320063|
|Validation|320081,320083,320101,320107|
|Frozen|320113,320119,320141,320143|
|Canary|320149|

Same gpt-6.1-sol high, K1/max3 branches;12 evaluated stages/600 physical calls;
two charged typed redispatches, SDK retry0;172800-second48-hour guard.
H180/C300 transport; Code12 turns/8 reads/8 searches/4 tests, no transcript
lifetime character cap. Parameter search remains disabled.

Ordinary autonomous pairs are champion-first, NOT counterbalanced. Expanded
stages rerun initial cells; never pool those as independent evidence.
Known populations are adaptive. Small synthetic tests, saved helper calls and
iteration counts cannot establish net timed quality or original-B0 retention.
A future balanced fixed-source confirmation remains separately preregistered.

## Analysis commitments

Inspect actual H source grounding, complete branch continuation, C implementation,
reference eligibility and expected values; separate helper equivalence, real
caller completion/reuse, accepted/retained gain and paired final advantage.
Audit all negative cases and seed reversals. Missing nonempty observations narrow
a diagnostic claim, not Contract/Decision acceptance. Full/empty/partly active
references must represent the same eligible population; a smaller fixture does
not repair omitted coverage. Include cold construction/miss/eviction/polling
cost when interpreting cache claims, without adding a new performance gate.
No mechanism, target, phase allocation or mandatory positive witness is selected.

## Prelaunch and freeze

Entry checkout clean1d9845db=local origin/v0.4-dev. This analysis/support/input/
test/handoff set is uncommitted; no Git publication requested. Record the exact
uncommitted-at-launch provenance. Freeze runtime/support/science before launch;
afterward only read-only startup checks and lifecycle docs, no competing tests,
solvers, maintenance or scientific edits.

Check complete source equality/48 Python parses; all25 data cases and public/
formal closure; all23 whole histories and exact H/C source/history/question
projection; private exclusion; prospective seeds/resources and focused regressions;
full optional example in isolated repository and selected C3 copies; fresh output/
session, no competing processes, disk, model listing and one bounded inference.

Root: `/home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028`.
Tmux: `scion-r26-scope-and-net-benefit-autonomous-20261028`.

## Direct invocation (fresh run once; never resume terminal state)

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028
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
    --research-input /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r26-scope-and-net-benefit-autonomous-research-input.json \
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
    --research-history /home/clawd/research/scion-experiments/v04-cvrp-r25-counterfactual-evidence-autonomous-20261026/research_history.jsonl \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r26-scope-and-net-benefit-autonomous-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r7-autonomous-source-continuation-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r26-scope-and-net-benefit-autonomous-seeds.yaml \
    --time-limit-sec 60 --rounds 12 --provider-call-cap 600 \
    --provider-transient-retries 2 --outer-hardwall-sec 172800 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-cvrp-r26-scope-and-net-benefit-autonomous-20261028
```

## Verification and execution record

142 focused input/support/diagnostic/public-dependency/Contract regressions pass
in39.38seconds. Targeted Ruff F/E9, CLI help and diff checks pass. The complete
28,780-character optional example passes both repository and isolated unchanged
C3 copies in the existing10-second sandbox; the two collected candidate tests
are AST-identical to HEAD. No full-suite rerun claim.

All100 source files match R25 championv1;48 Python files parse. All25 data cases
parse (the public canary resolves under the source tree), and declared public/
formal closure passes. All23 whole histories yield247 normalized/224 safe records
plus five observations:229 H history and30 source entries. The exact46,995-character
question survives projection. C carries19 read-only and11 editable bodies, each
equal to its owner, with no overlap; private sentinels are absent. Every one of
the296 appended screening cells matches its exact R25 metric.

Model listing and one gpt-6.1-sol high inference pass at October28
12:32:36.174514 UTC /20:32:36 Beijing,9.190seconds, SDK retry0. No secret printed
or stored. Disk has about65GiB available; all previous carriers are dead and no
competing campaign/test/solver is observed. The fresh root/session is checked
again immediately before dispatch. Source/support/science now freeze; only
read-only startup checks and lifecycle documentation follow.

Launched once October28 12:33:40.816188 UTC /20:33:40 Beijing, foreground
tmux PID1451899, own-pane remain-on-exit enabled. Fresh root/session were absent,
all preceding carriers terminal, no competing solver/test/campaign. Runtime is
1d9845db plus this12-file uncommitted analysis/support/R26 set. No Git action.

Actual initial champion matches all100 selected source files. Saved research
input, Code limits and600-call/two-redispatch/172800-second envelope match.
Whitelisted non-secret process settings confirm gpt-6.1-sol high, H180/C300
ceilings and single-thread numerical settings. No credential was printed/stored.

First H succeeds at12:33:53.743672 UTC /20:33:53 Beijing, attempt0:
`llm_traces/20261028T123353743482_hypothesis_research_turn_35f4251f.json`.
Actual46,995-character question and complete229-history/30-source indexes match
independent context assembly after ordinary JSON normalization. Private sentinels
are absent. Three completed H traces succeed at this startup audit, zero errors,
zero evaluated stages. This verifies startup, not algorithm quality. No tests,
competing solvers, maintenance or runtime/support/scientific edits after launch;
only read-only startup checks and lifecycle docs.

## Subsequent Git publication

The October28 follow-up authorizes commit/push of the frozen12-file R25 analysis,
optional support and R26 input/test/handoff set. Read-only Git/diff/carrier/status
checks find R26 live at first Code research, zero evaluated stages. No tests,
provider/solver rerun or runtime/support/scientific-input edit accompanies Git.
Publication does not rewrite the1d9845db-plus-uncommitted launch provenance.
The executed Protocol file retains R25's descriptive version label; its only
difference from R25 is canary seed320149. Preserve that frozen file, all science
gates and original evidence unchanged; the R26 paths/seeds identify this run.

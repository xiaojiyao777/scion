# R15 Warehouse control r2: separate formal and development populations

State: completed at `2026-09-27T13:51:19.140280+00:00`, two evaluated stages,
no promotion. Launched once at `2026-09-27T13:44:28Z`, PID 288668. This is the configuration correction to the
[first startup](v04-r15-warehouse-feedback-control-20260927.md), which was
rejected before output/provider/solver creation. It preserves that record and
uses a fresh output/session, not a resumed campaign.

Runtime remains exactly the shared repair tested by 2471 passed / 1 skipped.
No implementation, source, public-test declaration, gate, resource limit,
seed, source choice or H/C guidance changes. Only the formal screening case
instance_development is replaced by the existing instance_small_6; the former
remains a public development fixture and cannot be a Protocol case.
No fixture is copied, renamed or regenerated to bypass that boundary.

[Protocol](inputs/v04-r15-warehouse-feedback-control-r2-protocol.yaml),
[split](inputs/v04-r15-warehouse-feedback-control-r2-split.yaml),
[seeds](inputs/v04-r15-warehouse-feedback-control-r2-seeds.yaml).
Initial deterministic selection: small_6 × one seed; expansion adds small_1
and uses two seeds. Two formal stages may instead be two different initial
candidates. Validation/frozen remain conditional and cannot execute within
two stages with required screening expansion. A valid negative is acceptable;
no claim of new Warehouse quality or retained improvement.
The stale calibration caveat and all limits in the first design remain.

Before r2, a separate in-process baseline-feasibility diagnostic checked the
unchanged complete solver with its existing registry on small_6 at
150001/150011, 2-second limits. Both are feasible with zero violations. It
produced no performance comparison, provider call or formal artifact.
This makes population selection explicitly outcome-informed engineering
control; the first small_2 failure remains unrepaired and preserved.
Control outcomes will not enter the CVRP research input.

Read-only preparation must include declared_development_suites,
declared_development_workspace_paths, declared_development_problem_package_paths,
and validate_development_closure_boundary with all formal/canary roots.
Focused input tests must preserve the first invalid input and ensure r2 is
disjoint. No full-suite rerun is needed for an input-only correction after the
frozen runtime passed. No concurrent tests/diagnostics during control or CVRP.

Output: `/home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-r2-20260927`.
Tmux: `scion-r15-warehouse-feedback-control-r2-20260927`.

Before launch the full public/formal closure, source, data, expansion, resource,
production/Verification setup and H projection checks passed. All five cases
parse; sandbox is available. Input regressions: 7 passed in 0.53 s, including
preserving first-input rejection and proving r2 disjointness. Ruff/diff pass.
No concurrent solver, test or maintenance job; output/session were absent.

## Invocation (executed once)

```bash
set -Eeuo pipefail
cd /home/clawd/research/or-autoresearch-agent
test ! -e /home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-r2-20260927
proxy_key_value=$(curl -fsS --connect-timeout 5 --max-time 15 http://127.0.0.1:8080/auth/status | jq -er '.proxy_api_key | select(type == "string" and length > 0)')
curl -fsS --connect-timeout 5 --max-time 15 -H "Authorization: Bearer $proxy_key_value" http://127.0.0.1:8080/v1/models | jq -e 'any(.data[]?; .id == "gpt-5.6-sol")' >/dev/null
exec env \
  PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
  PYTHONPATH=/home/clawd/research/or-autoresearch-agent/scion \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/surrogate \
  SCION_MODEL=gpt-5.6-sol SCION_REASONING_EFFORT=high \
  SCION_BASE_URL=http://127.0.0.1:8080 SCION_API_KEY="$proxy_key_value" \
  SCION_LLM_TIMEOUT_SEC=180 SCION_LLM_HYPOTHESIS_RESEARCH_TURN_TIMEOUT_SEC=180 \
  SCION_LLM_CODE_RESEARCH_TURN_TIMEOUT_SEC=300 SCION_LLM_CODE_RESEARCH_FINALIZE_TIMEOUT_SEC=300 \
  /home/clawd/miniconda3/envs/claw/bin/python -B -m scion.cli.main run \
    --problem /home/clawd/research/or-autoresearch-agent/scion/problems/warehouse_delivery/problem-v1.yaml \
    --source-tree /home/clawd/research/or-autoresearch-agent/surrogate \
    --code-research-limits /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-cvrp-r3i-long-run-code-research-limits.json \
    --protocol /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r15-warehouse-feedback-control-r2-protocol.yaml \
    --split /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r15-warehouse-feedback-control-r2-split.yaml \
    --seeds /home/clawd/research/or-autoresearch-agent/scion/docs/experiments/v0.4/inputs/v04-r15-warehouse-feedback-control-r2-seeds.yaml \
    --time-limit-sec 2 --rounds 2 --provider-call-cap 80 \
    --provider-transient-retries 2 --outer-hardwall-sec 7200 \
    --campaign-dir /home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-r2-20260927
```

## Result

Completed / requested_rounds_completed. [Status](/home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-r2-20260927/status.json)
and [summary](/home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-r2-20260927/campaign_summary.json)
establish completion independently of the dead tmux pane. 48 physical calls,
all successful at attempt index zero: H 17, C 30, finalizer one. No global
exhaustion or infrastructure failure. Three H/C attempts, two evaluated
candidates and one Code abandonment after public D3 failure. No held-out stage;
champion remains v1 / weight revision 0.

| Step | Actual candidate | Complete paired result | Recorded Decision |
|---|---|---|---|
| 1 | split-targeted DestroyRebuild | small_6 / 150001, 1/1 valid, tie, delta/CI 0 | continue_explore |
| 2 | MoveOrder draft | public development test failed; abandoned, no formal pair | no Decision |
| 3 | objective-directed MergeVehicles | small_6 / 150001, 1/1 valid, loss, delta/CI -300 | continue_explore |

Both formal stages passed Contract, Verification and canary, used 2-second
limits, had zero failed pairs and no protected subcategory-splits regression.
Both Protocol verdicts are SCREENING_FAIL_WIN_RATE; deterministic mapping to
CONTINUE_EXPLORE is unchanged. Metrics:
[step 1](/home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-r2-20260927/metrics/59ce27d9-297b-478a-9a64-bb8ccd304a42.json),
[step 3](/home/clawd/research/scion-experiments/v04-r15-warehouse-feedback-control-r2-20260927/metrics/86b9cacc-10ae-4374-a92c-7f12f8fa76dd.json).
These are two initial screens; small_1 and seed 150011 were not formally
executed. This is a valid negative engineering control, not quality evidence.

Independent source audit: all 31 visible C source values equal their actual
champion base. The two complete 406-file non-cache candidates differ only by
their respective implemented operator and registry serialization (typed
registry values equal baseline). Their ready content exactly equals the
evaluated file. Source directories are candidate-9v4czmnv and
candidate-x775elx5 under candidate_workspaces. The rejected MoveOrder never
entered a source head. Real D1/D1b/D2/D3/D4 checks and immediate ready export
worked; repair guidance is present in every applicable real provider request.

Remaining research limitations: H2/H3 prose incorrectly calls sibling
DestroyRebuild work inherited, although history labels it sibling and their
actual read/current source is unchanged champion. This is model reasoning,
not source contamination; prompt guidance is not a guarantee of compliance.
Repeated requests for nonvisible frozen support files and empty-path searches
also consume local turns. No gate is added to force history reading or style.
The two evaluated candidates are different branches; this control does not
prove same-branch deepening or trigger a real unsafe-import preflight event.
Those boundaries have separate focused/full regression and exact-R14 static
diagnostic evidence. No framework blocker was found for fresh CVRP R15.

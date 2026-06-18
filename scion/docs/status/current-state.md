# Scion v0.4 Current State

Last updated: 2026-06-18

This is the short operational resume point. It is not an append-only run log.
Detailed evidence belongs in `scion/docs/experiments/v0.4/`; curated milestone
history belongs in `scion/docs/status/v0.4-history.md`.

## Operating Frame

- Active branch: `codex/v04-evidence-repair-plan`.
- Governing design: `scion/design/scion-architecture-v3.md`.
- v0.4 closeout goal: make Scion stable enough that warehouse can recover
  continuous useful research and CVRP/VRP can produce evidence-backed solver
  hypotheses before v0.5 broad experiment matrices.
- Current repair posture: do not add broad budgets, truncation, compression, or
  generic gate tightening. Keep CVRP/warehouse semantics in problem-owned
  layers and keep generic `DecisionFeatures` problem-neutral.

## Current Conclusions

Warehouse:

- Warehouse recovery checkpoint is accepted. The short validation-transfer
  acceptance-contract WSL gate from commit `ce5d884` completed validly, reached
  screening/validation/frozen holdout, and promoted champion `v2`.
- This restores a useful warehouse research path, but it is not yet a long-run
  continuous-promotion proof.
- Remaining caveat: split-preserving cost-compression effects still need cleaner
  measurement interpretation, because diagnostics can over-read zero
  `split_delta_sum` even when the declared useful effect is cost compression.

CVRP/VRP:

- Framework plumbing for copied-campaign continuation has now been repaired
  through current champion, active branch, branch workspace, active hypothesis,
  and candidate patch restoration. The remaining CVRP issue is research
  targeting and solver mechanism quality, not basic inability to resume a
  branch.
- The older CVRP route-merge evidence remains negative as a solver result.
  Repeated
  `route_merge_repair` absorption/guarded variants either produced zero
  objective effect or mixed/regressive evidence. Scion can now continue and
  reject those branches with evidence.
- The provider-guidance pivot is now field-accepted. The `ff2e652` WSL
  target-intent/proposal check escaped route-merge and generated
  `demand_slack_regret_insertion` in `destroy_repair.py`, with complete formal
  screening and direct mechanism telemetry.
- The CVRP `demand_slack_regret_insertion` branch is now negative. A copied
  WSL continuation from commit `6e78a95` completed valid expanded screening
  with `48/48` valid pairs and `0` failures, then parked the lineage as
  `quality_regression`: pair W/L/T `16/28/4`, case W/L/T `3/6/3`, median
  delta `-3.75`, CI `[-7.0, 1.75]`. A/E gains survived only on selected cases;
  CMT4 remained negative, and the expanded set did not retest prior-negative
  CMT2.
- Branch-specific follow-up case targeting is now locally and WSL focused-test
  accepted. Expand-stage protocol selection retains prior branch evidence cases
  by exact id or unique basename, keeps those diagnostics out of
  `DecisionFeatures`, and records requested priority cases in raw metrics.
  Formal CVRP selection smoke confirms that CMT2 is restored to the expanded
  screening set without changing the configured case count.
- The CVRP problem-owned solver-design provider now carries the demand-slack
  negative lesson in both target-intent and hypothesis guidance. Live prompts
  no longer treat unchanged `demand_slack_regret_insertion` as an acceptable
  default continuation.
- The `28f3e5f` WSL demand-slack-pivot field check completed validly with
  `2/2` effective rounds. It is accepted as framework/research-loop evidence
  and rejected as solver-improvement evidence. Live prompts carried the
  demand-slack lesson, escaped unchanged demand-slack/route-merge twice, and
  generated material instrumented solver changes:
  `cross_route_2opt_reconnect` (`5/10/17` pair W/L/T, CMT2 negative) and
  `cluster_biased_worst_removal` (`8/16/8`, median delta `-0.5`, CMT2/CMT4 not
  fixed). Both candidates completed `32/32` valid screening pairs with `0`
  failures and were correctly abandoned on quality evidence.
- CVRP provider guidance now also carries this post-demand-slack pivot lesson:
  do not repeat unchanged `cross_route_2opt_reconnect` or unchanged
  `cluster_biased_worst_removal` by default; any revisit must explain a
  materially different causal path and CMT2/CMT4 protection, otherwise pivot to
  another problem-owned solver-design owner.
- The `acc21ba` WSL post-pivot guidance check completed validly with `1/1`
  effective round. It field-accepts the post-demand-slack pivot lesson: live
  target-intent/hypothesis prompts contained the new lesson and selected a new
  construction owner, `route_limit_seed_diversification`, instead of the
  rejected demand-slack/route-merge/cross-route/cluster-biased defaults. The
  candidate is rejected as solver evidence: `32/32` valid screening pairs,
  `0` failures, pair W/L/T `1/3/28`, median delta `0.0`, CMT2 negative
  (`1/3/0`, median `-4.5`), activation only in `4/32` candidate runs, and
  missing direct effect attribution.
- CVRP provider guidance now also carries the construction-pivot lesson:
  unchanged `route_limit_seed_diversification` should not be repeated by
  default; a construction revisit must explain broader formal-surface
  activation or direct objective-changing seed-selection effect with CMT2
  protection.
- Rejected default directions remain broad VNS removal, pure ALNS/no-polish,
  simple initial-VNS disablement, raw cadence-2, recent-best/stall gating,
  fixed early-8, tested share70 cap/rescue variants, unchanged route-merge
  absorption/guarded variants, unchanged demand-slack regret insertion,
  unchanged cross-route 2-opt reconnect, and unchanged cluster-biased worst
  removal, and unchanged route-limit seed diversification.
- CVRP now shows useful framework behavior for proposal guidance, material code
  generation, telemetry, complete formal screening, and evidence-backed
  rejection. It still has not closed v0.4 CVRP effective-research acceptance,
  because no current CVRP solver-design branch has produced continuous
  improvement or promotion.

## Active Work

- No LLM campaign is currently running.
- Latest WSL artifacts are synced back to the server under
  `/home/clawd/research/scion-experiments/`.
- Latest CVRP post-pivot guidance artifacts are synced back to:
  `/home/clawd/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z`.
- The next construction-pivot guidance check is temporarily blocked by LLM
  infrastructure, not by Scion code or prompt construction. A clean WSL rerun
  from `867f5de` reached prompt construction but produced `0` effective rounds
  because the WSL `127.0.0.1:8080` proxy returned `401` after its upstream
  OAuth session was invalidated. A server fallback through `https://aihubmix.com`
  also produced `0` effective rounds because the account returned
  `insufficient_user_quota`; the official OpenAI key also returned
  `insufficient_quota`. A clean `f462133` rerun proved the new launcher
  completion preflight and prompt construction path: the small `gpt-5.5`
  preflight returned non-empty output, and live target-intent/hypothesis prompts
  contained the construction-pivot lesson, but both real agentic proposal
  requests still failed with `403 insufficient_user_quota`.
- The CVRP launcher has been repaired for this resume path: non-local keys can
  now be supplied with `--api-key-env` so secrets are not written to
  `launch.env`, `launch.env` is `0600`, and `--completion-preflight` performs
  a real chat-completion readiness check before campaign startup.
- WSL campaign launches must set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion`. Without
  it, Python may import stale Scion core modules from
  `/home/xjy-ubuntu/projects/scion/scion` while reading problem files from the
  synchronized repo.

## Next Actions

1. Restore a live `gpt-5.5` route with enough balance/quota for Scion's full
   agentic proposal prompts before launching another campaign. For WSL,
   `/v1/chat/completions` must return HTTP `200` and non-empty text/tool
   output; `/v1/models` is not enough, and a tiny OK completion is only an auth
   preflight. Then rerun the next CVRP research slice from a clean synchronized
   commit using launcher `--completion-preflight` and, for non-local keys,
   `--api-key-env`. First inspect live target-intent/hypothesis traces for the
   construction-pivot lesson.
2. The next CVRP mechanism must not be unchanged demand-slack, unchanged
   route-merge absorption, unchanged `cross_route_2opt_reconnect`, unchanged
   `cluster_biased_worst_removal`, or unchanged
   `route_limit_seed_diversification`. It should choose a materially different
   problem-owned owner or explain a new causal path with CMT2/CMT4 protection.
3. Clean up status/projection polish separately: abandoned branch DB rows retain
   mechanism/evidence, but their history-card projection can still drop compact
   status fields; in-flight `run_status.json` also remains too coarse during
   long formal screening.
4. Keep a later warehouse repeat available to test whether champion `v2`
   enables continuous follow-on improvement.

## Key Evidence

- Core reset: `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`.
- Warehouse recovery:
  `scion/docs/experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md`.
- CVRP current negative route-merge frontier:
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-guarded-agentic-1r-f3d634c-postrun-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-transfer-agentic-resume1r-af5b5a2-postrun-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-routemerge-branchcard-transfer-agentic-2r-9193d4e-postrun-20260618.md`.
- CVRP provider pivot repair:
  `scion/docs/experiments/v0.4/v04-cvrp-route-merge-pivot-guidance-repair-20260618.md`.
- CVRP provider pivot field check:
  `scion/docs/experiments/v0.4/v04-cvrp-route-merge-pivot-guidance-agentic-1r-ff2e652-postrun-20260618.md`.
- Campaign reopen continuation repair:
  `scion/docs/experiments/v0.4/v04-campaign-reopen-active-branch-restore-repair-20260618.md`.
- CVRP demand-slack follow-up:
  `scion/docs/experiments/v0.4/v04-cvrp-demand-slack-followup-agentic-resume1r-6e78a95-postrun-20260618.md`.
- CVRP follow-up case targeting repair:
  `scion/docs/experiments/v0.4/v04-cvrp-followup-case-targeting-repair-20260618.md`.
- CVRP demand-slack provider guidance repair:
  `scion/docs/experiments/v0.4/v04-cvrp-demand-slack-provider-guidance-repair-20260618.md`.
- CVRP demand-slack pivot field check and postrun provider lesson:
  `scion/docs/experiments/v0.4/v04-cvrp-demand-slack-pivot-agentic-2r-28f3e5f-postrun-20260618.md`.
- CVRP post-pivot guidance field check and construction-pivot lesson:
  `scion/docs/experiments/v0.4/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-postrun-20260618.md`.
- Current CVRP construction-pivot infra failures:
  `scion/docs/experiments/v0.4/v04-cvrp-constructionpivot-guidance-infra-failures-867f5de-20260618.md`.
- CVRP launcher secret/preflight repair:
  `scion/docs/experiments/v0.4/v04-cvrp-launch-secret-completion-preflight-repair-20260618.md`.
- WSL reference docs:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `RSYNC_PATHS.md`.

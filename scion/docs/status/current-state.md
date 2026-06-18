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

- Warehouse has a valid v0.4 positive research-path checkpoint. The short WSL
  validation-transfer gate promoted champion `v2`, and the later
  split-preserving cost-compression telemetry repair keeps real cost/improving
  move effects visible without turning a zero split delta into a false
  effect-zero diagnosis.
- This is enough to treat warehouse as the simpler recovery surface for the
  next continuous-improvement check. It is not yet a long-run
  continuous-promotion proof.

CVRP/VRP:

- The core CVRP blocker is no longer basic campaign resumption. Copied
  campaigns restore champion, active branch, branch workspace, hypothesis,
  candidate patch, branch evidence, follow-up case targeting, and compact
  status/report projections.
- Live CVRP checks now show useful research-loop behavior: target-intent and
  hypothesis guidance can steer away from stale branches, generate material
  solver code, complete formal screening, preserve mechanism telemetry, and
  reject bad hypotheses with evidence.
- Current rejected/default-avoid directions are broad VNS removal, pure
  ALNS/no-polish, simple initial-VNS disablement, raw cadence-2,
  recent-best/stall gating, fixed early-8, tested share70 cap/rescue variants,
  unchanged route-merge absorption, unchanged demand-slack regret insertion,
  unchanged cross-route 2-opt reconnect, unchanged cluster-biased worst
  removal, and unchanged route-limit seed diversification.
- Construction seed/portfolio mechanisms now require direct effect attribution
  from a same-run candidate-vs-baseline seed comparison or same-mechanism
  accepted delta. Fallback activation, seed-pool size, or merely selecting a
  seed is only activation/design evidence.
- CVRP still has not closed v0.4 effective-research acceptance: the framework
  can steer, continue, measure, and reject, but no current CVRP solver-design
  branch has produced continuous improvement or promotion.

Framework observability:

- Status and summary artifacts now expose compact branch lifecycle/progress and
  reduced measurement readiness without leaking raw A/A evidence or
  `calibration_ref`.
- `report research-efficiency` now brings together reduced readiness,
  protocol-effect-vs-MDE summaries, research-shape diagnostics, and
  cross-branch observability counters. Older copied artifacts can recover
  readiness from compatible copied `problem-v1.yaml` plus A/A calibration
  files.
- These are observability/reporting repairs only. They do not change Decision,
  `DecisionFeatures`, Protocol, scheduling, gates, budgets, lifecycle policy,
  proposal context, or problem semantics.

## Active Work

- No LLM campaign is currently running.
- The next CVRP construction-pivot guidance check is blocked by LLM
  infrastructure, not by Scion prompt construction or campaign code. The local
  WSL proxy returned `401`; server fallbacks returned quota errors.
- The launcher resume path is repaired: use `--completion-preflight` before
  campaign startup, use `--api-key-env` for non-local keys, and keep generated
  `launch.env` secret-safe. CVRP and warehouse now both have prepare-only
  launch helpers for their next focused agentic checks and both write postrun
  acceptance reports by default after Scion exits. Both helpers can copy an
  existing campaign into the new run root so follow-ups resume from restored
  champion and branch evidence rather than manual copy steps.
- Latest WSL artifacts are synced back under
  `/home/clawd/research/scion-experiments/`; the latest accepted CVRP
  post-pivot artifacts are under
  `/home/clawd/research/scion-experiments/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-20260618T064210Z`.
- The next warehouse `v2` follow-up is prepared but not launched at
  `/home/xjy-ubuntu/research/scion-experiments/v04-warehouse-v2-followup-ready-6r-gpt55-20260618T093411Z-claw`
  and synced locally under `/home/clawd/research/scion-experiments/`. It has
  completion preflight and default postrun report generation enabled; do not
  run it until the `gpt-5.5` chat-completion route returns HTTP `200`.
- WSL campaign launches must set
  `PYTHONPATH=/home/xjy-ubuntu/research/or-autoresearch-agent/scion` to avoid
  stale Scion core imports from `/home/xjy-ubuntu/projects/scion/scion`.

## Next Actions

1. Restore a live `gpt-5.5` route with enough balance/quota for Scion's full
   agentic proposal prompts before launching another campaign. For WSL,
   `/v1/chat/completions` must return HTTP `200` and non-empty text/tool
   output; `/v1/models` is not enough, and a tiny OK completion is only an auth
   preflight. Then rerun the next CVRP research slice from a clean synchronized
   commit using launcher `--completion-preflight` and, for non-local keys,
   `--api-key-env`; use `--resume-from-campaign` when continuing a live branch.
   Keep the default postrun report bundle enabled, then first inspect live
   target-intent/hypothesis traces for the construction-pivot lesson.
2. The next CVRP mechanism must not be unchanged demand-slack, unchanged
   route-merge absorption, unchanged `cross_route_2opt_reconnect`, unchanged
   `cluster_biased_worst_removal`, or unchanged
   `route_limit_seed_diversification`. It should choose a materially different
   problem-owned owner or explain a new causal path with CMT2/CMT4 protection.
   If it revisits construction, direct seed effect must come from a same-run
   seed baseline or same-mechanism accepted delta, not fallback activation.
3. Keep a later warehouse repeat available to test whether champion `v2`
   enables continuous follow-on improvement. Use the warehouse launcher to
   copy the accepted `v2` campaign, prepare rebased production configs, and run
   completion preflight before launch. Keep the default postrun report bundle
   enabled unless the run is only a shell/config smoke.

## Key Evidence

- Core reset and design authority:
  `scion/reports/v04-core-framework-review-20260611.md`,
  `scion/reports/v04-core-framework-code-review-20260611.md`,
  `scion/design/v0.5-evidence-uplift-roadmap.md`, and
  `scion/design/scion-architecture-v3.md`.
- Curated milestone index:
  `scion/docs/status/v0.4-history.md`.
- Warehouse recovery and telemetry:
  `scion/docs/experiments/v0.4/v04-warehouse-validation-transfer-contract-rerun6r-postrun-20260617.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-cost-compression-telemetry-interpretation-repair-20260618.md`.
- CVRP live research-loop frontier:
  `scion/docs/experiments/v0.4/v04-cvrp-demand-slack-pivot-agentic-2r-28f3e5f-postrun-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-postpivot-guidance-agentic-1r-acc21ba-postrun-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-construction-effect-guidance-repair-20260618.md`.
- Continuation, readiness, and reporting repairs:
  `scion/docs/experiments/v0.4/v04-campaign-reopen-active-branch-restore-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-followup-case-targeting-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-branch-history-status-projection-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-run-status-branch-progress-projection-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-measurement-readiness-status-projection-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-research-efficiency-observability-projection-repair-20260618.md`.
- Current LLM/launcher blocker:
  `scion/docs/experiments/v0.4/v04-cvrp-constructionpivot-guidance-infra-failures-867f5de-20260618.md`,
  `scion/docs/experiments/v0.4/v04-cvrp-launch-secret-completion-preflight-repair-20260618.md`,
  `scion/docs/experiments/v0.4/v04-warehouse-launcher-preflight-repair-20260618.md`.
- WSL reference docs:
  `/home/clawd/research/scion-experiments/v04-cvrp-phaseB-wsl-handoff-20260614T095900Z/WSL_EXECUTION.md`
  and `RSYNC_PATHS.md`.

# Scion Documentation Index

*Last updated: 2026-05-04*

This directory is the active documentation surface for Scion. Historical sprint notes, validation drafts, and intermediate analysis are archived under `archive/`.

## Read First

- [v0.3-current-state.md](v0.3-current-state.md) - current v0.3 status and formal experiment location.
- [evidence-manifest.md](evidence-manifest.md) - active map from claims to experiment artifacts, including superseded outputs.
- [v0.3-final-visual-report.md](v0.3-final-visual-report.md) - visual summary of final v0.3 results.
- [v0.3-final-12campaign-analysis.md](v0.3-final-12campaign-analysis.md) - formal 12-campaign internal framework/search analysis.
- [v0.3-production-timeout-fix-analysis.md](v0.3-production-timeout-fix-analysis.md) - production-only rerun after incomplete-evidence/runtime fixes.
- [v0.3-final-validation-checklist.md](v0.3-final-validation-checklist.md) - final engineering and experiment gates.
- [v0.4-current-state.md](v0.4-current-state.md) - current v0.4 implementation status, validation result, and active Sonnet campaign paths.
- [v0.4-design.md](v0.4-design.md) - v0.4 design baseline: performance-aware Scion, CVRP generalization, and campaign framework cleanup.
- [v0.4-phase1-task-manifest.md](v0.4-phase1-task-manifest.md) - Phase 1 extraction task manifest and subagent development model.
- [v0.4-phase1-worklog.md](v0.4-phase1-worklog.md) - Phase 1 execution notes, baseline test status, and worker dispatch log.
- [v0.4-phase1-closeout.md](v0.4-phase1-closeout.md) - Phase 1 extraction closeout, test results, and remaining campaign responsibilities.
- [v0.4-phase2-task-manifest.md](v0.4-phase2-task-manifest.md) - Phase 2 framework hardening manifest: adapter-native V5 and runtime evidence.
- [v0.4-phase2-worklog.md](v0.4-phase2-worklog.md) - Phase 2 execution notes for runtime verification/evidence/context hardening.
- [v0.4-phase2-closeout.md](v0.4-phase2-closeout.md) - Phase 2 closeout: adapter-native runtime verification, CVRP smoke, and ProblemSpecV1 bridge.
- [v0.4-phase3-design.md](v0.4-phase3-design.md) - Phase 3 design: final quality evidence harness and CVRP benchmark reporting.
- [v0.4-phase3-task-manifest.md](v0.4-phase3-task-manifest.md) - Phase 3 task manifest and first worker slice.
- [v0.4-phase3-worklog.md](v0.4-phase3-worklog.md) - Phase 3 execution notes for final quality package writer and validation.
- [v0.4-phase3-closeout.md](v0.4-phase3-closeout.md) - Phase 3 closeout: final evidence infrastructure and Phase 4 readiness.
- [v0.4-phase4-design.md](v0.4-phase4-design.md) - Phase 4 design: controlled CVRP campaign readiness and first run path.
- [v0.4-phase4-task-manifest.md](v0.4-phase4-task-manifest.md) - Phase 4 task manifest starting with CVRPLIB input support.
- [v0.4-phase4-worklog.md](v0.4-phase4-worklog.md) - Phase 4 execution notes for CVRPLIB input/runtime readiness.
- [v0.4-phase4-closeout.md](v0.4-phase4-closeout.md) - Phase 4 closeout: controlled CVRP promotion path and final evidence refs.
- [v0.4-p4-05-matrix-readiness.md](v0.4-p4-05-matrix-readiness.md) - P4-05 formal CVRP matrix readiness assets, commands, and residual risks.
- [v0.4-p0-promotion-integrity-design.md](v0.4-p0-promotion-integrity-design.md) - P0-C promotion commit, registry, and weight-opt integrity policy.
- [v0.4-p0-campaign-controller-decomposition-design.md](v0.4-p0-campaign-controller-decomposition-design.md) - P0-D campaign controller decomposition plan aligned with v3.
- [v0.4-p1-runtime-aware-optimization-design.md](v0.4-p1-runtime-aware-optimization-design.md) - P1 runtime-aware optimization design: efficiency as default Scion promotion governance.
- [v0.4-performance-aware-plan.md](v0.4-performance-aware-plan.md) - performance-aware optimization plan from production timeout findings.
- [v0.4-cvrp-plan.md](v0.4-cvrp-plan.md) - CVRP second-problem plan for v0.4 generalization.
- [v0.4-evidence-harness.md](v0.4-evidence-harness.md) - common promotion/final-quality/runtime evidence schema for v0.4.
- [v0.3-code-audit-dataflow.md](v0.3-code-audit-dataflow.md) - current code logic and dataflow audit.
- [../design/scion-architecture-v3.md](../design/scion-architecture-v3.md) - project architecture blueprint.
- [../design/scion-v0.3-design.md](../design/scion-v0.3-design.md) - v0.3 design.
- [../reviews/v0.3-design-detail-plan.md](../reviews/v0.3-design-detail-plan.md) - v0.3 detailed implementation/review plan.
- [../reviews/v0.3-design-review-report.md](../reviews/v0.3-design-review-report.md) - v0.3 design review findings.

## Active Reference

- [experiment-quickref.md](experiment-quickref.md) - campaign and experiment operations.
- [experiment-baseline-management.md](experiment-baseline-management.md) - git tag and baseline management.
- [metrics-guide.md](metrics-guide.md) - metric definitions and gate interpretation.
- [milp-model.md](milp-model.md) - warehouse-delivery MILP model reference.
- [milp-usage-strategy.md](milp-usage-strategy.md) - MILP as report-only comparison source.
- [glossary.md](glossary.md) - project terms.
- [v0.2-final-state.md](v0.2-final-state.md) - v0.2 code archaeology used by v0.3.
- [v1.0-roadmap.md](v1.0-roadmap.md) - post-v0.4 roadmap for warehouse + CVRP evidence and framework hardening.

## Historical Documents

### `archive/v0.3/`

v0.3 development history and experiment analysis:

- W16 experiment records: `w16-results.md`, `w16-campaign-log.md`, `sprint-w16-optimization.md`
- F1/F2 analysis: `v0.3-f1-analysis-and-a1-reflection.md`, `v0.3-f2-analysis.md`
- Closure validation analysis and preregistration:
  - `v0.3-closure-validation-20260425-analysis.md`
  - `v0.3-closure-validation-20260425-deep-analysis.md`
  - `v0.3-closure-validation-20260425-deep-analysis.zh.md`
  - `v0.3-closure-validation-prereg.md`
  - `v0.3-production-closure-validation-prereg.md`
- Two-model validation: `v0.3-two-model-validation-analysis.md`
- Historical state snapshots: `v0.3-current-state.md.pre-*`
- Earlier plans and assessments:
  - `v0.3-implementation-plan.md`
  - `v0.3-optimization-design.md`
  - `v0.3-engineering-assessment.md`

### `../design/archive/`

Historical architecture/design documents for v0.1 and v0.2.

### `../reviews/archive/`

Historical review reports and remediation plans, mainly from v0.2.

## Directory Shape

```text
scion/
├── docs/
│   ├── README.md
│   ├── evidence-manifest.md
│   ├── v0.3-current-state.md
│   ├── v0.3-final-visual-report.md
│   ├── v0.3-final-12campaign-analysis.md
│   ├── v0.3-production-timeout-fix-analysis.md
│   ├── v0.3-final-validation-checklist.md
│   ├── v0.4-current-state.md
│   ├── v0.4-design.md
│   ├── v0.4-phase1-task-manifest.md
│   ├── v0.4-phase1-worklog.md
│   ├── v0.4-phase1-closeout.md
│   ├── v0.4-phase2-task-manifest.md
│   ├── v0.4-phase2-worklog.md
│   ├── v0.4-phase2-closeout.md
│   ├── v0.4-phase3-design.md
│   ├── v0.4-phase3-task-manifest.md
│   ├── v0.4-phase3-worklog.md
│   ├── v0.4-phase3-closeout.md
│   ├── v0.4-phase4-design.md
│   ├── v0.4-phase4-task-manifest.md
│   ├── v0.4-phase4-worklog.md
│   ├── v0.4-phase4-closeout.md
│   ├── v0.4-p4-05-matrix-readiness.md
│   ├── v0.4-p0-promotion-integrity-design.md
│   ├── v0.4-p0-campaign-controller-decomposition-design.md
│   ├── v0.4-p1-runtime-aware-optimization-design.md
│   ├── v0.4-performance-aware-plan.md
│   ├── v0.4-cvrp-plan.md
│   ├── v0.4-evidence-harness.md
│   ├── v0.3-code-audit-dataflow.md
│   ├── experiment-quickref.md
│   ├── metrics-guide.md
│   ├── milp-model.md
│   ├── milp-usage-strategy.md
│   ├── v1.0-roadmap.md
│   └── archive/
│       └── v0.3/
├── design/
│   ├── scion-architecture-v3.md
│   ├── scion-v0.3-design.md
│   └── archive/
└── reviews/
    ├── v0.3-design-detail-plan.md
    ├── v0.3-design-review-report.md
    └── archive/
```

Maintenance rule: keep the active docs directory small. Move sprint logs, pre-registration drafts, interim experiment analysis, and superseded state snapshots into the matching `archive/vX.Y/` directory once they are no longer the current operating source.

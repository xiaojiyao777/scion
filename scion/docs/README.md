# Scion Documentation Index

*Last updated: 2026-04-26*

This directory is the active documentation surface for Scion. Historical sprint notes, validation drafts, and intermediate analysis are archived under `archive/`.

## Read First

- [v0.3-current-state.md](v0.3-current-state.md) - current v0.3 status and formal experiment location.
- [v0.3-final-12campaign-analysis.md](v0.3-final-12campaign-analysis.md) - formal 12-campaign internal framework/search analysis.
- [v0.3-final-validation-checklist.md](v0.3-final-validation-checklist.md) - final engineering and experiment gates.
- [v0.4-performance-aware-plan.md](v0.4-performance-aware-plan.md) - performance-aware optimization plan from production timeout findings.
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
- [v1.0-roadmap.md](v1.0-roadmap.md) - next-version planning input.

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
│   ├── v0.3-current-state.md
│   ├── v0.3-final-12campaign-analysis.md
│   ├── v0.3-final-validation-checklist.md
│   ├── v0.4-performance-aware-plan.md
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

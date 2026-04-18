# Scion Documentation Index

*Last updated: 2026-04-18*

本目录是 Scion 项目的活跃文档区。历史版本归档在 `archive/` 下。

---

## 活跃文档（当前版本 v0.2 → v0.3 过渡期）

### 权威设计
- **[design/scion-architecture-v3.md](../design/scion-architecture-v3.md)** — 基石架构，不随版本变化
- **[design/scion-v0.3-draft.md](../design/scion-v0.3-draft.md)** — v0.3 设计草案（开发中）

### 当前状态
- **[v0.2-final-state.md](v0.2-final-state.md)** — v0.2 完成态代码考古（技术债 D01-D17，v0.3 开发参考）

### 常驻参考（不随版本归档）
- **[milp-model.md](milp-model.md)** — 仓配协同 MILP 数学模型
- **[metrics-guide.md](metrics-guide.md)** — win_rate / median_delta / splits 等指标说明
- **[glossary.md](glossary.md)** — 项目术语表
- **[experiment-quickref.md](experiment-quickref.md)** — 实验操作速查
- **[experiment-baseline-management.md](experiment-baseline-management.md)** — 实验基线 tag 管理
- **[figures/](figures/)** — 实验图表（含 sprint-f6/ 历史图）

---

## 归档文档

### `archive/v0.1/`
v0.1 MVP 时期的报告与调优记录。v0.2 之后不再更新。

- `v0.1-completion-report.md`、`v0.1-tuning-report.md`、`v0.1.1-changelog.md`

### `archive/v0.2/`
v0.2 开发全周期（Sprint A→M）的设计、实验、审查产物。

- **完工报告**：`v0.2-completion-report.md`
- **开发日志**：`v0.2-mvp-development-log.md`、`v02-uuid-fix-validation-report.md`
- **Sprint 记录**：`sprint-g-summary.md`、`sprint-h-plan.md`、`sprint-j-plan.md` 等
- **实验分析**：`sprint-f2/f3/f4/f6-*.md`、`sprint-f-failure-analysis.md`、`sprint-j-v3-analysis.md`
- **Prompt 工程**：`cc-prompt-engineering-analysis.md`、`prompt-improvement-plan.md`、`operator-quality-analysis.md`
- **Campaign 产物**：`campaign_summary.json`、`v3_campaign.log`
- **系统性理解文档**：`understanding/` 整组 freeze（v0.3 做完再逐个更新）

### `../design/archive/v0.1/`
- v0.1 MVP 设计：`scion-v0.1-design.md`、`scion-engineering-arch-v1.md`

### `../design/archive/v0.2/`
- v0.2 完整设计系列（13 份文档）：`scion-v0.2-*.md`、`sprint-ef-plan.md`、`sprint-f-design.md`、`cc-design-reference*.md`、`case-level-feedback-v1.md`、`v0.2-remediation-plan.md`

### `../reviews/archive/`
- v0.2 时期的 GPT-5.4-Pro 架构审查：`scion-v02-review_result.md`、`SprintF前整改任务单.md`、`phase*-review.md`、`context-manager-gap-analysis.md` 等

---

## 活跃路径速查

```
scion/
├── README.md                          # 项目入口
├── docs/
│   ├── README.md                      # 本索引
│   ├── v0.2-final-state.md            # v0.2 代码考古（v0.3 参考）
│   ├── milp-model.md                  # MILP 模型
│   ├── metrics-guide.md               # 指标说明
│   ├── glossary.md                    # 术语表
│   ├── experiment-quickref.md         # 实验操作
│   ├── experiment-baseline-management.md
│   ├── figures/                       # 图表
│   └── archive/                       # v0.1/v0.2 归档
├── design/
│   ├── scion-architecture-v3.md       # 基石架构
│   ├── scion-v0.3-draft.md            # v0.3 设计（开发中）
│   └── archive/                       # v0.1/v0.2 归档
├── reviews/
│   ├── sprint-review.py               # review 工具
│   └── archive/                       # v0.2 审查归档
└── postmortem/                        # 事故复盘（不归档）
```

---

*维护规则：版本发布完成后，该版本的 sprint/plan/analysis/review 类文档整组 `git mv` 到 `archive/vX.Y/`，保留活跃区只有基石架构、下一版本设计、常驻参考、当前版本状态快照。*

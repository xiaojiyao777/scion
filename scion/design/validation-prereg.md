# Scion v0.3 Validation Pre-Registration

**冻结日期**: 2026-04-21
**状态**: Frozen — 实验开始前不可修改

---

## 1. 实验目标

验证 Scion v0.3 系统在 warehouse delivery 问题上的端到端搜索能力，量化不同模型和数据变体的表现差异。

## 2. Research Questions

### W16: Full-System Validation

| RQ | 问题 | 度量 | 成功标准 |
|----|------|------|---------|
| RQ1 | Scion 搜索能否持续改进 champion？ | champion 版本数、promotion 总数 | ≥ 1 次 promotion 且 final champion 优于 initial |
| RQ2 | 模型差异对搜索效率的影响？ | per-model promote rate, abandon rate, rounds to first promote | 三个模型之间存在可观测差异 |
| RQ3 | Synthetic vs production 泛化性？ | 同 model 在两种 variant 上的 screening win_rate 分布 | 记录差异幅度，不预设方向 |
| RQ4 | Champion 距离 MILP 最优解的 gap？ | `optimality_gap = (champion - milp_exact) / milp_exact` | 报告 exact 实例的 gap 分布 |
| RQ5 | Early-stop 在哪些条件下触发？ | 实际终止 round vs 100 round 上限 | 记录触发规则和节省比例 |

### W17: Mechanism Study（如执行）

| Layer | 问题 | 方法 | 度量 |
|-------|------|------|------|
| A | Structure search 单独贡献 | weight-opt OFF vs full | champion delta 差异 |
| B | Parameter search 单独贡献 | offline snapshot 分析 | weight 变化幅度 vs objective delta |
| C | Early-stop 因果增益 | replay: on/off paired | 终止 round 差异 |
| D | Classifier 效用 | classifier on vs keyword-only | family 分类准确度、搜索效率差异 |

**W17 范围声明**: W17 是 lightweight mechanism study，样本量有限（1 model × 2 variants × 3 seeds），结论为初步性质，不等同于全面 ablation。

## 3. 实验矩阵

### W16 Configuration

| 维度 | 值 |
|------|----|
| Models | `claude-sonnet-4-6`, `claude-opus-4-6`, `gpt-5.4` |
| Variants | `warehouse_synthetic` (split_manifest.yaml), `warehouse_prod` (split_manifest_prod.yaml v1.1) |
| Campaign seeds | `[11, 29, 47]` |
| Round limit | 100（early-stop enabled） |
| Total campaigns | 3 × 2 × 3 = 18 |

### Instance Coverage

| Split | Synthetic | Production |
|-------|-----------|------------|
| Canary | 3 | 2 |
| Screening | 17 | 17 |
| Validation | 10 | 5 |
| Frozen | 18 | 8 |

Production manifest 已剔除 4 个不可行实例（locked vehicle capacity bug）。

### MILP Bounds

- 78 个实例有 MILP bounds（73 exact + 4 feasible + 1 新增）
- 5 个不可行实例无 bounds
- Gap 分析仅对 `milp_exact = True` 的实例进行

## 4. 协议参数

### Evaluation Protocol

| Stage | Cases | Seeds | Gate |
|-------|-------|-------|------|
| Screening | modify=6, create=10 | [42, 137] | win_rate ≥ 0.60 |
| Validation | 6 | [7, 19, 83] | win_rate ≥ 0.66 + bootstrap_ci_low ≥ 0 |
| Frozen | 4 | [256, 512, 1024] | bootstrap_ci_low ≥ 0 + canary_passed |

### Solver

| 参数 | 值 |
|------|----|
| time_limit_sec | 300 |
| max_iter | 200 |
| algorithm | VNS (multi-operator) |

## 5. 分析计划

### 5.1 Per-Campaign Metrics

每个 campaign 结束时提取：
- `n_rounds_actual`: 实际运行轮数
- `n_promotions`: champion 升级次数
- `final_champion_version`: 最终 champion 版本
- `early_stop_triggered`: 是否触发 early-stop
- `early_stop_rule`: 触发的规则
- `screening_win_rate_dist`: 各 round 的 screening win_rate
- `token_usage_total`: 总 token 消耗

### 5.2 Cross-Campaign Aggregation

- **Model comparison**: per-model 的 promotion rate, median rounds to first promote, final champion gap
- **Variant comparison**: synthetic vs production 的 win_rate 分布、abandon 率
- **Seed stability**: 同 (model, variant) 不同 seed 的结果方差

### 5.3 Gap Analysis

对每个 exact-solved 实例：
```
gap_f1 = champion_f1 - milp_f1  (理想为 0)
gap_f2_pct = (champion_f2 - milp_f2) / milp_f2 × 100
```

报告：gap 中位数、四分位距、最大 gap 实例。

### 5.4 统计方法

- Bootstrap confidence interval: n=10000, 95% CI
- Case-level aggregation: 每个 case 的 delta 跨 seed 取中位数
- 不使用 p-value 或 NHST；以 effect size + CI 为主

## 6. W16 不能回答的问题

明确声明以下问题需要 W17 或后续工作：
- Structure search 单独贡献（需要 weight-opt OFF ablation）
- Parameter search 单独贡献（需要 offline analysis）
- Structure + parameter 协同效应
- Early-stop 因果增益（需要 paired on/off comparison）
- 不同 operator 的相对贡献

## 7. 数据与代码完整性

- 所有实验结果存储在 `~/research/scion-experiments/v03-validation/`
- Campaign summary JSON + SQLite lineage database 保存完整历史
- MILP bounds 来自 `surrogate/milp_bounds/`，78 个文件已验证
- 代码分支: `v0.3-dev`，实验前打 tag `v0.3-Q1-prereg`

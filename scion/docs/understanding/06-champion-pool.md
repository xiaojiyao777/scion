# 06 — Champion Pool 与权重优化

## Champion 的定义

**Champion 是池级别，不是算子级别。**

Champion 不是"某个算子赢了"，而是**整个算子集合（pool）的一个配置**赢了。

```python
ChampionState:
  version: int                           # 版本号
  operator_pool: dict[str, OperatorConfig]  # 算子名 → {file, weight}
  code_snapshot_path: str               # 文件系统快照路径
  code_snapshot_hash: str               # 内容哈希，用于 Stale 检测
  promoted_at: str
```

---

## A/B 评估结构

每次实验是：

```
Champion Solver:   pool = {现有算子集合，权重 w1...wN}
Candidate Solver:  pool = {现有算子集合 ± 变更，权重同}

相同实例 × 相同 seed → 配对比较结果（win / loss / tie）
```

**字典序比较规则（多目标）：**
```
Level 1: 业务聚合约束（splits 数）← 最高优先级
Level 2: 成本（cost）
Level 3: 运行效率
```

先比 Level 1，若相当（在容忍度内）才比 Level 2，以此类推。

---

## Promote 的含义

Promote 一个候选 = 把"新的 pool 配置"提升为 champion。

假设原 champion pool 有算子 {A, B, C}，候选是"新增算子 D"：
- Promote 后：champion = {A, B, C, D}
- 下一次实验的 champion baseline 是 {A, B, C, D}

---

## 权重优化（Weight Optimization）

**时机**：每次 promote 成功后立即运行。

**目标**：找到让新 champion pool 性能最优的算子权重分配。

**当前实现**：pure-Python UCB fallback（scipy/skopt 未安装）
- 评估次数：n_initial_random(4) + n_iterations(4) = 8 次
- 每次评估：8个screening实例 × 2 seeds = 16次 solver 调用
- 总计：~128 次 solver 调用，约 10-20 分钟

**权重的作用**：VNS 在每次迭代时按概率选算子。权重高的算子被选中概率高。优化后的权重让 champion pool 发挥最优综合效果。

---

## 已知问题：同步阻塞

**当前问题**：weight optimization 在 `_on_promote()` 内同步运行，每次 promote 阻塞 campaign 10-40 分钟（取决于参数和 solver 速度）。

**影响**：campaign 探索效率低，每次 promote 后长时间停顿。

**v0.3 计划**：改为异步，但需要配合 STALE 机制——详见 [08-known-issues-roadmap.md](08-known-issues-roadmap.md)。

**Sprint F 临时缓解**：`n_initial_random=4, n_iterations=4`（从原来 8+8=16 次评估降到 4+4=8 次）。

---

## Oracle：评估的信任锚点

**Oracle** 是验证算子输出"业务正确性"的代码，用于 Verification Gate 的 feasibility check 和 objective recomputation。

Oracle 的特殊性：
- **由人写 spec，由 Opus 写实现，由人审核**
- **冻结为 frozen files，不可被搜索过程修改**
- 这是整个系统的信任锚点——如果 oracle 有 bug，所有实验结论都不可信

这也是为什么说"人在回路但不在循环里"：人不参与每轮迭代，但人定义了 oracle（即"什么叫正确"）。

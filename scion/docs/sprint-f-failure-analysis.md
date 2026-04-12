# Sprint F 失败根因分析与修复记录

*日期: 2026-04-12 晚 → 2026-04-13 凌晨*
*分析者: Cris + BigBOSS*
*状态: 全部修复完成，Sprint F2 已启动验证*

---

## 0. 背景

Sprint F（第一轮端到端验证实验）三组结果：

| 实验 | 模型 | 轮次 | Promotes | V8 失败 | V5 失败 |
|---|---|---|---|---|---|
| F1 | Opus 30r | 30 | **2** | 少量 | 0 |
| F2 | Opus 50r | 12有效 | **1** | **13** | 0 |
| F3 | Sonnet 30r | 3有效 | **0** | 5 | **16** |

F2/F3 的异常失败率引发了深度追踪。

---

## 1. V8_nondeterminism 根因分析

### 1.1 现象

F2 中 13 轮 V8 失败（26%）。同一份代码、同一个 seed、跑两次 solver，产出不同的 objective。

失败是**概率性的**——同一组算子有时 PASS 有时 FAIL，不是 100% 复现。

### 1.2 排查过程

**第一步：确认基线是否确定性**

```bash
# 纯基线 6 个算子，10 次运行
V8 results: 10/10 PASS
```

基线完全确定。问题由 LLM 算子引入。

**第二步：逐算子隔离**

对 round_9_ archive（包含 subcategory_aware_swap / subcategory_merge / subcategory_redistribute）：

```
+subcategory_aware_swap.py:    [FAIL, FAIL, PASS]
+subcategory_merge.py:         [FAIL, FAIL, PASS]
+subcategory_redistribute.py:  [FAIL, PASS, PASS]
+ALL THREE:                    [FAIL, FAIL, FAIL]
```

三个算子各自都能触发，且是**概率性**失败——这排除了"某个算子里有固定的非确定性代码"。

**第三步：排除代码层面原因**

检查了这些算子：
- 无 `uuid`、无 `random`、无 `time`（ContractGate C9b 已拦）
- 有 `set()` 但只用于 `len()` 判断
- `sorted()` 调用保证稳定顺序
- `PYTHONHASHSEED=0` 已固定

静态分析找不到非确定性来源。

**第四步：trace logging 追踪**

给 `vns.py` 加 trace logging，记录每次 operator 调用前后的 `rng.getstate()`：

```python
# 关键发现：iteration 2, sol[11], op=DestroyRebuild
run1: rng_before=[3039594328, ...] → rng_after=[1521510369, ...]  # rng 被消耗
run2: rng_before=[3039594328, ...] → rng_after=[3039594328, ...]  # rng 未消耗！
```

两次进入同一个算子时 rng_before 完全相同，但 rng_after 不同——说明算子内部走了不同的执行路径，根源在于**传入的 `sol`（pool 解 #11）不同**。

**第五步：定位到 pool**

继续追踪 iteration 0：所有 40 个 op 的 rng before/after 完全一致，但 `new_solutions` 的 assignment **hash 不同**：

```
new_sol[0] objective: [8, 38600, 0]  (相同)
new_sol[0] assignment hash: 23fb9946 vs fe158b3d  (不同！)
```

objective 相同但内部结构不同，说明**初始解**就已经不同了。

**第六步：定位到 greedy_init**

```python
# surrogate/greedy_init.py 第 108 行
current_vid = f"V_{uuid.uuid4().hex[:8]}"  # ← 罪魁祸首
```

**cascade 路径**：

```
greedy_init uuid → vehicle ID 不同
→ 初始解内部结构不同（objective 相同但 assignment 不同）
→ pool.update() stable sort 保留不同解
→ iteration 1 遍历不同的 pool
→ 算子走不同分支 → rng 消耗量不同
→ 所有后续 rng.choice/rng.shuffle 全部偏移
→ 两次 run 产出不同 objective → V8 FAIL
```

### 1.3 为什么之前没发现

- uuid 修复（postmortem #001）只修了 `operators/base.py` 里的算子代码
- `greedy_init.py` 不是算子，不经过 ContractGate 检查，被遗漏
- 验证实验（4 轮）pool 里解数量少，tie 概率低，没有触发
- Sprint F 跑 50 轮，pool 更拥挤，触发概率显著升高

### 1.4 修复（Sprint H1）

```python
# 修复前（greedy_init.py）
import uuid
current_vid = f"V_{uuid.uuid4().hex[:8]}"

# 修复后
from operators.base import generate_vehicle_id
def greedy_init(instance: Instance, rng: Random) -> Solution:
    ...
    current_vid = generate_vehicle_id(rng)
```

- `solver.py` 的 `solve()` 传入同一个 `rng`（seed 固定），greedy_init 消耗确定数量的 rng 状态
- 移除 `import uuid`

**验证结果**：

```
修复前 (round_9_ archive): ~3/10 PASS
修复后 (round_9_ archive): 10/10 PASS
```

---

## 2. V5_state_mutation 根因分析

### 2.1 现象

F3（Sonnet）从 round 9 开始 V5 连续失败 16 轮，V5 detail 全部是 "solver run failed or no output"。

### 2.2 初步假设（错误的）

初始判断：Sonnet 代码质量差，写了原地修改 solution 的算子，导致内部一致性破坏。

LLM 也被同样误导，尝试了多种修复方向：
- "确保 deep_copy 在前"
- "使用 fully immutable reads"
- "不引用原始 solution 的可变子对象"

16 轮全部无效。

### 2.3 实际根因

```bash
# 在实际 workspace 上复现 V5
$ cd ~/research/scion-experiments/sprint-f/f3/workspaces/4263897b-...
$ python solver.py data/instance_small_1.json --seed 77 ...

Traceback (most recent call last):
  File "solver.py", line 125, in _load_operators_from_registry
    cls = getattr(module, entry["class_name"])
AttributeError: module 'operators.subcategory_pair_merge' has no attribute 
'SubcategoryPairMerge'. Did you mean: 'SubcategoryPairMergeFixed'?
```

**真实根因**：`action=modify` 时 Sonnet 把算子类名从 `SubcategoryPairMerge` 改成了 `SubcategoryPairMergeFixed`，但 `_sync_pool_registry()` 没有更新 `registry.yaml` 里的 `class_name` 字段。

之后每轮 V5 check 都在尝试加载已经不存在的类名：
```
registry.yaml: class_name=SubcategoryPairMerge
operators/subcategory_pair_merge.py: class SubcategoryPairMergeFixed
→ AttributeError → solver crash → V5 "solver run failed"
```

**为什么 V5 失败而不是更早被发现**：
- Contract Gate 检查代码格式/接口，不检查类名是否与 registry 一致
- V5 的 failure detail 只有 "solver run failed or no output"，不传 subprocess stderr
- LLM 永远看不到 AttributeError，只能猜测

**为什么从 round 9 开始**：
- round 8 是该 branch 的第一次类名变更
- 从 round 9 起，V5 每轮都 crash 在同一个地方

**从 F3 archive 复现 V5 失败**：
```
round_9_ (11 ops): 3/3 PASS   ← archive 只存 .py 文件，不存 registry
round_25 (18 ops): 0/10 FAIL  ← 测试结果正常，V5 pass
```

Archive 复现不了——因为 archive 只保存了算子文件，不保存 registry.yaml 的状态。用 archive 构建的 workspace 会重新扫描生成 registry，类名是正确的。

### 2.4 修复

**Sprint H3：Registry class_name AST 同步**

在 `apply_patch` 之后，重新扫描 `.py` 文件的 AST，提取实际的 class 名，更新 registry entry：

```python
# scion/runtime/pool_manager.py
def _sync_pool_registry(self, workspace: str, patch: PatchProposal) -> None:
    ...
    # 重新扫描 .py 文件，更新 class_name
    for entry in registry["operators"]:
        fp = os.path.join(workspace, entry["file_path"])
        if os.path.exists(fp):
            actual_class = _extract_class_name_from_file(fp)
            if actual_class:
                entry["class_name"] = actual_class
```

**Sprint H4：V5/V8 传递 subprocess stderr**

```python
# scion/verification/state_mutation.py
if not result.success or result.output_path is None:
    stderr_snippet = (result.stderr or "")[:500]
    return _cr(False, f"solver run failed: {stderr_snippet}", t0)
```

LLM 现在能看到 `AttributeError: module '...' has no attribute '...'`，不再被误导。

---

## 3. Oracle Bug（H2）

### 3.1 发现时机

在排查 F3 环境问题时，运行 `pytest tests/test_oracle.py`，发现两个失败：

```
FAILED TestHardConstraintViolations::test_H1_capacity_exceeded
  容量超载（总 pallets > vehicle capacity）→ oracle 误报 is_feasible=True

FAILED TestHardConstraintViolations::test_H3_too_many_pickups_donguan
  东莞提货超限（>2 个提货点）→ oracle 误报 is_feasible=True
```

### 3.2 影响链

```
Oracle → Verification Gate feasibility check
       → Screening/Validation/Frozen A/B 比较 Level 1（feasibility）

如果 oracle 放过不可行解：
- 不可行算子通过 V6_feasibility check
- 不可行解参与 A/B 比较，结果失真
```

Sprint F1 的两个 promote 是否受影响：查了实验日志，没有发现 feasibility_violation 的算子，影响有限。但在 oracle 修复前，实验结论"在有已知 oracle bug 的环境下"可信度存疑。

### 3.3 修复（Sprint H2）

CC 读取了 `test_oracle.py` 中的测试用例，在 `oracle.py` 的 `check_feasibility()` 中补齐了两个约束检查：
- H1：`total_pallets > VEHICLE_TYPES[vtype].capacity → infeasible`
- H3：东莞片区提货点数 > 2 → infeasible

**验证**：
```
oracle tests: 16/16 PASS（包括之前失败的 H1 和 H3）
```

---

## 4. 问题汇总与修复一览

| # | 问题 | 影响 | 根因 | 修复 | commit |
|---|---|---|---|---|---|
| H1 | greedy_init uuid | V8 概率失败 | 初始解 vehicle ID 跨进程不确定 | generate_vehicle_id(rng) | 9bab826 |
| H2 | Oracle H1/H3 | 不可行解漏检 | check_feasibility 缺少两个约束 | 补约束 + 城市别名 | d7a48ca |
| H3 | Registry class_name 不同步 | V5 连败雪崩 | modify 改类名后 registry 不更新 | AST 重扫描更新 class_name | 09d0c13 |
| H4 | V5/V8 不传 stderr | LLM 误导 | subprocess 错误被吞 | 传递 stderr snippet | 525f842 |

---

## 5. FailureRouter 升级（Sprint H2）

### 5.1 动机

Sprint F 暴露了 FailureRouter 无状态的根本缺陷：

- F3 的 16 次 V5 crash，FailureRouter 每次独立 `discard`，从未升级为 `infra_suspected`
- F2 的 13 次 V8 失败，同样每次独立处理，没有触发任何升级机制
- LLM 每次只看到单次错误，看不到"这是第 N 次同类失败"

参考 CC 源码的 circuit breaker 设计（`MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3`）。

### 5.2 升级内容（5 项）

**T1: Campaign 级持久计数器**
```python
self._failure_streak: Dict[str, int] = {}   # failure_code → 连续次数
self._total_failures: Dict[str, int] = {}   # failure_code → 累计次数
# 验证 pass 时 clear
```

**T2: streak-based 路由升级**
```python
# light failure 连续 3 次 → infra_suspected（暂停，建议检查环境）
if cat in _LIGHT_CATS and streak >= 3:
    return FailureAction(action="infra_suspected", ...)

# heavy failure 连续 2 次 → abandon_fast（快速放弃分支）
if cat in _HEAVY_CATS and streak >= 2:
    return FailureAction(action="abandon_fast", ...)

# retry 时 escalation_level 随 streak 增加（注入更强提示）
```

**T3: StagnationDetector infra_loop（第五种模式）**
```python
# 同种 failure_code streak >= 5 → should_stop=True, suggestion=check_environment
infra_loop: 5+ consecutive same failure → campaign should stop
```

**T4: 评估路由分级**
```python
wr < 0.3    → abandon_fast（碾压级失败，不值得继续）
wr 0.3-0.6  → continue_explore
wr > 0.6    → continue_explore + high_potential 标记
```

**T5: ContextManager 失败模式注入**
```python
# streak >= 2 时，在 LLM 上下文里注入：
## Failure Pattern Warning
# This branch has failed V5_state_mutation 3 consecutive times.
# Common causes: ...
```

### 5.3 与 CC 设计的对应关系

| CC 模式 | Scion 实现 |
|---|---|
| session 级持久计数器 | `_failure_streak` 跨轮次累积 |
| Escalating retry | `escalation_level` 0→1→2 注入更强提示 |
| Circuit breaker (max=3) | light_streak≥3 → infra_suspected |
| 前台/后台分级 | infra_suspected 不消耗分支预算 |

Scion 特有（CC 没有）：跨轮次实验失败模式 vs CC 单次对话错误。

---

## 6. 回顾：失败分析方法论

本次追踪使用的方法，可作为 Scion 未来失败分析的标准流程：

### V8 追踪方法（rng trace）

```python
# 在 vns.py 里加 trace logging
_trace.append({
    "iter": iteration,
    "rng5": list(rng.getstate()[1][:5]),
    "ops": []
})
for sol in current_pool:
    rb = list(rng.getstate()[1][:3])
    candidate = op.execute(sol, rng)
    ra = list(rng.getstate()[1][:3])
    _trace[-1]["ops"].append({"op": op.name, "rb": rb, "ra": ra})
```

1. 找 rng 第一次分叉的 iteration
2. 检查该 iteration 的 op 哪个 rb==rb 但 ra!=ra
3. 检查上一个 iteration 的 new_solutions hash

**关键观察**：如果 iteration 0 的所有 op rng 一致但 new_solutions hash 不同 → 问题在初始解生成（greedy_init）。

### V5 追踪方法

1. 先在实际 workspace（不是 archive）复现
2. 直接运行 solver subprocess，看完整 stderr
3. archive 复现不了 V5 是因为 archive 不含 registry.yaml 快照

---

## 7. Sprint F2 配置

基于上述修复，Sprint F2 重新设计：

| 实验 | 模型 | 轮次 | 启动时间 |
|---|---|---|---|
| F1 | Claude Opus 4-6 | 80r | 2026-04-13 00:03:47 |
| F2 | Claude Opus 4-6 | 80r | 2026-04-13 00:04:19 |
| F3 | Claude Sonnet 4-6 | 80r | 2026-04-13 00:04:47 |

**变化**：
- 轮次从 30/50/30 提升至 80/80/80
- F1/F2/F3 全并行（workspace copytree 完全隔离，无 __pycache__ 冲突）
- 内存安全（峰值 ~800MB，服务器可用 2.3GB）
- 完成后各自 openclaw system event 推送

产物目录：`~/research/scion-experiments/sprint-f2/`

---

## 8. 教训

1. **失败归因要先排框架/环境，再排 LLM 能力**（postmortem #001 教训3 再次验证）
2. **基线代码也有 bug**（postmortem #001 教训5 再次验证——uuid 修了算子，漏了 greedy_init）
3. **错误信息必须完整传递给 LLM**（V5 吞 stderr 导致 16 轮无效迭代）
4. **registry 和代码必须保持同步**（class_name 是隐性约定，modify 必须同步更新）
5. **trace logging 是确定性 bug 的最可靠追踪手段**（不要停留在 aggregate metrics）

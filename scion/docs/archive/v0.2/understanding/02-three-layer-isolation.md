# 02 — 三层隔离

三层隔离解决的是**代码安全性**问题：LLM 生成的代码能不能被信任，能不能放进实验环境运行。

> 注意：三层隔离 ≠ 三级实验协议。前者是安全门控，后者是统计验证。见 [03](03-experiment-protocol.md)。

---

## 整体流水线

```
LLM 生成代码
    ↓
[Contract Gate]      ← 静态分析，不运行代码，检查结构合规性
    ↓ 通过
[Verification Gate]  ← 运行一次，检查语义正确性
    ↓ 通过
[Decision Input Guard] ← 实验结果转换为纯数值，切断文本通道
    ↓
Decision Engine（确定性）
```

---

## Layer 1：Contract Gate（结构边界）

**作用**：在代码运行之前，通过静态分析拦截结构性违规。

**实现**：AST 解析 + 规则检查（C1-C10）

| 检查项 | 说明 |
|--------|------|
| C1 | 接口签名必须是 `execute(solution, rng) -> Solution` |
| C5 | import 白名单（禁止 `random`、`uuid`、`datetime` 等非确定性模块） |
| C8 | 随机源必须来自参数 `rng`，不能用全局随机 |
| C9b | AST 扫描 `from X import Y` 和 `import X as Y` 形式的非法随机源 |
| C10 | 禁止 shell/subprocess/socket 等敏感调用 |

**为什么用 AST 而不是字符串搜索？**

字符串搜索会被绕过：
```python
import random as rng_helper   # grep "import random" 找不到
from random import randint     # grep 找不到
```
AST 解析看的是语法结构节点，不看字符串，无法被重命名或变形绕过。

---

## Layer 2：Verification Gate（语义正确性）

**作用**：把代码放进隔离的 subprocess 里运行，验证语义层面的正确性。

**为什么用 subprocess 隔离？**
- 防止 LLM 代码修改主进程状态
- `os.setsid()` 让 subprocess 成为独立进程组，超时时可 SIGKILL 整个组，不留僵尸进程

**验证清单（优先级排序）：**

| # | 检查项 | 类型 |
|---|--------|------|
| V1 | import / syntax | P0（轻度，可重试）|
| V2 | interface compliance | P0（轻度）|
| V3 | unit tests | P0（轻度）|
| V5 | state mutation（double-run 比较结果是否一致） | P0（重度，不重试）|
| V8 | nondeterminism（运行两次结果是否相同） | P0（重度）|
| V-wall | wall-clock guard | P0（重度）|

**V5/V8 的历史教训（uuid 事故）：**

2026-04-11 发现：`uuid.uuid4()` 在算子里调用会导致 V8_nondeterminism 失败率达 75%。根因是每次运行生成不同 UUID，解法是用 `generate_vehicle_id(rng)` 替代，从 import 白名单中移除 uuid。

---

## Layer 3：Decision Input Guard（决策输入白名单）

**作用**：切断 LLM 自由文本进入决策逻辑的通道。

**为什么需要？**

LLM 可能在 hypothesis 里写："此算子效果显著，建议直接 promote"。如果这段话流入决策层，LLM 实际上在通过措辞影响自己的晋升结果——**自我实现偏差**。

**实现**：`DecisionFeatures`，一个 Pydantic v2 严格类型的 dataclass：

```python
@dataclass(frozen=True)
class DecisionFeatures:
    branch_id: str
    stage: Literal["screening", "validation", "frozen"]
    contract_passed: bool
    verification_passed: bool
    canary_passed: bool
    n_cases: int
    win_rate: Optional[float]      # float，无文本
    median_delta: Optional[float]  # float，无文本
    ci_low: Optional[float]
    ci_high: Optional[float]
    retry_count: int
    failure_codes: Tuple[str, ...]  # 枚举，非自由文本
    budget_remaining_ratio: float
    # ← 没有任何 str 自由文本字段
```

类型系统本身就是守卫——Pydantic 拒绝将字符串赋值给 float 字段。Decision Engine 在物理上无路径访问 LLM 的 hypothesis_text 或 rationale。

---

## 数据权限矩阵

| 数据类型 | LLM 可写 | Contract | Verification | Protocol | Decision |
|---------|:---:|:---:|:---:|:---:|:---:|
| hypothesis_text | ✅ | 仅校验 | ❌ | ❌ | **❌** |
| patch/code | ✅ | ✅ | ❌ | ❌ | **❌** |
| verification_result | ❌ | ❌ | ✅ | ❌ | ✅ |
| aggregate stats | ❌ | ❌ | ❌ | ✅ | ✅ |
| pass/fail label | ❌ | ❌ | ❌ | ✅ | ✅ |

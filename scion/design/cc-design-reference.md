# Scion CC 源码设计参考文档

*撰写日期：2026-04-11*
*来源：CC 源码分析报告 #11~#15 + Scion 架构文档 v3 + v0.2 设计文档 + Postmortem #001*
*作者：Cris（综合分析）*
*状态：设计参考 — 可操作*

---

## 1. 概述

### 1.1 研究背景

2026 年 4 月，团队对 Claude Code（CC）的 1900 文件泄露源码进行了系统性分析，产出 5 份专题报告（#11 工具系统、#12 记忆与压缩、#13 任务协调、#14 核心服务、#15 命令与状态），覆盖 CC 在工具定义、错误处理、子 agent 分发、上下文管理、API 重试、记忆提取、任务编排等核心领域的设计实现。

研究的出发点并非"复刻 CC"，而是通过对比一个**工程上成熟、经实际大规模使用验证**的 agent 框架，识别 Scion 在当前设计中的可改进点。CC 与 Scion 的目标截然不同——CC 是通用 AI 编程助手，Scion 是面向组合优化算法自动研究的专用框架——但在 agent 架构的若干底层共性问题（结构化输出、错误反馈链、上下文管理、子任务协调、健壮性）上，CC 的解法具有直接的参考价值。

### 1.2 研究目标与方法

本次研究聚焦以下问题：**CC 在哪些具体工程决策上，解决了 Scion 当前或潜在的效率/可靠性问题？** 分析方法为跨模块对照：将 CC 的每个核心设计映射到 Scion 的对应模块，评估 Scion 当前实现与 CC 设计之间的差距，并以"对 Scion 实验效率的实际影响"为唯一排序标准给出优先级。

所有结论均基于 5 份 CC 分析报告中的具体发现和代码引用，结合 v0.1 Postmortem（#001）中已验证的实际失效案例。本文档不生成任何未经报告支撑的推测性建议。

### 1.3 文档用途

本文档是 Scion v0.2 及后续版本设计的参考输入。§2 提供全量对照分析表，§3 展开 P0 改进的详细实现方案，§4 列出 P1 改进清单，§5 列出不建议引入的 CC 设计及原因，§6 将改进点与 v0.2 现有任务（T01-T18）对应，并指出需要新增的任务。

---

## 2. 对照分析表

按 Scion 模块分组，每行一个改进点。优先级：P0 = 对实验效率影响最大，P1 = 中等，P2 = 低优先级。

| Scion 模块 | 当前设计 | CC 对标模块 | CC 做法 | 建议改进 | 优先级 | 来源报告 |
|---|---|---|---|---|---|---|
| **ProposalEngine** | `code_content` 嵌入 JSON 字符串，100+ 行 Python 代码在 JSON 内逐字符 escape | Tool System / `mapToolResultToToolResultBlockParam()` | `tool_result.content` 为 ContentBlock 数组，code 作为独立 text block，不经过 JSON 字符串序列化 | 用多 content block 替换单 JSON 字符串嵌套；代码块独立存放不 escape | **P0** | #11 §4 |
| **ProposalEngine** | JSON 格式错误直接进入 LLM 执行路径，无前置结构校验 | Tool System / `validateInput()` | 执行前无副作用校验，失败返回 `{result:false, message, errorCode}`，模型看到错误后自行修正 | 增加 Pydantic 前置校验层；格式失败直接构造 tool_result 错误反馈，不进执行路径 | **P0** | #11 §2.1 |
| **Verification Gate (V5)** | V5 失败只返回 `run1_objective != run2_objective`，无失败分类，LLM 被误导到错误修复方向（postmortem #001 已验证） | Tool System / `classifyAPIError()` + Task System / `stuck.ts` | 错误分类 + 分类后提供不同诊断路径；错误信息通过语义化 tag 路由 | V5 失败分三类（ENV_NONDETERMINISM / CANDIDATE_NONDETERMINISM / UNKNOWN）；提供两次 run 的完整输出 diff 和候选代码快照 | **P0** | #14 §1.3 / Postmortem #001 §4 |
| **Context Manager** | Hypothesis blacklist 基于文本记录，无机制层级去重；10/10 假设都是同族机制（subcategory consolidation 变体） | Memory System / `extractMemories` 四类型 + Session Memory 固定10节 | 记忆分4个封闭类型（user/feedback/project/reference），每类有结构化存储规则；feedback 类型等同保存"确认"和"纠正" | 引入 HypothesisFamily 机制标签；记录每族失败次数；连续失败 N 次后主动引导 LLM 切换 action/locus/mechanism | **P0** | #12 §2 / #13 §11.2 |
| **Proposal Engine** | LLM 生成代码失败时整个 Proposal 失败，无降级 | Tool System / AgentTool 的 `syncAgentError` 处理 | 子 agent 出错但有部分 assistant 消息时，返回已有内容而非抛错；有内容优于完全失败 | Code 生成失败时若 Hypothesis 已成功，返回 hypothesis-only 结果让主循环决定是否重试 code | **P0** | #11 §2.3 |
| **LLM Client** | 重试策略无 query source 分级，后台任务和前台任务共用同一重试配额 | API Service / `withRetry.ts` `QuerySource` 分级 | 后台 query source（summaries, suggestions）529 → 立即放弃，不占主线程重试配额；前台任务才做指数退避重试 | 区分前台（campaign 主循环）/ 后台（autoDream/summary 等）LLM 调用；后台调用 429/529 立即放弃 | P1 | #14 §1.2 |
| **LLM Client** | LLM API 错误不注入对话历史，模型无法感知错误后自主决策 | API Service / `getAssistantMessageFromError()` | 将 API error 转为 `AssistantMessage(isApiErrorMessage=true)` 注入历史，模型可看到错误后重试或换策略 | rate_limit / tool_error 等 LLM 可感知的错误注入 conversation history | P1 | #14 §1.3 |
| **Campaign Controller** | 上下文增长时无结构化压缩；历史实验记录随轮次增加 context 线性膨胀 | Compact System / `sessionMemoryCompact` | 有结构化笔记时零 LLM 调用直接压缩；历史渲染为结构化表格（hypothesis/failure/benchmark）作为替代摘要 | 使用已有 HypothesisRecord 和 VerificationResult 做结构化渲染压缩，不调用 LLM；仅在记录不存在时回退 LLM 摘要 | P1 | #12 §4 |
| **Scheduler** | 停滞检测只有 `consecutive_fully_abandoned_branches >= threshold`，缺少模式级停滞识别 | Task System / `stuck.ts` + Token Budget 边际收益检测 | `stuck.ts` 检测 CPU/D-状态/RSS/僵尸等维度；Token budget 检测连续 2 次增量 < 500 触发强制停止 | 引入 StagnationDetector：检测 oscillation（结果在两值间反复）/ plateau（N 轮无改善）/ collapse（突然大幅退步） | P1 | #14 §2.3 / #13 §11.5 |
| **Verification Gate** | 验证逻辑与实验生成共享同一对话上下文；验证者可能受实现者先入叙述影响 | Task Coordination / `verify.ts` + coordinatorMode | "验证是证伪而非确认"；Verification worker 必须 spawn fresh，不继承实现者上下文 | VerificationGate LLM 调用使用独立上下文（不含实验生成 messages），只注入：实验结果 + 验证标准 + 历史验证日志 | P1 | #13 §6 / #13 §11.4 |
| **ContractGate** | import 白名单允许 uuid；`uuid.uuid4()` 是 V5 失败的真实根因（postmortem #001 已验证） | Tool System / `bashSecurity.ts` | 多层静态分析：危险 API 模式（命令替换/进程替换/Zsh特殊命令）在 Tree-sitter 层精确检测 | 补充 import 白名单中 API 危险性评注（uuid/random/os.urandom 等非 rng 随机源）；Contract 校验中增加 non-rng 随机源使用检测 | P1 | #11 §5 / Postmortem #001 §3 |
| **Lineage Registry** | `campaign_summary.json` 缺少 `protocol_result`、`code_content` 归档；无法从单一 summary 还原每轮细节 | State Management / SessionHistory + AppState | AppState 各 task 有完整状态（进度、磁盘输出路径、代码快照 symlink）；session sidecar 支持 --resume 恢复 | 扩展 campaign_summary：加入 `protocol_result`、`case_feedback` 摘要、`code_archive_ref`、`verification_detail` | P1 | #14 §5 / #15 §4.3 |
| **Decision Engine** | BudgetState 无安全阈值，预算用满才终止；可能在临界点反复调用 | Token Budget / `checkTokenBudget()` | `COMPLETION_THRESHOLD=0.9`（到 90% 认为"够了"）；连续2次增量 < 500 token → 边际收益递减强制停止；`nudgeMessage` 推动继续工作 | 引入 budget 安全阈值（90%）；连续轮次无进展时注入"当前方向已收敛，请换思路"的 nudge message | P1 | #14 §2.3 |
| **Campaign Controller** | 无 fire-and-forget 后台任务隔离；autoDream 等类似任务若与主循环共享资源可能引发竞争 | Stop Hooks / `handleStopHooks()` | 后台任务（PromptSuggestion/extractMemories/autoDream）在 stop hook 以 void fire-and-forget 执行，不阻塞主循环 | 后台类任务（记忆提取、campaign 中期诊断）与主实验循环显式解耦，fire-and-forget 执行 | P2 | #14 §4 |
| **Experiment Protocol** | 边界值结果（score 在 promote 阈值 ±ε 内）立即采信 | Task System / RemoteAgentTask 稳定空闲检测 | 连续 5 次 idle 才认为 session 真正完成，防把 tool turn 间歇误判为完成 | 对边界值结果去抖：连续 2 次验证通过才触发 promote，避免噪声误 promote | P2 | #13 §11.6 |
| **Context Manager** | LLM 使用压缩后历史时无"如何找回被压缩详细记录"的指引 | Memory System / "Searching past context" grep 指令 | 记忆 prompt 末尾提供精确 grep 指令；压缩后注入"历史已压缩，用 FileRead: experiments/\<id\>.json 查细节"指引 | 压缩后的上下文中加入检索指引，指向具体 artifact 路径 | P2 | #12 §8 |

---

## 3. P0 改进详述

### P0-1：ProposalEngine — 代码输出多 content block 序列化

**当前 Scion 的具体问题**

`ProposalEngine` 的 Round 2（Code Generation）让 LLM 在 JSON 字符串中直接生成 `code_content` 字段。当候选代码超过 100 行时，JSON 字符串内的多行字符串、引号、反斜杠需要逐字 escape，导致 JSON 格式错误频率随代码长度急剧上升。这是当前 Proposal 格式失败的首要来源。

**CC 的具体设计（见报告 #11 §4）**

CC 的 `AgentTool.mapToolResultToToolResultBlockParam()` 将子 agent 输出序列化为 `ContentBlock[]` 数组，每个逻辑单元是独立的 text block：

```typescript
// AgentTool.tsx: mapToolResultToToolResultBlockParam
return {
  tool_use_id: toolUseID,
  type: 'tool_result',
  content: [
    ...contentOrMarker,  // 子 agent 实际输出（多个 block）
    { type: 'text', text: `agentId: ${data.agentId}\n<usage>...</usage>` },
  ],
}
```

代码内容作为独立 text block 存放，不嵌入外层 JSON 字符串，彻底规避 escape 问题。

**建议的实现方案**

Round 2 的 tool schema 改为两个独立字段的多 content block 输出：

```python
# 当前（问题设计）
class PatchProposal:
    file_path: str
    action: str
    code_content: str  # ← 嵌入 JSON 字符串，100行代码全部 escape

# 建议（CC 多 content block 模式）
# 让模型生成如下结构：
# tool_result.content = [
#   {"type": "text", "text": "<file_path>operators/new_op.py</file_path>"},
#   {"type": "text", "text": "<action>create</action>"},
#   {"type": "text", "text": "<code_content>\n# 代码正文，无需 escape\ndef execute(...):\n    ...\n</code_content>"},
# ]

def parse_proposal_from_blocks(blocks: list[dict]) -> PatchProposal:
    """从多 content block 解析 PatchProposal，不经 JSON 反序列化"""
    text = "\n".join(b["text"] for b in blocks if b["type"] == "text")
    file_path = extract_xml_tag(text, "file_path")
    action = extract_xml_tag(text, "action")
    code_content = extract_xml_tag(text, "code_content")
    return PatchProposal(file_path=file_path, action=action, code_content=code_content)
```

如 Anthropic API 限制强制要求单 content 字符串，退而求其次使用 XML 标签分隔（CC 的 `<usage>` 模式），而不是 JSON 字符串嵌套：

```
tool_result.content = "<file_path>op.py</file_path><action>create</action><code_content>
# 代码正文，无 JSON escape 问题
</code_content>"
```

**预期收益**

代码生成的 JSON 格式错误率预计下降 80%+（当前 code_content 相关失败是主要失败来源）。每次格式失败意味着一次 LLM 重试调用浪费，修复后可显著提升 Proposal 成功率。

**风险/成本**

改动范围：仅 ProposalEngine 的序列化层（`engine.py` 的 prompt template + tool schema + 输出解析）。不涉及 ContractGate、VerificationGate 等下游组件。改动量小。风险：需要确认 Anthropic API 当前是否支持 tool_result 的 content 数组形式（已知支持）。

---

### P0-2：Verification Gate — V5 诊断分类与代码级根因

**当前 Scion 的具体问题**

V5 失败的诊断信息只有 `run1_objective != run2_objective`，没有失败分类。Postmortem #001 详细记录了这一缺陷的代价：6 轮迭代中 LLM 被 V5 的错误 suggestion（"ensure deepcopy"）引向了一个不存在的问题（mutation），而真实根因是 `uuid.uuid4()` 不受 rng 控制。失败信号没有帮助 LLM 定位根因，反而产生了系统性误导。

**CC 的具体设计（见报告 #14 §1.3）**

CC 的 `classifyAPIError()` 将所有 error 规范化为 string tag，与处理逻辑完全解耦。`getAssistantMessageFromError()` 将 error → `AssistantMessage` 注入历史：

```typescript
// errors.ts: classifyAPIError()
// error → tag 映射（prompt_too_long / rate_limit / tool_use_mismatch 等）
// errorDetails 存储原始数据供下游精确处理
```

CC 的 `stuck.ts` 也体现了类似原则：多维度检测（CPU/D-状态/RSS/子进程），不同维度有不同路由，而非单一指标触发单一建议。

**建议的实现方案**

**Step 1：V5 失败分类**

```python
@dataclass
class V5FailureDetail:
    category: Literal[
        "ENV_NONDETERMINISM",        # PYTHONHASHSEED/环境变量差异导致
        "CANDIDATE_NONDETERMINISM",  # 候选代码本身有非确定性
        "UNKNOWN_NONDETERMINISM",    # 无法自动判断
    ]
    run1_objective: float
    run2_objective: float
    run1_output_path: str       # 完整 output JSON 归档路径
    run2_output_path: str
    code_snapshot_path: str     # 候选代码快照
    diff_summary: str           # 两次 run 中第一处分叉点（可选，轻量实现）
    suggested_fix: str          # 基于 category 给出的定向建议
```

**Step 2：基于 category 的定向诊断建议**

```python
V5_SUGGESTIONS = {
    "ENV_NONDETERMINISM": (
        "非确定性来自运行环境（PYTHONHASHSEED 或系统熵源），而非候选代码逻辑。"
        "请检查：是否调用了 os.urandom()、uuid.uuid4()、time.time() 等外部熵源？"
        "修复：所有随机性必须通过 rng 参数，使用 generate_vehicle_id(rng) 替代 uuid.uuid4()。"
    ),
    "CANDIDATE_NONDETERMINISM": (
        "非确定性来自候选代码内部逻辑。"
        "请检查：set 迭代顺序、dict 插入顺序（依赖 uuid key）、未通过 rng 的随机调用。"
        "修复：对所有中间集合使用 sorted() 保证遍历顺序，所有随机性通过 rng 参数传入。"
    ),
}
```

**Step 3：分类判断逻辑**

```python
def classify_v5_failure(run1_result, run2_result, candidate_code: str) -> str:
    # 如果固定 PYTHONHASHSEED 后重跑能复现分叉 → CANDIDATE_NONDETERMINISM
    # 否则 → ENV_NONDETERMINISM（环境熵导致）
    # 实现复杂时先默认 UNKNOWN，手动分析
    if "uuid.uuid4()" in candidate_code or "os.urandom" in candidate_code:
        return "CANDIDATE_NONDETERMINISM"
    return "UNKNOWN_NONDETERMINISM"
```

**预期收益**

Postmortem #001 显示：V5 的错误诊断方向导致 6 轮（60-75% 的假设预算）被完全浪费。正确的诊断链可以在第 1-2 次失败时就定位根因，而非在 6 次失败后还在错误方向上打转。直接收益是实验预算利用率提升。

**风险/成本**

改动范围：`verification/checks.py`（V5 check 逻辑）+ `context_manager.py`（诊断建议注入）。代码快照归档已在 T02/T04 中规划。分类判断逻辑可以从简单静态分析开始（grep `uuid.uuid4`），逐步增强。

---

### P0-3：Context Manager — Hypothesis Family Tracking + 策略切换引导

**当前 Scion 的具体问题**

v0.1 实验中 10/10 假设都是 `create_new + vehicle_level + subcategory consolidation` 的变体（见 v0.2 设计文档 §2.2）。当前 blacklist 基于"文本去重"，无法识别语义等价的机制变体。LLM 不知道自己已经在同一族机制上连续失败了多少次，也不知道哪些 locus/action 还从未被探索。

**CC 的具体设计（见报告 #12 §2 + 报告 #13 §11.2）**

CC 的 `extractMemories` 将记忆约束在 4 个封闭类型，核心原则是"只存储无法从当前状态推导的内容"。特别值得注意的是 `feedback` 类型：CC 明确要求**保存"用户的确认"等同保存"纠正"**，防止模型只记失败从而变得过度保守。这一原则直接对应 Scion 的问题：如果 hypothesis memory 只记"失败了"，而不记"什么机制曾经被验证有效"，LLM 会越来越保守，最终陷入同一族安全机制的反复尝试。

CC 的 coordinatorMode prompt 还包含明确的"Continue vs. Spawn"决策框架，核心原则是：**当前上下文的失败经验会锚定后续尝试**，应在必要时 spawn fresh（见报告 #13 §2.3）。

**建议的实现方案**

**Step 1：HypothesisFamily 数据结构**

```python
@dataclass
class HypothesisFamily:
    family_id: str
    mechanism_label: str     # e.g., "subcategory_consolidation", "destroy_rebuild"
    action_pattern: str      # "create_new" / "modify" / "remove"
    locus_pattern: str       # "vehicle_level" / "order_level"
    evidence_count: int
    statuses: list[str]      # ["rejected", "rejected", "borderline", "promoted"]
    last_outcome: str
    notes: str               # 人/LLM 可读摘要
```

**Step 2：Coverage Reporting（注入 Context）**

```python
def build_exploration_coverage(families: list[HypothesisFamily]) -> str:
    """构造探索覆盖度报告，注入 hypothesis 生成 prompt"""
    action_counts = Counter(f.action_pattern for f in families)
    locus_counts = Counter(f.locus_pattern for f in families)
    
    report = "## 当前探索覆盖度\n"
    report += f"- action 分布：{dict(action_counts)}\n"
    report += f"- locus 分布：{dict(locus_counts)}\n"
    
    # 连续失败族：明确提示切换
    stale_families = [f for f in families if f.evidence_count >= 3 
                      and all(s == "rejected" for s in f.statuses[-3:])]
    if stale_families:
        report += "- 以下机制族连续3次失败，建议切换方向：\n"
        for f in stale_families:
            report += f"  - {f.mechanism_label}（{f.action_pattern}/{f.locus_pattern}）\n"
    
    # 未探索 locus：主动提示
    unexplored = [l for l in ["order_level", "vehicle_level"] 
                  if locus_counts.get(l, 0) == 0]
    if unexplored:
        report += f"- 以下 locus 尚未探索：{unexplored}\n"
    
    return report
```

**Step 3：已验证策略的正向记录（CC feedback "确认"等同"纠正"原则）**

```python
# 在 hypothesis memory 中，不只记"失败"
FAMILY_MEMORY_TEMPLATE = """
## 机制族：{mechanism_label}

**探索记录**：{evidence_count} 次尝试
**结果分布**：{status_summary}

**有效的子变体**（如有 promoted/borderline）：
{successful_variants}

**无效的子变体**（连续失败）：
{failed_variants}

**建议**：{guidance}
"""
```

**预期收益**

v0.1 中超过 70% 的实验预算被用于探索同一族机制的变体，其中大多数失败。有效的探索覆盖度提升可以直接提高"每单位 LLM 调用产生真正新信息"的比率，是外层搜索效率的关键瓶颈。

**风险/成本**

改动范围：`context_manager.py`（注入 coverage 报告）+ `lineage.py` 或 SQLite（新增 `hypothesis_families` 表）+ hypothesis prompt template。改动量中等。机制族标签可以先用 rule-based 分类（基于 mechanism_label 字段前缀），不需要 embedding clustering。

---

### P0-4：ProposalEngine — Hypothesis 成功但 Code 失败时的降级恢复

**当前 Scion 的具体问题**

Round 2（Code Generation）失败时，整个 Proposal（包括已成功的 Round 1 Hypothesis）被丢弃。即使 hypothesis 本身是高质量的方向，code 生成的一次失败就会让整个轮次的 hypothesis 工作付诸东流。

**CC 的具体设计（见报告 #11 §2.3）**

CC 的 AgentTool 在 sync 执行路径的 catch 块中：

```typescript
// AgentTool.tsx: syncAgentError 处理
if (syncAgentError) {
  const hasAssistantMessages = agentMessages.some(msg => msg.type === 'assistant')
  if (!hasAssistantMessages) {
    throw syncAgentError  // 无内容则重新抛出
  }
  // 有消息则降级：返回已收集内容（有内容优于完全失败）
  logForDebugging(`Sync agent recovering from error with ${agentMessages.length} messages`)
}
```

核心原则：**有内容就返回有内容的，部分完成优于完全失败**。

**建议的实现方案**

```python
class ProposalEngine:
    async def generate_proposal(self, branch_context) -> ProposalResult:
        # Round 1: Hypothesis
        hypothesis = await self._run_hypothesis_round(branch_context)
        if hypothesis is None:
            return ProposalResult(status="hypothesis_failed")
        
        # Round 2: Code（失败时降级而非抛出）
        try:
            patch = await self._run_code_round(branch_context, hypothesis)
            return ProposalResult(status="complete", hypothesis=hypothesis, patch=patch)
        except ProposalCodeError as e:
            # 降级：返回 hypothesis-only，让主循环决定是否重试 code
            logger.warning(f"Code generation failed, returning hypothesis-only: {e}")
            return ProposalResult(
                status="hypothesis_only",
                hypothesis=hypothesis,
                code_error=str(e),
            )
    
class CampaignController:
    def handle_hypothesis_only_proposal(self, result: ProposalResult):
        # 选项1：直接重试 code round（复用已生成的 hypothesis）
        # 选项2：记录 hypothesis 供后续分支复用
        # 选项3：报告给人工处理
        pass
```

**预期收益**

高质量 hypothesis 不会因 code 格式错误而被丢弃。在修复 P0-1（JSON 序列化）之前尤其有价值，可作为临时保护机制。

**风险/成本**

改动量小（仅 ProposalEngine 的错误处理路径）。主要风险：hypothesis-only 状态需要主循环有对应处理逻辑，否则会在状态机中形成死角。

---

### P0-5：ContractGate — Import 白名单中非 rng 随机源检测

**当前 Scion 的具体问题**

Postmortem #001 §3.3 明确记录：`uuid` 在 import 白名单中，`uuid.uuid4()` 调用 `os.urandom()`，产出的 vehicle ID 不受 `rng` seed 控制，是 V5_state_leak 的真实根因。Contract Gate 无法拦截，operator interface spec 虽然说"use rng for all randomness"但没有点名 uuid 是随机来源。

**CC 的具体设计（见报告 #11 §5）**

CC 的 `bashSecurity.ts` 维护 `ZSH_DANGEROUS_COMMANDS` 精确集合，包含所有已知危险 API（zmodload, zpty, zsocket 等）。危险判断不仅基于 import，还基于**调用模式**（命令替换、进程替换、heredoc 嵌入等）：

```typescript
// bashSecurity.ts: ZSH_DANGEROUS_COMMANDS
const ZSH_DANGEROUS_COMMANDS = new Set([
  'zmodload', 'emulate', 'sysopen', 'sysread', 'syswrite',
  'zpty', 'ztcp', 'zsocket', 'mapfile', ...
])
```

**建议的实现方案**

**Step 1：在 import 白名单中区分"允许使用"和"允许 import 但禁止特定调用"**

```yaml
# problem.yaml
import_whitelist:
  - module: "uuid"
    allowed_apis: []             # 完全禁止 uuid.uuid4()
    reason: "uuid.uuid4() calls os.urandom(), bypasses rng. Use generate_vehicle_id(rng)."
  - module: "random"
    allowed_apis: []             # 禁止 Python random 模块（绕过 rng 参数）
    reason: "Use rng parameter instead of random module."
  - module: "collections"
    allowed_apis: ["Counter", "defaultdict", "deque"]
```

**Step 2：ContractGate 的 AST 扫描增强**

```python
NON_RNG_RANDOM_CALLS = {
    "uuid.uuid4", "uuid.uuid1",
    "random.random", "random.randint", "random.choice",
    "os.urandom", "secrets.token_bytes",
    "time.time",  # 作为随机种子时危险
}

def check_non_rng_randomness(code: str) -> list[ContractViolation]:
    """检测代码中使用了非 rng 参数的随机源"""
    violations = []
    tree = ast.parse(code)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = get_call_name(node)
            if call_name in NON_RNG_RANDOM_CALLS:
                violations.append(ContractViolation(
                    type="non_rng_randomness",
                    line=node.lineno,
                    message=f"'{call_name}' bypasses rng. Use rng parameter or generate_vehicle_id(rng).",
                ))
    return violations
```

**预期收益**

从源头拦截 V5_state_leak 的真实根因。若此检测已上线，Postmortem #001 中的 6 轮失败可以在第 1 次 Contract 检查时被截断。这是防止同类问题复发的结构性修复。

**风险/成本**

改动量小（ContractGate AST 扫描层 + problem.yaml 配置）。风险：需要仔细维护"禁止调用"列表，避免误判合法的 uuid 使用（如用于标识符生成而非随机数）。

---

## 4. P1 改进清单

### P1-1：LLM Client — 查询来源分级重试

CC 将 LLM 调用按 `querySource` 分为前台（campaign 主循环）和后台（autoDream/summary/诊断等），后台调用遇 429/529 立即放弃，不占主线程重试配额（见报告 #14 §1.2）。Scion 应在 LLMClient 中区分 `foreground`（主循环）和 `background`（后台诊断/摘要）两类调用，后台调用失败静默降级，避免后台任务占用实验主流程的 API 配额。

### P1-2：LLM Client — API 错误注入对话历史

CC 的 `getAssistantMessageFromError()` 将 rate_limit / context_overflow 等 API error 转为 AssistantMessage 注入对话历史，使模型在感知错误后自主决策（如压缩输入、换策略）（见报告 #14 §1.3）。Scion 的 ProposalEngine 应将 LLM API 错误（context 过长、格式错误等）构造为 `tool_result(is_error=true)` 反馈给模型，而非在框架层静默重试，让模型有机会自行修正。

### P1-3：Campaign Controller — 基于结构化记录的零 LLM 压缩

CC 的 Session Memory Compact 在有结构化笔记时完全不调用 LLM，直接用已有笔记作为摘要（见报告 #12 §4）。Scion 的所有历史都是结构化数据（HypothesisRecord、VerificationResult、ExperimentMetrics），ContextManager 的 `compact()` 应优先使用"结构化渲染"路径：将 hypothesis 历史渲染为 Markdown 表，将 failure_pattern 渲染为 bullet list，只有在结构化数据不存在时才回退 LLM 摘要调用。

### P1-4：Scheduler — 多维停滞检测

CC 的 `stuck.ts` 检测 CPU/D-状态/RSS/僵尸等多维度停滞，不同维度路由不同建议；Token Budget 通过"连续 2 次增量 < 500"检测边际收益递减（见报告 #14 §2.3 + 报告 #13 §11.5）。Scion 应引入 `StagnationDetector` 类，检测：oscillation（结果在两个 objective 值间反复）、plateau（连续 N 轮无 promote、无 borderline）、timeout_cascade（连续超时）等模式，不同模式触发不同响应（换方向/扩大样本/人工介入）。

### P1-5：Verification Gate — 独立验证上下文原则

CC 的 `verify.ts` 明确要求验证 worker 必须 spawn fresh（不继承实现者上下文），定义验证为"prove the code works, not confirming it exists"（见报告 #13 §6.2）。Scion 的 VerificationGate LLM 调用（如果有）应使用完全独立的上下文，只注入：实验结果 + 验证标准 + 历史验证日志，不传入任何实验生成过程中的 messages，防止验证者被实现者的叙述框架锚定。

### P1-6：ContractGate — API 危险性动态 AST 扫描

在 Postmortem #001 修复（uuid 白名单）的基础上，参考 CC 的 `bashSecurity.ts` 多层防御模式（见报告 #11 §5.2），将 ContractGate 的静态分析从"import 白名单"扩展为"调用模式分析"：不仅检查 import 的模块，还检查实际调用的 API（`uuid.uuid4()`、`random.random()`、`os.urandom()` 等非 rng 随机源），提供精确的违规位置和修复建议。

### P1-7：Lineage Registry — 完整 Campaign Artifact Schema

CC 的 AppState 每个 task 有完整状态（进度、磁盘输出 symlink、代码快照），支持 `--resume` 恢复（见报告 #14 §5）。Scion 的 `campaign_summary.json` 应扩展为研究级 artifact：加入 `protocol_result`（每阶段 win_rate/median_delta/gate）、`case_feedback` 摘要、`code_archive_ref`（失败候选代码的稳定归档路径）、`verification_detail`。这样 future analysis 不必重新爬 SQLite。

### P1-8：Decision Engine — 预算安全阈值与 nudge 机制

CC 的 Token Budget 使用 `COMPLETION_THRESHOLD=0.9`（到 90% 时认为"够了"，留 10% 余量），并在触发"继续"时注入 `"Keep working — do not summarize."` 的 nudge message（见报告 #14 §2）。Scion 的 BudgetState 应引入类似的安全阈值（避免在临界点反复触发边界检查）；在预算使用过半但无进展时，注入"当前方向已连续 N 轮无改善，请考虑切换机制族"的 nudge message，主动打破探索停滞。

### P1-9：Campaign 中期停滞诊断（autoDream 三重门控借鉴）

CC 的 autoDream 用时间 + session 数量 + 分布式锁三重门控触发记忆巩固（见报告 #13 §4）。Scion 应设计 Campaign Mid-Check：当满足 `连续验证失败 >= 3`、`过半轮次无 promote`、`预算耗用 >= 50%` 其中任意条件时，触发一次以 Opus 级别 LLM 进行的诊断分析，将诊断结论注入 hypothesis history，不自动执行任何操作（仅提供分析参考）。

### P1-10：Campaign 后分析 — 强制代码级根因追溯流程

Postmortem #001 §6 教训 1 指出：设计了完整 lineage 和 artifact 归档，但从未真正追溯。CC 的 `verify.ts` 体现的"证伪"而非"确认"文化（见报告 #13 §6.2）提示 Scion 应在流程层面而非工具层面保证分析质量。建议在 Scion CLI 中增加 `scion postmortem` 命令：对每类失败模式自动抽样 1 个 case，打印候选代码 + 失败 detail + 建议分析路径，强制产出代码级根因报告。

---

## 5. 不建议引入的 CC 设计

以下 CC 设计在 CC 的场景中合理，但不适用于 Scion，附简要说明：

| CC 设计 | 为什么不适用于 Scion |
|---|---|
| **TUI 实时进度（AgentSummary，每 30s 一次 3-5 词描述）** | Scion 的实验轮次以分钟计，不需要秒级 UI 更新；每 30s 额外 LLM 调用会显著提高成本。Scion 用结构化 log + SQLite lineage 提供可观测性已足够。（见报告 #12 §6） |
| **PromptSuggestion 投机预执行（预测下一条用户输入）** | Scion 是无人值守自动化框架，没有"用户下一步输入"这个概念。（见报告 #14 §7） |
| **toolUseSummary（Haiku 生成工具批次摘要，给移动端 UI）** | Scion 没有移动端 UI，工具批次摘要没有消费方。（见报告 #12 §7） |
| **RemoteAgentTask 云端 CCR Session（向 claude.ai 发起 Teleport）** | Scion 的所有计算在本地/固定集群，不需要云端 agent 分发。（见报告 #13 §1.2）|
| **/loop cron 循环调度（将 prompt 注册为 cron 任务）** | Scion 有自己的 Campaign 主循环，不需要外部 cron 驱动。（见报告 #13 §7） |
| **MagicDocs 自动文档更新（在文件头加 MAGIC DOC: header）** | Scion 的组件文档由人工维护更合适；自动文档更新在 Scion 源码库中引入 CC 依赖的成本高于收益。（见报告 #14 §6）但可在 Scion 开发环境中使用 CC 的 MagicDocs 来维护 Scion 自身的架构文档。 |
| **sessionMemoryCompact 的 minTextBlockMessages=5 保留策略** | Scion 的上下文不是对话消息，而是结构化实验记录；CC 的消息数阈值对 Scion 无直接意义，需要重新定义基于"最少保留 N 轮完整实验"的等价约束。（见报告 #12 §4.3）|

---

## 6. 与 v0.2 任务的对应关系

### 6.1 可融入现有 v0.2 任务的改进

| 改进点 | 融入的 v0.2 任务 | 融入方式 |
|---|---|---|
| P0-2（V5 失败分类 + 代码级诊断） | **T02**（V5 diagnostics enhancement） | T02 的输出 schema 直接采用 `V5FailureDetail` 结构；`ENV_NONDETERMINISM` 分类覆盖 T01 的 PYTHONHASHSEED 修复验证 |
| P0-5（ContractGate 非 rng 随机源检测） | **T01**（Runner deterministic env fix）补充 | T01 修环境，P0-5 修合同层；两者联合才能完整解决 uuid 问题 |
| P1-7（Campaign Artifact 完整性） | **T03**（campaign summary schema upgrade）+ **T04**（candidate code archiving） | T03/T04 的目标字段与 P1-7 完全吻合，直接采用建议的 schema |
| P0-3（HypothesisFamily Tracking） | **T07**（hypothesis family tracking） | T07 的 `HypothesisFamily` 数据结构与本文档建议一致；Coverage Reporting 作为 T08 的实现基础 |
| P0-3（策略切换引导） | **T08**（strategy-shift guidance injection） | T08 的 guidance prompt 基于 P0-3 的 `build_exploration_coverage()` 输出 |
| P1-2（API 错误历史注入） | **T09**（richer case feedback rendering）部分覆盖 | T09 关注的是 case feedback 渲染，P1-2 是 API 错误注入；可在 T09 中一并处理"错误信息对 LLM 可见性" |
| P1-8（预算安全阈值 + nudge） | **T06**（observability fields in report）+ **T03** | BudgetState 的 safety threshold 和 nudge 统计可作为 T06 的 observability 字段纳入 |

### 6.2 需要新增的任务

以下改进点未被 T01-T18 覆盖，建议新增任务：

| 新任务编号 | 任务描述 | 对应改进 | 优先级 |
|---|---|---|---|
| **T19** | ProposalEngine 输出序列化重构：用多 content block 替换 `code_content` JSON 嵌套 | P0-1 | **P0** |
| **T20** | ProposalEngine 降级恢复：Hypothesis 成功但 Code 失败时返回 hypothesis-only 结果 | P0-4 | **P0** |
| **T21** | ContractGate AST 扫描增强：非 rng 随机源调用检测（uuid.uuid4/random/os.urandom） | P0-5 | **P0** |
| **T22** | LLM Client 查询来源分级：前台/后台调用分级重试策略 | P1-1 | P1 |
| **T23** | Campaign 中期停滞诊断（autoDream 模式）：三重门控触发 Opus 级诊断 | P1-9 | P1 |
| **T24** | `scion postmortem` CLI 命令：失败模式自动抽样 + 代码级根因追溯模板 | P1-10 | P1 |
| **T25** | StagnationDetector：oscillation/plateau/collapse 多维停滞检测 | P1-4 | P1 |

### 6.3 总体优先级建议

建议 v0.2 的任务执行顺序在当前 Phase 0/1/2/3 基础上，将以下新任务插入对应阶段：

```
Phase 1（Foundation）: T01, T02, T03, T04, T05, T06
  + 新增: T19（P0-1，ProposalEngine 序列化）
  + 新增: T20（P0-4，降级恢复）
  + 新增: T21（P0-5，AST 随机源扫描）

Phase 2（Search Efficiency）: T07, T08, T09, T10, T11
  + 新增: T22（P1-1，LLM 分级重试）
  + 新增: T25（P1-4，StagnationDetector）

Phase 3（Parameter Search）: T12-T18
  + 新增: T23（P1-9，中期诊断）
  + 新增: T24（P1-10，postmortem CLI）
```

---

*本文档基于 CC 分析报告 #11（工具系统）、#12（记忆与压缩）、#13（任务协调）、#14（核心服务）、#15（命令与状态）及 Postmortem #001 的具体发现撰写，所有改进建议均有来源报告编号和代码位置支撑。如需查阅原始证据，参见 `~/research/claude-code-src/analysis/` 下对应报告。*

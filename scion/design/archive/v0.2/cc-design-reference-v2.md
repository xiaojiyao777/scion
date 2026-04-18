# Scion CC 源码设计参考文档 v2

*撰写日期：2026-04-11*
*作者：Cris（综合分析）*
*状态：设计参考 — 可直接用于 Sprint E 规划决策*

---

## 1. 概述

### 1.1 研究背景

2026 年 4 月，团队对 Claude Code（CC）1900 文件泄露源码进行了系统性分析，产出 16 份专题报告，覆盖以下全部领域：

| 报告编号 | 主题 | 核心内容 |
|---|---|---|
| #00 | 总结 | 四层架构、Agent 执行主循环、工具系统、状态管理、上下文管理 |
| #01 | 整体架构 | 入口层/服务层/执行层/工具层分层设计 |
| #02 | 主循环深度分析 | queryLoop 异步生成器、工具执行流水线、循环终止条件 |
| #03 | CC vs OpenCode | 架构/权限/执行循环/工具系统横向对比 |
| #04 | Compact 核心 | autoCompact 触发机制、消息分组策略、压缩 prompt 9 部分结构、post-compact 状态重建 |
| #05 | Microcompact + Token | microCompact 三条路径、token 三层估算、工具结果两层防御 |
| #06 | Query 上下文管理 | 主循环上下文管理时序、token 溢出四层防御、system prompt 管理 |
| #07 | 综合上下文管理 | 三级压缩体系全貌、Scion 适用性分析 |
| #08 | 输出解析设计 | tool_use 代码传输、SyntheticOutputTool、四方案对比 |
| #09 | 编排与元控制 | Plan 系统、失败三层恢复、Sub-agent 系统 |
| #10 | Prompt Engineering | System prompt 模块化分层、tool description 设计策略、代码质量负面约束 |
| #11 | 工具系统 | ToolDef 三元泛型、错误处理三层架构、AgentTool 分发设计 |
| #12 | 记忆与压缩深度 | extractMemories 后台提取、Session Memory 10 节模板、记忆类型四分类学 |
| #13 | 任务协调 | Task 七类型体系、coordinatorMode、InProcessTeammateTask、autoDream |
| #14 | 核心服务 | API 重试策略、Token 预算、Policy Limits、Stop Hooks、MagicDocs |
| #15 | 命令/Hooks/状态 | 命令类型体系、命令队列系统、AppState 结构、Skills 技能系统 |

同时，本文档整合以下 Scion 实战文档的全部发现：

| 文档 | 核心内容 |
|---|---|
| v0.1-completion-report | 5 大目标全部达成、3 次 campaign 验证、框架机制触发统计 |
| v0.1-tuning-report | 14 项修复措施、从"从未 Promote"到"稳定 Promote + splits 减半" |
| v0.1.1-changelog | ContextManager 上下文真空修复、实验历史不存储修复、新算子不被加载修复 |
| operator-quality-analysis | 字段名 bug（`subcategory` vs `vehicle_subcategory`）、假设同质化、6 项 context gap 分析 |
| prompt-improvement-plan | 8 项具体 prompt 修改方案（P0-P2） |
| cc-prompt-engineering-analysis | CC prompt 工程 → Scion 7 项改进建议（P0-P3） |
| metrics-guide | Win Rate / Median Delta 定义与解读 |
| postmortem #001 | V5_state_leak UUID 非确定性根因、4 条反馈链失效分析、5 条经验教训 |

以及以下 Scion 架构设计文档：

| 文档 | 核心内容 |
|---|---|
| scion-architecture-v3 | 基石架构：三层控制、双硬闸门、三级协议、22 条锁定决策 |
| scion-engineering-arch-v1 | 工程架构：端到端数据流、模块接口、Runtime Isolation |
| scion-v0.1-design | v0.1 目标、模块实现方案、23 个 task 定义 |
| scion-v0.2-design | v0.2 三部分设计（Foundation + Search Efficiency + Parameter Layer） |
| scion-v0.2-detailed-design | v0.2-MVP 与 v0.2-Full 边界、细化设计 |
| scion-v0.2-development-plan | Sprint A-E 开发计划、测试计划、风险与应对 |

### 1.2 与 v1 的区别

v1 参考文档仅基于 CC 报告 #11-#15 和 Scion v3/v0.2 架构文档撰写。本 v2 版本的关键扩展：

1. **覆盖全部 16 份 CC 报告**（v1 遗漏了 #00-#10 的早期深度分析）
2. **整合 Scion v0.1 全部实战文档**（v1 未参考 completion-report、tuning-report、operator-quality-analysis、prompt-improvement-plan 等关键实战记录）
3. **用 v0.1 实战数据（而非设计理论）驱动优先级排序** — 每个 P0 建议均有实际失败次数/浪费预算的数据支撑
4. **新增"v0.1 实战问题清单"章节** — 从 7 份实战文档中系统提取所有已知问题
5. **新增"已有 CC→Scion 改进的交叉验证"章节** — 对照 cc-prompt-engineering-analysis 中已给出的建议
6. **新增"Sprint E 重构建议"章节** — 基于完整分析给出可执行的 task 清单
7. **v1 的所有 P0/P1/P2 内容保留并扩展**，标注来源

### 1.3 文档用途

本文档是 Scion v0.2 Sprint E 及后续版本设计的核心参考输入。直接面向 BigBOSS 的 Sprint E 规划决策。

---

## 2. CC 架构核心洞察总结（基于 #00-#10 早期深度分析）

### 2.1 CC 主循环设计对 Scion CampaignManager 的启示

**CC 的设计**（#00 §三、#02 全文、#06 §1）

CC 主循环是 `src/query.ts` 中的 `queryLoop` 异步生成器 + `while(true)` 结构。关键工程决策：

1. **上下文管理在 API 调用之前执行**（预防性，非响应性），形成严格流水线：compact boundary 截取 → 工具结果预算截断 → snip → microcompact → context collapse → autocompact → 硬阻断检查 → API call
2. **异常恢复嵌入主循环**：max_output_tokens 截断时自动注入续写提示（最多 3 次），prompt_too_long 时触发 reactive compact
3. **maxTurns 硬限制防无限循环**，Stop Hooks 提供外部终止通道
4. **工具执行流水线**：validateInput → checkPermissions → classifyYoloAction → tool.call → 输出截断/转存 → tool_result 追加

**对 Scion CampaignManager 的启示**：

| CC 机制 | Scion 对应 | 当前状态 | 建议 |
|---|---|---|---|
| 上下文预防性管理（API 前） | ContextManager 在每轮 proposal 前构建 | ✅ 已有 | 保持，但增加 token 预算检查（见 §5.5） |
| 异常恢复 + 续写 | ProposalEngine code 生成截断处理 | ❌ 缺失 | 加入 max_tokens 截断检测 + 重试（v0.1-tuning-report 记录：max_tokens=4096 导致 code_content 被截断） |
| maxTurns 硬限制 | termination.max_experiments | ✅ 已有 | 保持 |
| Stop Hooks 外部终止 | 无等价机制 | ❌ 缺失 | P2：加入 SIGTERM/SIGUSR1 优雅终止信号处理 |
| 工具执行流水线 | Contract → Verification → Protocol | ✅ 已有 | 保持 |

### 2.2 CC 上下文压缩三级体系对 Scion ContextManager 的启示

**CC 的设计**（#04 全文、#05 全文、#06 §2-3、#07 全文）

CC 实现了三级上下文压缩，嵌入主循环：

```
Level 1: microCompact（不破坏 prompt cache，仅清除/压缩工具结果）
  ├── 时间触发（60min gap → cache 已冷，趁机清理）
  ├── Cached MC（cache_edit API，不修改本地消息）
  └── 无操作 fallback

Level 2: autoCompact（fork agent 生成 9 部分结构化摘要）
  ├── 触发阈值：effectiveContextWindow - 13K buffer ≈ 167K tokens（200K 窗口时）
  ├── 压缩后重建"状态恢复附件"（最多 5 文件 + 技能 + 工具声明 + 计划）
  └── 熔断器：连续 3 次失败后停止重试

Level 3: Blocking（硬阻断）
  └── 接近 context window 上限时拒绝新请求
```

关键工程细节：

- **消息分组以 API 轮次为边界**（不是用户消息边界），允许单用户消息的长 agentic session 细粒度压缩（#04 §3）
- **强制保留所有用户消息**：Compact prompt 第 6 条明确要求"保留所有非工具结果的用户消息"，防止意图漂移（#04 §4）
- **压缩后状态重建**（#04 §2）：compact 不是截断，是"换挡"——重建最近读取文件（50K token 预算）、技能（25K）、工具声明、计划文件、异步子任务状态
- **Token 估算三层机制**（#05 §3）：字符比例（最快最粗）→ 消息级结构化估算（4/3 保守系数）→ API 精确计数（最准最贵）
- **`tokenCountWithEstimation` 是权威函数**（#05 §3）：用最后一次 API usage 作基线，只估算增量，避免累积双重计算
- **工具结果两层防御**（#05 §4）：单条超限 → 持久化到磁盘 + 只传预览；聚合超预算 → 贪心选最大的外包。核心原则："**永远不截断，只外包到磁盘**"
- **Session Memory Compact**（#12 §4）：有结构化笔记时**零 LLM 调用**直接压缩，不依赖 LLM 摘要

**对 Scion ContextManager 的启示**：

| CC 机制 | Scion 适用性 | 优先级 |
|---|---|---|
| 分层阈值（warning/error/autocompact/blocking） | ✅ 适用。Scion 应区分"接近满"/"需要压缩"/"强制阻塞" | P1 |
| 熔断器（连续 N 次失败后停止） | ✅ 适用。Scion 的 LLM-in-the-loop 操作均需熔断 | P1 |
| 工具结果外包到磁盘 | ✅ 高度适用。Scion 的求解器输出可能数千行，应持久化全文 + prompt 只放摘要 | P1 |
| "永远不截断，只外包" | ✅ 核心原则。求解器完整输出存磁盘，上下文里只放关键结论 | P1 |
| SM Compact（零 LLM 调用的结构化压缩） | ✅ 高度适用。Scion 历史全是结构化数据，可直接模板渲染 | P1 |
| Prompt cache 前缀匹配优化 | ⚠️ 有限适用。Scion prompt 每轮变化大（experiment history），cache 命中率天然低 | P2 |
| forkedAgent 复用 parent cache | ❌ 不适用。Scion 无 fork 机制 | — |
| 对话级 LLM 摘要 | ❌ 不适用。Scion 历史是结构化的，模板渲染优于 LLM 摘要 | — |

### 2.3 CC 输出解析设计对 Scion ProposalEngine 的启示

**CC 的设计**（#08 全文、#11 §1-2）

CC 从不让 LLM 在 JSON 中返回代码内容。核心机制：

1. **tool_use content block**：代码作为 `tool_use.input` 的 JSON 字段值存在，JSON escape 由 Anthropic 服务端 constrained decoding 负责，不是 LLM 自由文本生成（#08 §1.1）
2. **SyntheticOutputTool**：需要结构化 JSON 时，注入一个 `StructuredOutput` tool 强制模型通过 tool_use 返回，走 constrained decoding 保证格式合法（#08 §1.3）
3. **Stop Hook 强制 Retry**：LLM 未调用 StructuredOutput tool 时，自动注入提示最多重试 5 次（#08 §1.4）
4. **Zod + AJV 双重校验**：tool 输入用 Zod schema，SyntheticOutputTool 用 AJV 验证自定义 JSON Schema，失败提供详细错误路径（#08 §1.5）

**Scion 的实际问题**（v0.1-tuning-report §2.3、v0.1.1-changelog §6.1）：

- 100+ 行 Python 代码嵌入 JSON 字符串，LLM 必须正确 escape 所有换行符、引号、反斜杠
- JSON 格式错误是 v0.1 早期 Proposal 失败的首要来源
- v0.1 tuning 修复后（tool_use 替代 JSON 文本解析），JSON 错误率从 ~10% 降到 0

**结论**：v0.1 tuning 已经按 CC 的 tool_use 方案（#08 方案 C）修复了此问题。v2 不需要再行动，但需确认当前实现完整覆盖了降级路径（tool_use 不可用时退回 XML 标签方案 A）。

### 2.4 CC 编排与元控制对 Scion Scheduler/Decision 的启示

**CC 的设计**（#09 全文、#13 全文）

1. **CC 没有独立的 meta agent 层**，采用基于状态机的编排 + 模式切换 + 持久化计划文件（#09 §1）
2. **Plan 系统**：EnterPlanModeTool 进入"只读探索"→ 用户审批 → bypass 执行（#09 §3）
3. **coordinatorMode prompt**（#13 §2）包含完整决策矩阵：
   - Research 覆盖了需修改的文件 → **Continue**（worker 已有文件上下文）
   - Research 广泛但实现范围窄 → **Spawn**（避免探索噪音污染实现）
   - 第一次实现用了错误方案 → **Spawn**（错误方案上下文会锚定重试）
4. **Synthesis 原则（反 lazy delegation）**（#13 §2.3）：coordinator 必须亲自理解 worker 结果并注入具体坐标，禁止"based on your findings"式的懒委托
5. **autoDream 三重门控**（#13 §4）：时间 + session 数量 + 分布式锁，防频繁触发
6. **verify.ts 独立验证原则**（#13 §6.2）：验证 worker 必须 spawn fresh，不继承实现者上下文

**对 Scion 的启示**：

| CC 机制 | Scion 对应 | 建议 |
|---|---|---|
| 状态机编排（无 meta agent） | branch 状态机 | ✅ 已有，设计一致 |
| Plan 模式（先规划再执行） | campaign 阶段切换 | P2：exploration → exploitation phase 切换 |
| coordinator Synthesis 原则 | CampaignManager 的 prompt 构建 | P1：验证结果应先"蒸馏"为结构化诊断再注入主 prompt |
| autoDream 三重门控 | 无等价机制 | P1：campaign 中期诊断（见 §5.9） |
| 独立验证原则 | VerificationGate | P1：验证 LLM 调用应使用独立上下文 |
| "错误方案会锚定重试" → spawn fresh | branch 迭代回退 | ✅ 已有（verification 未过回退到 clean 基线） |

### 2.5 CC Prompt Engineering 对 Scion prompt 的启示

**CC 的设计**（#10 全文）

1. **System prompt 模块化分层**（15+ section）：Static/Dynamic 分离，`SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 标记缓存切割点
2. **Tool description 极其详细**：300-4000 字/工具（Scion v0.1 之前只有 1 行/工具）
3. **"负面约束优先"**措辞策略：大量 "Don't" / "NEVER" / "CRITICAL"，告诉模型不要做什么
4. **先读后写四层防御**：Description → Description → Runtime → System Prompt
5. **代码质量哲学嵌入 system prompt**：YAGNI 原则、"三行重复代码好过一个提前抽象"、默认不加注释

**Scion v0.1 tuning 已实施的 CC 启发改进**（v0.1-tuning-report §3）：

| 修复编号 | 内容 | 来源 | 实施状态 |
|---|---|---|---|
| F9 | CC 风格 tool description（300-500 字/工具） | #10 §2 | ✅ 已实施 |
| F10 | System prompt 分层（static + champion 分块缓存） | #10 §4 | ✅ 已实施 |
| F11 | "先分析后提案"步骤 | #10 §3.3 | ✅ 已实施 |
| F12 | 代码质量负面约束 | #10 §3.2 | ✅ 已实施 |
| F13 | Schema field descriptions | #10 §2.3 | ✅ 已实施 |
| F14 | Cache stats 监控 | #10 §4.2 | ✅ 已实施 |

**尚未实施的建议**（cc-prompt-engineering-analysis §5）：

| 建议 | 优先级 | 状态 |
|---|---|---|
| Examples 加入 tool description（`<example>` blocks） | P2 | ❌ 未实施 |
| 输出风格约束（hypothesis_text 3-5 句） | P3 | ❌ 未实施 |
| 多层 cache_control（global/org/none） | P2 | ⚠️ 保持单层 ephemeral，但已加监控 |

---

## 3. Scion v0.1 实战问题清单

从 v0.1-completion-report、v0.1-tuning-report、v0.1.1-changelog、operator-quality-analysis、prompt-improvement-plan、postmortem #001、metrics-guide 中提取的所有已知问题。

### 3.1 问题汇总表

| # | 问题 | 来源文档 | 严重性 | v0.2 设计覆盖？ | CC 报告有解决方案？ |
|---|---|---|---|---|---|
| P01 | V5_state_leak 失败率 60-75%，根因是 uuid.uuid4() 不受 rng 控制 | postmortem #001 | 🔴 P0 | ✅ T01+T02 | ✅ #11 §5（BashTool 安全检查模式）、#14 §1.3（错误分类） |
| P02 | V5 诊断只返回 objective 差异，无失败分类，LLM 被误导 6 轮 | postmortem #001 §4 | 🔴 P0 | ✅ T02 | ✅ #14 §1.3（classifyAPIError 模式） |
| P03 | 字段名 bug：`order.subcategory` 不存在，正确是 `order.vehicle_subcategory` | operator-quality-analysis §B.1 | 🔴 P0 | ✅ prompt-improvement-plan Change 1 | ❌（CC 场景不同） |
| P04 | 缺目标函数公式，LLM 不知 splits 计算方式 | operator-quality-analysis §C.2 | 🔴 P0 | ✅ prompt-improvement-plan Change 2 | ❌ |
| P05 | max_tokens=4096 导致代码被截断 | v0.1-tuning-report §2.3 | 🔴 P0 | ✅ F4 已修（→16384） | ✅ #06 §3.2（max_output_tokens escalating retry） |
| P06 | code_content 嵌入 JSON 字符串导致格式错误 | v0.1.1-changelog §6.1 | 🔴 P0 | ✅ tool_use 已修 | ✅ #08 全文（tool_use 方案） |
| P07 | ContextManager 上下文真空（~300 tokens） | v0.1.1-changelog §1.1 | 🔴 P0 | ✅ v0.1.1 已修（→4500+ tokens） | ✅ #10（丰富 tool description 模式） |
| P08 | 新算子不被 Solver 加载（registry.yaml 未更新） | v0.1.1-changelog §1.3 | 🔴 P0 | ✅ v0.1.1 已修 | ❌ |
| P09 | Campaign 不存储实验历史 | v0.1.1-changelog §1.2 | 🔴 P0 | ✅ v0.1.1 已修 | ✅ #12（Session Memory 持续更新） |
| P10 | EXPLORE_EXPAND 状态机 bug | v0.1.1-changelog §1.4 | 🟠 P1 | ✅ v0.1.1 已修 | ❌ |
| P11 | compute_delta 只算 cost → splits 改善被 frozen CI 拒绝 | v0.1-tuning-report §2.2 | 🔴 P0 | ✅ F3 已修 | ❌ |
| P12 | 10/10 假设都是同族机制变体（subcategory consolidation） | operator-quality-analysis §A.1 | 🟠 P1 | ⚠️ T07/T08 覆盖 | ✅ #12 §2（记忆四分类学 + feedback 确认/纠正等价）、#13 §11.2（Synthesis 原则） |
| P13 | 缺 Greedy init 原理说明 | operator-quality-analysis §C.3 | 🟡 P1 | ✅ prompt-improvement-plan Change 3 | ❌ |
| P14 | 缺 VNS 动态说明 | operator-quality-analysis §C.4 | 🟡 P1 | ✅ prompt-improvement-plan Change 4 | ❌ |
| P15 | 缺 Worked Example | operator-quality-analysis §C.5 | 🟡 P1 | ✅ prompt-improvement-plan Change 5 | ❌ |
| P16 | LLM 使用 `list(set(...))` 引入非确定性 | v0.1-tuning-report §2.4 | 🟡 P1 | ✅ F7 已修（prompt 约束） | ✅ #10（负面约束优先模式） |
| P17 | medium_2 全 tie（退化 instance） | operator-quality-analysis §F.1 | 🟡 P1 | ✅ v2 instances 替换 | ❌ |
| P18 | Experiment feedback 不够清晰 | operator-quality-analysis §E | 🟡 P2 | ⚠️ T09/T10 覆盖 | ❌ |
| P19 | 不引导 LLM 使用 "modify" action | operator-quality-analysis §D.7 | 🟡 P2 | ⚠️ T08 覆盖 | ❌ |
| P20 | 上下文增长管理缺失 | v0.1.1-changelog §6.3 | 🟡 P2 | ⚠️ 部分由 8 轮窗口覆盖 | ✅ #04/#05/#07/#12（全套压缩体系） |
| P21 | UUID 在 import 白名单中，未被 ContractGate 拦截 | postmortem #001 §3.3 | 🟠 P1 | ⚠️ 已修（移除 uuid），但缺 AST 扫描 | ✅ #11 §5（bashSecurity 模式） |
| P22 | V5 诊断建议基于命名而非证据 | postmortem #001 §4.1 | 🟠 P1 | ⚠️ T02 部分覆盖 | ✅ #14 §1.3（errorDetails 存原始数据） |
| P23 | Proposal Engine 无降级恢复（hypothesis 成功但 code 失败时全部丢弃） | 推导自 v0.1 实验 | 🟠 P1 | ❌ 未覆盖 | ✅ #11 §2.3（AgentTool syncAgentError 部分结果恢复） |
| P24 | 缺少 Instance 统计上下文 | operator-quality-analysis §C.6 | 🟡 P2 | ❌ 未覆盖 | ❌ |
| P25 | 基线代码也有 uuid bug | postmortem #001 §3.2 | 🟠 P1 | ✅ 已修（commit b783cbb） | ❌ |
| P26 | 连续失败后缺乏框架/环境审查机制 | postmortem #001 §6 教训 3 | 🟠 P1 | ❌ 未覆盖 | ✅ #13 §11.5（stuck.ts 多维检测） |

### 3.2 关键数据

- **V5_state_leak 浪费**：v0.1 首轮 6/10 假设（60%），v0.2 Sprint D 6/8 假设（75%）。每次 V5 失败 ≈ $0.10-0.30 LLM + ~30s solver 双跑。6 轮误导迭代的总浪费远大于单次失败。
- **字段名 bug 影响**：5/7 生成算子使用 `order.subcategory`，所有 subcategory-targeting 逻辑变成死代码（operator-quality-analysis §B.1）
- **假设同质化**：10/10 = `create_new`，10/10 = `vehicle_level`，7/10 = subcategory consolidation 变体
- **tuning 修复效果**：从"从未 Promote"到"5 次连续成功 Promote"，Screening WR 0.75-0.81，Splits 改善 30-60%
- **v2 instance 效果**：20/20 通过区分度验证（≥2/3 seeds distinct）

---

## 4. 完整对照分析表

合并 v1 的 17 行 + 基于 #00-#10 和 v0.1 实战文档的新增发现。

| # | Scion 模块 | 实际问题（来自 v0.1 实战） | CC 对标设计 | 建议改进 | 优先级 | 来源 |
|---|---|---|---|---|---|---|
| 1 | ProposalEngine 序列化 | P06: code_content 嵌入 JSON 字符串，格式错误率 ~10% | #08 tool_use / #11 mapToolResultToToolResultBlockParam | ✅ 已修（tool_use）。确认降级路径（XML 标签方案 A）完整 | ✅ 已修 | #08, v0.1-tuning F6→tool_use |
| 2 | ProposalEngine 校验 | JSON 格式错误直接进入执行路径，无前置结构校验 | #11 §2.1 validateInput() | 增加 Pydantic 前置校验层；格式失败直接构造 tool_result 错误反馈 | **P0** | #11 v1-§2 |
| 3 | Verification V5 | P01+P02: V5 失败率 60-75%，诊断只有 objective 差异，LLM 被误导 6 轮 | #14 §1.3 classifyAPIError + #13 §11.5 stuck.ts | V5 失败分三类（ENV/CANDIDATE/UNKNOWN），提供 diff + 代码快照 + 定向建议 | **P0** | #14, postmortem #001 |
| 4 | Context Manager Hypothesis | P12: 10/10 假设同族变体，blacklist 只做文本去重 | #12 §2 记忆四分类学 + feedback 确认=纠正 | HypothesisFamily 机制标签 + 探索覆盖度报告 + 连续失败引导切换 | **P0** | #12, operator-quality-analysis |
| 5 | ProposalEngine 降级 | P23: code 失败时 hypothesis 也被丢弃 | #11 §2.3 AgentTool syncAgentError 部分结果恢复 | Code 失败时返回 hypothesis-only 结果让主循环决策 | **P0** | #11 |
| 6 | ContractGate | P21+P01: uuid 在白名单，uuid.uuid4() 是 V5 真实根因 | #11 §5 bashSecurity 危险 API 精确集合 | AST 扫描非 rng 随机源（uuid.uuid4/random/os.urandom 等） | **P0** | #11, postmortem #001 |
| 7 | ProposalEngine max_tokens | P05: 4096 截断代码 | #06 §3.2 max_output_tokens escalating retry（8K→64K） | ✅ 已修（→16384）。建议加入截断检测 + 自动升级 retry | ✅ 已修 | #06, v0.1-tuning F4 |
| 8 | Context Manager 数据模型 | P03+P04: 字段名不完整 + 缺目标函数公式 | #10 §2（tool description 极其详细）、#10 §3.3（先读后分析） | ✅ 已修（F1/F2）。保持完整 Order 14 字段 + 目标函数公式 | ✅ 已修 | #10, prompt-improvement-plan |
| 9 | Context Manager 结构理解 | P13+P14+P15: 缺 greedy init/VNS 动态/worked example | #10 §2.1（BashTool 4000 字 description 含完整上下文） | ✅ 已修（F5/F6）。保持 greedy init + VNS 动态 + worked example 在 prompt 中 | ✅ 已修 | #10, prompt-improvement-plan |
| 10 | LLM Client 重试 | 无 query source 分级，后台/前台共用重试配额 | #14 §1.2 QuerySource 分级（后台 529 立即放弃） | 前台（campaign 主循环）/ 后台（诊断/摘要）分级重试 | P1 | #14 v1-§4.1 |
| 11 | LLM Client 错误可见性 | API 错误不注入对话历史，模型无法感知 | #14 §1.3 getAssistantMessageFromError | API error 构造为 tool_result(is_error=true) 反馈给模型 | P1 | #14 v1-§4.2 |
| 12 | Campaign 压缩 | P20: 上下文随轮次线性膨胀 | #12 §4 SM Compact（零 LLM 调用结构化压缩） | 用已有 HypothesisRecord/VerificationResult 做结构化渲染压缩 | P1 | #12 v1-§4.3 |
| 13 | Scheduler 停滞检测 | P26: 只有 consecutive_fully_abandoned_branches 单一指标 | #14 §2.3 Token Budget 边际收益 + #13 §11.5 stuck.ts 多维 | StagnationDetector：oscillation/plateau/collapse/timeout_cascade | P1 | #14, #13 |
| 14 | Verification 独立性 | 验证与实验共享上下文，验证者可能被锚定 | #13 §6.2 verify.ts spawn fresh + "prove not confirm" | VerificationGate LLM 调用使用独立上下文 | P1 | #13 v1-§4.5 |
| 15 | ContractGate AST 深度 | 只检查 import，不检查调用模式 | #11 §5.2 bashSecurity 多层防御（静态分析→权限→sandbox） | 从"import 白名单"扩展为"调用模式分析" | P1 | #11 v1-§4.6 |
| 16 | Lineage 完整性 | campaign_summary 缺少 protocol_result/code_content/verification_detail | #14 §5 SessionHistory + AppState（完整状态+symlink） | 扩展 campaign_summary 为研究级 artifact | P1 | #14 v1-§4.7 |
| 17 | Decision Engine 预算 | BudgetState 无安全阈值，用满才终止 | #14 §2 COMPLETION_THRESHOLD=0.9 + nudge message | 90% 安全阈值 + 无进展时 nudge "请换方向" | P1 | #14 v1-§4.8 |
| 18 | Campaign 中期诊断 | P26: 连续失败缺乏框架/环境审查 | #13 §4 autoDream 三重门控 | 三重条件触发 Opus 级诊断注入 | P1 | #13 v1-§4.9 |
| 19 | Campaign 后分析 | postmortem #001 教训 1："设计了追溯但从未追溯" | #13 §6.2 verify.ts 证伪文化 | `scion postmortem` CLI 命令：自动抽样+代码级根因模板 | P1 | #13, postmortem #001 |
| 20 | Context Manager 检索指引 | 压缩后无"如何找回被压缩详细记录"指引 | #12 §8 "Searching past context" grep 指令 | 压缩后注入 artifact 路径检索指引 | P2 | #12 v1-§4.14 |
| 21 | Experiment Protocol 去抖 | 边界值结果立即采信 | #13 §11.6 RemoteAgentTask 稳定空闲检测（连续 5 次 idle） | 边界值结果去抖：连续 2 次验证通过才 promote | P2 | #13 v1-§4.13 |
| 22 | Campaign fire-and-forget | 无后台任务隔离 | #14 §4 Stop Hooks fire-and-forget | 后台类任务（记忆提取/中期诊断）与主循环显式解耦 | P2 | #14 v1-§4.12 |
| 23 | Tool Description Examples | 无 `<example>` blocks | #10 §1.4 AgentTool XML examples | 至少为 PATCH_TOOL 添加一个完整算子示例 | P2 | #10, cc-prompt-analysis |
| 24 | 输出风格约束 | hypothesis_text 有时过于冗长 | #10 §2.3 Schema description 中加长度提示 | field description 加 "3-5 sentences" 约束 | P3 | #10, cc-prompt-analysis |
| 25 | Context Manager 记忆类型 | 无封闭分类学，blacklist 是文本列表 | #12 §2 记忆四分类学（user/feedback/project/reference） | hypothesis memory 按 hypothesis/constraint/failure_pattern/benchmark 四类存储 | P1 | #12 |
| 26 | Context Manager 正向记录 | 只记失败，不记"什么策略被验证有效" | #12 §2.2 feedback "确认"等同"纠正"防过度保守 | failure_pattern 同时记"什么有效"（哪个参数组合带来 promote） | P1 | #12 |
| 27 | 主循环截断恢复 | 无 max_output_tokens 截断检测 | #02 §3.1（截断时自动注入续写提示，最多 3 次） + #06 §3（8K→64K escalating） | 检测 LLM 输出截断 + 自动注入续写/升级 max_tokens | P1 | #02, #06 |

---

## 5. P0 改进详述

### 5.1 P0-1：ProposalEngine — Pydantic 前置校验层

**v0.1 实战证据**：v0.1.1-changelog §6.1 记录 JSON 格式频繁失败。虽然 tool_use 修复了 code_content 嵌套问题，但 tool_use 返回的 dict 仍可能缺少 required 字段或类型不匹配。

**CC 的具体设计**（#11 §2.1）：CC 的 `validateInput()` 在 `call()` 之前、无副作用地校验 schema，失败返回 `{result:false, message, errorCode}`。模型看到错误后自行修正，无需框架层重试。

**建议实现**：

```python
def validate_proposal(raw: dict) -> ValidationResult:
    try:
        parsed = PatchProposalSchema.model_validate(raw)
        return ValidationResult(ok=True, value=parsed)
    except ValidationError as e:
        return ValidationResult(
            ok=False,
            error=f"Proposal format error: {e}. Required: file_path(str), action(str), code_content(str)"
        )
```

格式失败直接构造 `tool_result(is_error=true)` 反馈给模型，不进执行路径。

**预期收益**：非格式问题不进 Contract/Verification 流水线，节省下游验证开销。

### 5.2 P0-2：Verification Gate V5 — 诊断分类与代码级根因

**v0.1 实战证据**：Postmortem #001 详细记录：V5 失败率 60-75%，6 轮迭代中 LLM 被错误 suggestion（"ensure deepcopy"）引向不存在的问题（mutation），真实根因是 uuid.uuid4()。诊断信号没有帮助 LLM 定位根因，反而产生了系统性误导。

**CC 的具体设计**（#14 §1.3）：`classifyAPIError()` 将所有 error 规范化为 string tag，与处理逻辑解耦。`errorDetails` 存储原始数据供下游精确处理。

**建议实现**：

```python
@dataclass
class V5FailureDetail:
    category: Literal["ENV_NONDETERMINISM", "CANDIDATE_NONDETERMINISM", "UNKNOWN"]
    run1_objective: tuple
    run2_objective: tuple
    run1_output_path: str
    run2_output_path: str
    code_snapshot_path: str
    suggested_fix: str  # 基于 category 的定向建议

V5_SUGGESTIONS = {
    "ENV_NONDETERMINISM": "非确定性来自运行环境。检查 uuid.uuid4()、os.urandom() 等。修复：使用 generate_vehicle_id(rng)。",
    "CANDIDATE_NONDETERMINISM": "非确定性来自候选代码。检查 set 迭代顺序、未通过 rng 的随机调用。修复：sorted() + rng 参数。",
}

def classify_v5(candidate_code: str) -> str:
    if "uuid.uuid4()" in candidate_code or "os.urandom" in candidate_code:
        return "CANDIDATE_NONDETERMINISM"
    if re.search(r'list\(set\(', candidate_code):
        return "CANDIDATE_NONDETERMINISM"
    return "UNKNOWN"
```

**预期收益**：Postmortem #001 的 6 轮误导浪费可在第 1-2 次失败时被截断。直接提升实验预算利用率。

**与 v0.2 T02 的关系**：T02 已规划 V5 诊断增强，本方案为 T02 的具体实现指导，增加了 category 分类维度。

### 5.3 P0-3：Context Manager — HypothesisFamily Tracking + 策略切换引导

**v0.1 实战证据**：operator-quality-analysis §A.1 记录 10/10 假设都是 `create_new + vehicle_level + subcategory consolidation` 变体。v0.1-tuning-report 确认修复后效果大幅改善，但机制层去重仍缺失。

**CC 的具体设计**（#12 §2）：CC 将记忆约束在 4 个封闭类型，核心原则是"只存储无法从当前状态推导的内容"。**feedback 类型明确要求保存"用户的确认"等同保存"纠正"**，防模型只记错误从而变得过度保守。

CC coordinator 的 "Continue vs. Spawn" 决策框架（#13 §2.3）核心原则：**当前上下文的失败经验会锚定后续尝试**，应在必要时 spawn fresh。

**建议实现**：

```python
@dataclass
class HypothesisFamily:
    family_id: str
    mechanism_label: str      # "subcategory_consolidation", "destroy_rebuild", ...
    action_pattern: str       # "create_new" / "modify" / "remove"
    locus_pattern: str        # "vehicle_level" / "order_level"
    evidence_count: int
    statuses: list[str]       # ["rejected", "rejected", "borderline", "promoted"]
    
def build_exploration_coverage(families: list[HypothesisFamily]) -> str:
    """注入 hypothesis 生成 prompt 的探索覆盖度报告"""
    # 1. 列出各 action/locus 分布
    # 2. 标注连续3次失败的族 → "建议切换方向"
    # 3. 列出未探索的 locus → 主动提示
    # 4. 记录有效策略（CC 的"确认=纠正"原则）→ 防过度保守
```

**预期收益**：v0.1 中 70%+ 实验预算用于同族机制变体。覆盖度引导可直接提高"每单位 LLM 调用产出新信息"的比率。

**与 v0.2 T07/T08 的关系**：T07（family tracking）和 T08（strategy-shift guidance）与本方案完全对齐。本方案提供了 CC 设计根据（记忆四分类学 + feedback 确认等同纠正），并补充了 Coverage Reporting 的具体实现。

### 5.4 P0-4：ProposalEngine — Hypothesis 成功但 Code 失败时的降级恢复

**v0.1 实战证据**：v0.1 早期 4/8 轮 code_content 失败（v0.1-tuning-report §5），每次失败丢弃整个 Proposal（含已成功的 hypothesis）。

**CC 的具体设计**（#11 §2.3）：AgentTool 的 sync 执行路径在 catch 块中：有部分 assistant 消息时返回已有内容而非抛错。核心原则："有内容就返回有内容的，部分完成优于完全失败"。

**建议实现**：

```python
class ProposalEngine:
    async def generate_proposal(self, branch_context) -> ProposalResult:
        hypothesis = await self._run_hypothesis_round(branch_context)
        if hypothesis is None:
            return ProposalResult(status="hypothesis_failed")
        try:
            patch = await self._run_code_round(branch_context, hypothesis)
            return ProposalResult(status="complete", hypothesis=hypothesis, patch=patch)
        except ProposalCodeError as e:
            return ProposalResult(status="hypothesis_only", hypothesis=hypothesis, code_error=str(e))
```

主循环对 `hypothesis_only` 状态的处理选项：复用已生成 hypothesis 重试 code round / 记录 hypothesis 供后续分支复用。

**预期收益**：高质量 hypothesis 不因 code 格式错误被丢弃。

### 5.5 P0-5：ContractGate — 非 rng 随机源 AST 扫描

**v0.1 实战证据**：Postmortem #001 §3.3 明确记录 uuid 在 import 白名单中未被拦截，是 V5 失败的真实根因。commit b783cbb 已从白名单移除 uuid 并修复基线算子，但缺少 AST 层面的动态检测。

**CC 的具体设计**（#11 §5）：`bashSecurity.ts` 维护精确的危险 API 集合（ZSH_DANGEROUS_COMMANDS），检测不仅基于 import 还基于调用模式。

**建议实现**：

```python
NON_RNG_RANDOM_CALLS = {
    "uuid.uuid4", "uuid.uuid1", "random.random", "random.randint",
    "random.choice", "random.sample", "os.urandom", "secrets.token_bytes",
}

def check_non_rng_randomness(code: str) -> list[ContractViolation]:
    tree = ast.parse(code)
    violations = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            call_name = get_full_call_name(node)
            if call_name in NON_RNG_RANDOM_CALLS:
                violations.append(ContractViolation(
                    type="non_rng_randomness", line=node.lineno,
                    message=f"'{call_name}' bypasses rng. Use rng parameter or generate_vehicle_id(rng).",
                ))
    return violations
```

**预期收益**：从源头拦截 V5 真实根因。若此检测已上线，Postmortem #001 的 6 轮失败可在第 1 次 Contract 检查时截断。

---

## 6. P1 改进清单

以下改进按 v0.1 实战影响排序。保留 v1 的 10 个 + 新增 6 个。

| # | 改进 | 对应问题 | 实现要点 | 来源 |
|---|---|---|---|---|
| P1-1 | LLM Client 查询来源分级重试 | — | 前台（campaign）/后台（诊断/摘要）分级，后台 429/529 立即放弃 | #14 §1.2 |
| P1-2 | LLM Client API 错误注入对话历史 | — | error → tool_result(is_error=true) 让模型感知错误后自主修正 | #14 §1.3 |
| P1-3 | Campaign 基于结构化记录的零 LLM 压缩 | P20 | HypothesisRecord → Markdown 表，failure_pattern → bullet list，不调用 LLM | #12 §4 |
| P1-4 | Scheduler 多维停滞检测 | P26 | StagnationDetector：oscillation/plateau/collapse/timeout_cascade | #14 §2.3, #13 §11.5 |
| P1-5 | Verification Gate 独立验证上下文 | — | VerificationGate LLM 调用使用独立上下文，不传入实验生成 messages | #13 §6.2 |
| P1-6 | ContractGate AST 调用模式分析 | P21 | 从"import 白名单"扩展为"调用模式分析"（补充 P0-5 的深度） | #11 §5.2 |
| P1-7 | Lineage Registry 完整 Campaign Artifact | — | campaign_summary 加入 protocol_result、case_feedback、code_archive_ref、verification_detail | #14 §5 |
| P1-8 | Decision Engine 预算安全阈值 + nudge | — | 90% 阈值 + 无进展时注入"请换方向"nudge message | #14 §2 |
| P1-9 | Campaign 中期停滞诊断 | P26 | 三重条件（verify fail ≥3 / 过半轮次无 promote / 预算 ≥50%）触发 Opus 诊断 | #13 §4 |
| P1-10 | Campaign 后分析 CLI | postmortem #001 教训 1 | `scion postmortem` 命令：失败模式自动抽样+代码级根因模板 | #13 §6.2 |
| **P1-11** | **Context Manager 记忆分类学** | P12 | hypothesis memory 按 hypothesis/constraint/failure_pattern/benchmark 四类存储 | #12 §2（新增） |
| **P1-12** | **Context Manager 正向记录** | P12 | failure_pattern 同时记"什么有效"（哪个策略带来 promote），防过度保守 | #12 §2.2（新增） |
| **P1-13** | **主循环截断恢复** | P05 | 检测 LLM 输出 stop_reason=max_tokens → 自动升级 max_tokens 重试（CC 8K→64K 模式） | #02 §3.1, #06 §3.2（新增） |
| **P1-14** | **工具结果外包到磁盘** | P20 | 求解器输出超过阈值时持久化全文到磁盘，prompt 只放摘要+路径 | #05 §4（新增） |
| **P1-15** | **Token 预算分层管理** | P20 | 先分配固定区（problem spec + interface spec），再分配动态区（champion code + history） | #06 §6.5（新增） |
| **P1-16** | **熔断器模式** | — | 任何 LLM-in-the-loop 操作连续失败 N 次后停止重试，避免 API 浪费 | #04 §7.2（新增） |

---

## 7. 不建议引入的 CC 设计

保留 v1 的 7 个 + 新增 5 个。

| # | CC 设计 | 为什么不适用于 Scion | 来源 |
|---|---|---|---|
| 1 | TUI 实时进度（AgentSummary，每 30s 一次） | Scion 实验以分钟计，秒级 UI 更新浪费成本。用结构化 log + SQLite 即可。 | #12 §6 |
| 2 | PromptSuggestion 投机预执行 | Scion 是无人值守自动化，没有"用户下一步输入"概念。 | #14 §7 |
| 3 | toolUseSummary（Haiku 生成移动端摘要） | Scion 没有移动端 UI。 | #12 §7 |
| 4 | RemoteAgentTask 云端 CCR Session | Scion 计算在本地/集群。 | #13 §1.2 |
| 5 | /loop cron 循环调度 | Scion 有自己的 Campaign 主循环。 | #13 §7 |
| 6 | MagicDocs 自动文档更新 | Scion 组件文档由人工维护更合适。但可在 Scion 开发环境中使用 CC 的 MagicDocs。 | #14 §6 |
| 7 | sessionMemoryCompact 的 minTextBlockMessages=5 | Scion 上下文不是对话消息，需基于"最少保留 N 轮完整实验"重新定义。 | #12 §4.3 |
| **8** | **forkedAgent 路径（复用 prompt cache prefix）** | Scion 无 fork agent 机制，且每轮 prompt 变化大，cache 命中率天然低。 | #04 §2 |
| **9** | **Cached MC（cache_edit API）** | Anthropic 内部特性，外部构建不可用。 | #05 §1 |
| **10** | **GrowthBook 远程配置** | Scion 单一部署，硬编码阈值更简单可控。 | #05 §5 |
| **11** | **消息配对保护（tool_use/tool_result 不拆散）** | Scion 不是对话格式，无 tool_use/tool_result 配对问题。 | #12 §4.4 |
| **12** | **YOLO 分类器（独立 LLM 做安全裁判）** | Scion 不需要权限检查机制。 | #00 §三 |

---

## 8. 已有 CC→Scion 改进的交叉验证

`cc-prompt-engineering-analysis.md`（即 CC 报告 #10 的 Scion 版本）在 v0.1 调优阶段已给出 7 项改进建议。以下对照其实施状态，并与本文档建议的重叠/冲突分析。

### 8.1 已实施的建议

| cc-prompt-analysis 建议 | 对应 Scion 修复 | 实施日期 | 效果验证 |
|---|---|---|---|
| P0-1: 丰富 tool description（300-500 字） | F9 | 2026-04-08 | ✅ v0.1-tuning-report：配合其他修复后 WR 0.75-0.81 |
| P0-2: 代码质量负面约束 | F12 | 2026-04-08 | ✅ 更简洁可靠的代码 |
| P1-1: System prompt 分层（static + champion 分块缓存） | F10 | 2026-04-08 | ✅ Cache hit rate 33%（首轮 create 拉低平均值，R2+ 完美 hit） |
| P1-2: "先分析后提案"步骤 | F11 | 2026-04-08 | ✅ 减少重复 hypothesis |
| P2-1: Cache stats 监控 | F14 | 2026-04-08 | ✅ 可观测性改善 |
| P2-2: Schema field descriptions | F13 | 2026-04-08 | ✅ 控制输出质量 |

### 8.2 未实施的建议

| cc-prompt-analysis 建议 | 状态 | 本文档对应 | 建议 |
|---|---|---|---|
| P2-2: Examples 加入 tool description | ❌ 未实施 | §4 #23（P2） | 建议在 Sprint E 实施 |
| P3: 输出风格约束（hypothesis_text 3-5 句） | ❌ 未实施 | §4 #24（P3） | 低优先级，可选 |

### 8.3 本文档与 cc-prompt-analysis 的差异

cc-prompt-analysis 聚焦 prompt 工程（工具描述、system prompt 分层、cache 策略），本文档覆盖范围更广：

1. **本文档新增**：V5 诊断分类（P0-2）、HypothesisFamily tracking（P0-3）、降级恢复（P0-4）、AST 随机源扫描（P0-5）、停滞检测（P1-4）、中期诊断（P1-9）、记忆分类学（P1-11）、工具结果外包（P1-14）
2. **cc-prompt-analysis 已覆盖但本文档扩展**：tool description（cc-prompt 仅建议丰富文本，本文档补充降级恢复和前置校验的工程机制）
3. **无冲突**：两份文档的建议完全兼容

### 8.4 prompt-improvement-plan 的交叉验证

prompt-improvement-plan（operator-quality-analysis 的配套文档）给出 8 项具体 prompt 修改：

| Change | 内容 | 实施状态 | 效果 |
|---|---|---|---|
| 1 | 完整 Order 14 字段列表 | ✅ F1 | 消灭字段名 bug |
| 2 | 目标函数公式 | ✅ F2 | LLM 理解优化目标 |
| 3 | Greedy init 原理 | ✅ F5 | LLM 理解 splits 来源 |
| 4 | VNS 动态说明 | ✅ F6 | LLM 设计高方差算子 |
| 5 | Worked example | ✅ F5 | 具体理解解结构 |
| 6 | 引导 "modify" action | ⚠️ T08 覆盖 | Sprint E 实施 |
| 7 | 改进 feedback 清晰度 | ⚠️ T09 覆盖 | Sprint E 实施 |
| 8 | Champion baseline 值注入 | ⚠️ T10 覆盖 | Sprint E 实施 |

---

## 9. Sprint E 重构建议

### 9.1 基于完整分析的 Sprint E Task 清单

Sprint E 在 v0.2-development-plan 中定义为"Search-efficiency polish"，原计划任务为 T05-T11 + T15b + T17b。基于本文档的完整分析，建议以下调整：

#### 保留的原 Sprint E 任务

| 原任务 | 内容 | 调整 |
|---|---|---|
| T05 | Frozen expansion | 保留，无变更 |
| T06 | Observability polish | 保留，融入 P1-7（Lineage 完整性） |
| T07 | Family tracking | 保留，按 §5.3（P0-3）实现 HypothesisFamily |
| T08 | Strategy guidance | 保留，按 §5.3 的 Coverage Reporting 实现 |
| T09 | Richer case feedback wording | 保留，融入 prompt-improvement-plan Change 7 |
| T10 | Champion baseline hints | 保留，融入 prompt-improvement-plan Change 8 |
| T11 | Screening rebalance | 保留，无变更 |
| T15b | Bayesian optimizer | 保留，但优先级降低（依赖 Sprint D 验证） |
| T17b | CLI/report polish | 保留，融入 P1-10（postmortem CLI） |

#### 新增的 Sprint E 任务

| 新任务 | 内容 | 对应改进 | 优先级 |
|---|---|---|---|
| **T19** | ProposalEngine 前置校验层（Pydantic validateInput） | P0-1 | **P0** |
| **T20** | ProposalEngine 降级恢复（hypothesis-only 结果） | P0-4 | **P0** |
| **T21** | ContractGate AST 非 rng 随机源扫描 | P0-5 | **P0** |
| **T22** | LLM Client 查询来源分级重试 | P1-1 | P1 |
| **T23** | Campaign 中期停滞诊断（三重门控 + Opus 诊断） | P1-9 | P1 |
| **T24** | `scion postmortem` CLI 命令 | P1-10 | P1 |
| **T25** | StagnationDetector 多维停滞检测 | P1-4 | P1 |
| **T26** | Context Manager 记忆分类学 + 正向记录 | P1-11 + P1-12 | P1 |
| **T27** | 主循环 max_tokens 截断恢复 | P1-13 | P1 |
| **T28** | 工具结果外包到磁盘 | P1-14 | P1 |
| **T29** | 熔断器模式（LLM-in-the-loop 连续失败保护） | P1-16 | P1 |

### 9.2 与原 Sprint E 设计的对比

| 维度 | 原 Sprint E（v0.2-development-plan §6） | 本文档建议 |
|---|---|---|
| 任务数量 | 9 个（T05-T11 + T15b + T17b） | 9 保留 + 11 新增 = 20 个 |
| 核心关注 | benchmark 结构 + outer-loop 质量 + optimizer | + 错误链路修复 + 健壮性 + 记忆治理 |
| P0 任务 | 0 个 | 3 个（T19/T20/T21） |
| 新增工程基础 | 无 | T22 分级重试、T25 停滞检测、T29 熔断器 |
| 新增分析工具 | 无 | T23 中期诊断、T24 postmortem CLI |

### 9.3 建议执行顺序和依赖关系

```
Phase E1（P0 — 错误链路修复）：
  T19（前置校验） → T20（降级恢复） → T21（AST 扫描）
  依赖：无。可立即开始。
  预期：Proposal 成功率 +10-15%，Contract 拦截覆盖率提升

Phase E2（Search Efficiency — 核心）：
  T07（Family tracking）→ T08（Strategy guidance）→ T26（记忆分类 + 正向记录）
  T05（Frozen expansion）+ T11（Screening rebalance）— 可并行
  依赖：T07 是 T08 和 T26 的基础。
  预期：假设多样性提升，同族重复率下降

Phase E3（Feedback + 可观测性）：
  T09（Feedback wording）+ T10（Baseline hints）+ T06（Observability）
  T23（中期诊断）+ T24（postmortem CLI）+ T25（StagnationDetector）
  依赖：T06 融入 P1-7 需要 Sprint A 的 T03/T04 完成。
  预期：诊断能力和事后分析能力大幅提升

Phase E4（工程健壮性）：
  T22（分级重试）+ T27（截断恢复）+ T28（工具结果外包）+ T29（熔断器）
  依赖：无。可随时穿插。
  预期：框架健壮性提升，边界情况处理完善

Phase E5（高级搜索）：
  T15b（Bayesian optimizer）+ T17b（CLI polish）
  依赖：Sprint D 的参数搜索验证结果。
  预期：参数搜索效率提升（需 Sprint D 证明 random/local 不够用）
```

```
依赖关系图：

T19 ──→ T20 ──→ （可立即做）
T21 ──→ （可立即做）
T07 ──→ T08 ──→ T26
T05 ──╮
T11 ──┤──→ （并行，独立于 E1）
T09 ──╮
T10 ──┤──→ （可并行）
T06 ──╯
T23 ──→ （依赖 T25 的 StagnationDetector）
T24 ──→ （依赖 T03/T04 的 artifact 完整性）
T25 ──→ T23
T22, T27, T28, T29 ──→ （独立，可随时做）
T15b ──→ （依赖 Sprint D）
T17b ──→ T24
```

---

## 10. 与 v0.2 任务的完整对应关系

### 10.1 融入现有 v0.2 任务的改进

| 改进点 | 融入的 v0.2 任务 | 融入方式 |
|---|---|---|
| P0-2（V5 分类 + 代码级诊断） | **T02** | T02 输出 schema 采用 V5FailureDetail；category 分类覆盖 T01 验证 |
| P0-5（ContractGate AST 扫描） | **T01** 补充 | T01 修环境，P0-5 修合同层，联合解决 uuid 问题 |
| P0-3（HypothesisFamily） | **T07 + T08** | T07 数据结构 = HypothesisFamily，T08 基于 Coverage Reporting |
| P1-2（API 错误历史注入） | **T09** 部分 | T09 关注 case feedback，可一并处理 LLM 可见性 |
| P1-7（Lineage 完整性） | **T03 + T04** | T03/T04 的字段与 P1-7 完全吻合 |
| P1-8（Budget 安全阈值） | **T06** | 作为 observability 字段纳入 |

### 10.2 新增任务完整清单（非 Sprint E 部分已在 v1 §6 中定义）

Sprint E 新增任务见 §9.1。其余改进自然融入现有 Sprint A-D 任务，无需额外新建任务。

### 10.3 v0.2 全 Sprint 任务总览

```
Sprint A（Foundation）: T01, T02, T03, T04 [+ P0-5 融入 T01]
Sprint B（Parameter plumbing）: T12, T13, T14
Sprint C（Parameter close loop）: T15a, T16, T17a
Sprint D（First proof）: T18

Sprint E（Search-efficiency polish — 扩展版）:
  E1: T19, T20, T21                    ← P0 新增
  E2: T05, T07, T08, T11, T26         ← 原有 + 新增
  E3: T06, T09, T10, T23, T24, T25    ← 原有 + 新增
  E4: T22, T27, T28, T29              ← 新增工程健壮性
  E5: T15b, T17b                      ← 原有
```

---

## 附录 A：关键常量参考（CC 源码）

以下常量来自 CC 源码，在 Scion 设计中可作为参考值：

```
# autoCompact 触发
AUTOCOMPACT_BUFFER_TOKENS = 13,000
MAX_CONSECUTIVE_AUTOCOMPACT_FAILURES = 3  ← Scion 熔断器参考值
WARNING_THRESHOLD_BUFFER_TOKENS = 20,000
MANUAL_COMPACT_BUFFER_TOKENS = 3,000

# Token 估算
bytesPerToken = 4（通用），2（JSON）
estimateMessageTokens 保守系数 = 4/3

# 工具结果
DEFAULT_MAX_RESULT_SIZE_CHARS = 50,000  ← Scion 求解器输出外包阈值参考
POST_COMPACT_TOKEN_BUDGET = 50,000
POST_COMPACT_MAX_FILES = 5
PREVIEW_SIZE_BYTES = 2,000

# Session Memory
MAX_SECTION_LENGTH = 2,000 tokens
MAX_TOTAL_SESSION_MEMORY_TOKENS = 12,000

# Token Budget
COMPLETION_THRESHOLD = 0.9  ← Scion Budget 安全阈值参考
DIMINISHING_THRESHOLD = 500  ← 边际收益递减检测阈值

# API 重试
DEFAULT_MAX_RETRIES = 10
MAX_529_RETRIES = 3
BASE_DELAY_MS = 500
MAX_OUTPUT_TOKENS_RECOVERY_LIMIT = 3  ← 截断恢复最多次数
CAPPED_DEFAULT_MAX_TOKENS = 8,000
ESCALATED_MAX_TOKENS = 64,000

# 记忆
MAX_ENTRYPOINT_LINES = 200
MAX_ENTRYPOINT_BYTES = 25,000
SUMMARY_INTERVAL_MS = 30,000（AgentSummary）

# SyntheticOutputTool
MAX_STRUCTURED_OUTPUT_RETRIES = 5
```

## 附录 B：文档引用索引

| 缩写 | 完整路径 |
|---|---|
| #00 | ~/research/claude-code-src/analysis/00-summary.md |
| #01 | ~/research/claude-code-src/analysis/01-overall-architecture.md |
| #02 | ~/research/claude-code-src/analysis/02-query-engine.md |
| #03 | ~/research/claude-code-src/analysis/03-cc-vs-opencode.md |
| #04 | ~/research/claude-code-src/analysis/04-compact-core.md |
| #05 | ~/research/claude-code-src/analysis/05-microcompact-token.md |
| #06 | ~/research/claude-code-src/analysis/06-query-context-management.md |
| #07 | ~/research/claude-code-src/analysis/07-comprehensive-context-management.md |
| #08 | ~/research/claude-code-src/analysis/08-output-parsing-design.md |
| #09 | ~/research/claude-code-src/analysis/09-orchestration-and-meta-control.md |
| #10 | ~/research/claude-code-src/analysis/10-prompt-engineering.md |
| #11 | ~/research/claude-code-src/analysis/11-tool-system.md |
| #12 | ~/research/claude-code-src/analysis/12-memory-and-compact-deep.md |
| #13 | ~/research/claude-code-src/analysis/13-tasks-and-coordination.md |
| #14 | ~/research/claude-code-src/analysis/14-services-core.md |
| #15 | ~/research/claude-code-src/analysis/15-commands-hooks-state.md |
| v0.1-completion | ~/research/or-autoresearch-agent/scion/docs/v0.1-completion-report.md |
| v0.1-tuning | ~/research/or-autoresearch-agent/scion/docs/v0.1-tuning-report.md |
| v0.1.1-changelog | ~/research/or-autoresearch-agent/scion/docs/v0.1.1-changelog.md |
| operator-quality | ~/research/or-autoresearch-agent/scion/docs/operator-quality-analysis.md |
| prompt-improvement | ~/research/or-autoresearch-agent/scion/docs/prompt-improvement-plan.md |
| cc-prompt-analysis | ~/research/or-autoresearch-agent/scion/docs/cc-prompt-engineering-analysis.md |
| metrics-guide | ~/research/or-autoresearch-agent/scion/docs/metrics-guide.md |
| postmortem #001 | ~/research/or-autoresearch-agent/scion/postmortem/001-v5-uuid-nondeterminism.md |
| arch-v3 | ~/research/or-autoresearch-agent/design/scion-architecture-v3.md |
| eng-arch-v1 | ~/research/or-autoresearch-agent/design/scion-engineering-arch-v1.md |
| v0.1-design | ~/research/or-autoresearch-agent/design/scion-v0.1-design.md |
| v0.2-design | ~/research/or-autoresearch-agent/scion/design/scion-v0.2-design.md |
| v0.2-detailed | ~/research/or-autoresearch-agent/scion/design/scion-v0.2-detailed-design.md |
| v0.2-devplan | ~/research/or-autoresearch-agent/scion/design/scion-v0.2-development-plan.md |
| v1-reference | ~/research/or-autoresearch-agent/scion/design/cc-design-reference.md |

---

*本文档基于 16 份 CC 源码分析报告、7 份 Scion v0.1 实战文档、1 份 Postmortem、6 份 Scion 架构/设计文档、以及 v1 参考文档撰写。所有改进建议均有来源文档引用和实战数据支撑。v1 中已有的好内容已保留并标注来源。*

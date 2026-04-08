# Claude Code Prompt Engineering Analysis — Scion 改进建议

> 分析基于 `~/research/claude-code-src/` (instructkr/claude-code 泄露版)
> 
> 日期: 2026-04-08

---

## 目录

1. [System Prompt 设计](#1-system-prompt-设计)
2. [Tool Description 设计](#2-tool-description-设计)
3. [Code Generation 相关 Prompt](#3-code-generation-相关-prompt)
4. [Context Window Management](#4-context-window-management)
5. [对 Scion 的改进建议](#5-对-scion-的改进建议)

---

## 1. System Prompt 设计

### 1.1 整体架构：模块化分层

CC 的 system prompt 并非单一字符串，而是一个 **`string[]` 数组**，每个元素对应一个独立的"section"。最终由 `getSystemPrompt()` (in `src/constants/prompts.ts`) 组装。

**关键发现**：CC 使用了一个 `SystemPrompt` branded type（`src/utils/systemPromptType.ts`），本质是 `readonly string[]`，在发送到 API 时才 join 为多个 text block。

#### 分层结构（从上到下）

```
[Static / Cacheable 部分]
├── 1. Identity + Intro（角色定义 + 安全指令）
│     └── getSimpleIntroSection()
├── 2. System Rules（输出格式、权限模式、hooks）
│     └── getSimpleSystemSection()
├── 3. Doing Tasks（代码任务核心指令）
│     └── getSimpleDoingTasksSection()
├── 4. Executing Actions with Care（可逆性/影响半径）
│     └── getActionsSection()
├── 5. Using Your Tools（工具使用偏好）
│     └── getUsingYourToolsSection()
├── 6. Tone and Style（语气风格）
│     └── getSimpleToneAndStyleSection()
├── 7. Output Efficiency（输出简洁性）
│     └── getOutputEfficiencySection()
│
├── === DYNAMIC_BOUNDARY MARKER ===  ← 缓存切割点
│
[Dynamic / Per-session 部分]
├── 8. Session-specific Guidance（Agent 工具、技能发现等）
├── 9. Memory（CLAUDE.md / MEMORY.md）
├── 10. Environment Info（CWD、OS、model、git）
├── 11. Language / Output Style
├── 12. MCP Server Instructions
├── 13. Scratchpad Directory
├── 14. Function Result Clearing
└── 15. Summarize Tool Results
```

**源码位置**: `src/constants/prompts.ts:getSystemPrompt()`，约 line 350-400

#### 核心设计原则

1. **Static/Dynamic 分离**：通过 `SYSTEM_PROMPT_DYNAMIC_BOUNDARY` 标记，将永远不变的指令（缓存友好）和每 session 变化的指令分开
2. **Section 缓存机制**：`systemPromptSection()` wrapper 使计算结果在 session 内被 memo 化，避免重复计算
3. **条件编译**：大量使用 `process.env.USER_TYPE === 'ant'` 做内部/外部用户分发，`feature()` 做功能开关

### 1.2 不同模式的 Prompt 调整

CC **没有**传统意义上的 plan/act/auto 三模式 prompt 变体。实际机制：

- **Plan Mode**: 通过 `EnterPlanModeTool` / `ExitPlanModeTool` 工具实现，模型通过工具调用进入/退出。plan mode 期间 permission mode 切换，限制写操作。
- **Auto Mode / Proactive Mode**: 完全替换 system prompt 为自主代理版本（`getProactiveSection()`），加入 tick/sleep/autonomous work 指令
- **Fork Mode**: 通过 `isForkSubagentEnabled()` 开关，在 Agent 工具描述中注入 fork 语义

**关键洞察**：CC 用工具（而非模式切换）来控制行为。模型"自己决定"何时进入 plan mode。

### 1.3 关键指令措辞分析

#### "必须做 X" 的模式

CC 大量使用以下措辞策略：

```
"IMPORTANT:" — 用于高优先级指令
"CRITICAL:" — 最高优先级
"NEVER" — 绝对禁止
"MUST" — 强制要求
"ALWAYS" — 无条件执行
```

**具体示例**（from `src/constants/prompts.ts`）:

```typescript
// 安全指令 — 位于最顶层
`IMPORTANT: You must NEVER generate or guess URLs for the user unless you are 
confident that the URLs are for helping the user with programming.`

// 工具使用指令 — 强调级别极高
`Do NOT use the ${BASH_TOOL_NAME} to run commands when a relevant dedicated 
tool is provided. Using dedicated tools allows the user to better understand 
and review your work. This is CRITICAL to assisting the user:`

// 代码质量 — 负面指令优先
`Don't add features, refactor code, or make "improvements" beyond what was asked.`
`Don't add error handling, fallbacks, or validation for scenarios that can't happen.`
`Don't create helpers, utilities, or abstractions for one-time operations.`
```

**模式总结**：CC 的措辞策略是 **"负面约束优先"** — 大量告诉模型"不要做什么"而非"要做什么"。这对 code generation 尤其重要。

#### "不能做 Y" 的模式

CC 的禁止指令特别具体，不是抽象的原则而是 **可执行的操作级别**：

```typescript
// Git 操作 — 极其详细的禁止列表
`NEVER update the git config`
`NEVER run destructive git commands (push --force, reset --hard, checkout ., 
 restore ., clean -f, branch -D) unless the user explicitly requests`
`NEVER skip hooks (--no-verify, --no-gpg-sign, etc)`

// 代码风格 — 用具体比喻而非抽象原则
`Three similar lines of code is better than a premature abstraction.`
```

### 1.4 Few-shot Examples

CC **在 system prompt 中不使用 few-shot examples**。

但在 **tool descriptions 中大量使用**，特别是：

- `AgentTool/prompt.ts`：包含 4-5 个完整的 `<example>` XML blocks，展示正确的 agent spawning 模式
- `BashTool/prompt.ts`：git commit 和 PR 创建有详细的分步骤示例
- `EnterPlanModeTool/prompt.ts`：包含 GOOD/BAD 示例对

**示例格式**（from `AgentTool/prompt.ts`）:

```xml
<example>
user: "What's left on this branch before we can ship?"
assistant: <thinking>Forking this — it's a survey question.</thinking>
Agent({
  name: "ship-audit",
  description: "Branch ship-readiness audit",
  prompt: "Audit what's left before this branch can ship..."
})
assistant: Ship-readiness audit running.
<commentary>
Turn ends here. The coordinator knows nothing about the findings yet.
</commentary>
</example>
```

---

## 2. Tool Description 设计

### 2.1 Description 的精确程度

CC 的 tool description **极其详细**，远超一般的 API 工具定义。每个工具的 `prompt()` 方法返回数百到数千字的指令。

**对比规模**：

| Tool | Description 长度 (approx) |
|------|--------------------------|
| BashTool | ~4000 字（含 git/PR/sandbox 指令） |
| FileEditTool | ~500 字 |
| FileWriteTool | ~300 字 |
| FileReadTool | ~600 字 |
| AgentTool | ~3000 字（含 examples） |
| EnterPlanModeTool | ~2000 字 |

**Scion 对比**:

| Tool | Description 长度 |
|------|-----------------|
| generate_hypothesis | 1 行（"Propose a single hypothesis..."） |
| generate_patch | 1 行（"Generate a code patch..."） |
| fix_patch | 1 行（"Fix a code patch..."） |

### 2.2 Description 的写法策略

CC 的 tool description 遵循一个清晰模式：

```
1. 一句话说明用途
2. "Usage:" 段 — 列出关键使用规则
3. "When to use" / "When NOT to use" — 正反示例
4. 交叉引用其他工具 — "use X instead of Y"
5. Examples（如适用）
```

**FileWriteTool** (`src/tools/FileWriteTool/prompt.ts`) 是最精炼的示例：

```typescript
`Writes a file to the local filesystem.

Usage:
- This tool will overwrite the existing file if there is one at the provided path.
- If this is an existing file, you MUST use the Read tool first to read the 
  file's contents. This tool will fail if you did not read the file first.
- Prefer the Edit tool for modifying existing files — it only sends the diff. 
  Only use this tool to create new files or for complete rewrites.
- NEVER create documentation files (*.md) or README files unless explicitly 
  requested by the User.
- Only use emojis if the user explicitly requests it.`
```

**关键 trick**:
1. **交叉引用**: "Prefer the Edit tool... Only use this tool to create new files" — 工具之间互相引用，形成优先级网络
2. **预条件声明**: "you MUST use the Read tool first... This tool will fail if..." — 把 runtime 验证逻辑写在 description 里，让模型自己避开
3. **负面约束内置**: "NEVER create documentation files" 直接写在工具级别

### 2.3 Input Schema 结构

CC 使用 Zod 定义 schema（`Tool.ts` 中 `inputSchema: Input` 类型为 `z.ZodType`），但发送到 API 时转为 JSON Schema。

**关键特点**：
- Schema 定义极简，复杂的约束通过 description 而非 schema 表达
- 使用 `validateInput()` 方法做 runtime 验证（如 FileWrite 检查是否先 Read 过文件）
- 有 `strict` 模式标记（`readonly strict?: boolean`）用于约束 API 解码

### 2.4 CC 如何引导模型行为的 Description Trick

1. **Tool 级别的 "system prompt"**：每个 tool 的 `prompt()` 实质是该工具的小型 system prompt，包含完整的行为指令
2. **条件化 description**：`prompt()` 是 `async` 方法，可以根据 runtime 状态动态生成（如是否有 AgentTool、是否在 REPL 模式）
3. **工具互斥网络**：BashTool description 明确列出 "Use X instead of bash for Y"，形成一个完整的工具路由图：

```
BashTool description 中:
  - To read files use Read instead of cat, head, tail, or sed
  - To edit files use Edit instead of sed or awk
  - To create files use Write instead of cat with heredoc or echo redirection
  - To search files use Glob instead of find or ls
  - To search content use Grep instead of grep or rg
```

---

## 3. Code Generation 相关 Prompt

### 3.1 FileWriteTool vs FileEditTool 的 Prompt 设计

这是 Scion 最可借鉴的部分。CC 严格区分两种代码写入场景：

**FileWriteTool**（完整文件）:
- 定位：创建新文件或完全重写
- 前置条件：修改已有文件必须先 Read
- 后缀约束："NEVER create documentation files"

**FileEditTool**（diff 编辑）:
- 定位：修改已有文件的首选方式
- 核心指令："Performs exact string replacements in files"
- 精确性约束："The edit will FAIL if `old_string` is not unique"
- Ant 内部版本追加："Use the smallest old_string that's clearly unique — usually 2-4 adjacent lines is sufficient"

**对 Scion 的启示**：Scion 当前 `generate_patch` 工具的 description 只有一行。CC 的经验表明，代码生成工具需要极其详细的描述来控制输出质量。

### 3.2 代码质量约束（在 System Prompt 中）

CC 在 `getSimpleDoingTasksSection()` 中嵌入了一整套代码质量哲学：

```typescript
// 最小主义原则
`Don't add features, refactor code, or make "improvements" beyond what was asked.`
`Don't add error handling, fallbacks, or validation for scenarios that can't happen.`
`Don't create helpers, utilities, or abstractions for one-time operations.`
`Three similar lines of code is better than a premature abstraction.`

// 注释哲学（Ant 内部版本）
`Default to writing no comments. Only add one when the WHY is non-obvious.`
`Don't explain WHAT the code does, since well-named identifiers already do that.`

// 安全
`Be careful not to introduce security vulnerabilities such as command injection, XSS, SQL injection`

// 验证（Ant 内部版本）
`Before reporting a task complete, verify it actually works: run the test, execute the script, check the output.`

// 诚实性（Ant 内部版本 — 针对 false claim 问题）
`Report outcomes faithfully: if tests fail, say so with the relevant output; 
if you did not run a verification step, say that rather than implying it succeeded. 
Never claim "all tests pass" when output shows failures.`
```

**这些约束不在工具层面，而在 system prompt 的"做任务"section**。这是设计决策：代码质量是全局关切，不应绑定到特定工具。

### 3.3 先读后写的强制链

CC 通过 **多层机制** 确保模型在修改文件前先阅读：

1. **Description 层**（FileWriteTool）: "you MUST use the Read tool first"
2. **Description 层**（FileEditTool）: "You must use your Read tool at least once"
3. **Runtime 层**（FileWriteTool `validateInput()`）: 实际检查 `readFileState` 缓存
4. **System Prompt 层**: "In general, do not propose changes to code you haven't read"

四层防御，确保代码修改有上下文基础。

---

## 4. Context Window Management

### 4.1 System vs User 的信息分配

CC 的策略：

| 放在 System | 放在 User |
|-------------|-----------|
| 角色定义和身份 | 用户消息 |
| 行为规则和约束 | 工具调用结果 |
| 工具使用偏好 | 文件内容 |
| 环境信息（CWD、OS） | 动态上下文 |
| CLAUDE.md 记忆 | MCP instructions (delta 模式) |
| 代码质量哲学 | Agent listing (attachment 模式) |

**核心原则**：System prompt 放 **不变或低频变化** 的指令；高频变化的内容（如 MCP server 列表）逐步迁移到 user message 的 attachment 形式，以保护缓存。

### 4.2 cache_control 使用策略

CC 的 prompt caching 是一个精密的三层系统：

```
Level 1: Global Cache (cacheScope='global')
  - Static system prompt 部分（DYNAMIC_BOUNDARY 之前）
  - 跨所有用户/org 共享
  - 包含：角色定义、行为规则、工具使用偏好、代码质量指令

Level 2: Org Cache (cacheScope='org')  
  - 包含用户特定内容的 system prompt 块
  - 同一 org 内共享

Level 3: No Cache (cacheScope=null)
  - Attribution header
  - Dynamic content after boundary
  - 每次变化的 MCP instructions
```

**实现**：`splitSysPromptPrefix()` in `src/utils/api.ts` 将 `string[]` 拆分为带 `cacheScope` 标注的 blocks，`buildSystemPromptBlocks()` in `src/services/api/claude.ts` 转为 API 的 `cache_control` 字段。

**缓存保护策略**：
- Agent list 从 tool description 迁移到 attachment message，因为 MCP server 连接/断开导致 tool description 变化，破坏 tool schema 缓存
- MCP instructions 从 system prompt 迁移到 delta attachment，因为 server 连接时机不可控
- `systemPromptSection()` 包装器做 memo 化，避免不必要的重计算

### 4.3 System Prompt 大小控制

CC 没有硬性 token 限制，但通过以下手段控制膨胀：

1. **条件包含**：只在相关工具启用时才包含对应指令
2. **Ant/External 分发**：内部版本有更详细的指令，外部版本更精简
3. **CLAUDE_CODE_SIMPLE 模式**：极简 system prompt（仅 CWD 和日期）
4. **Automatic summarization**：明确告知模型"conversation has unlimited context through automatic summarization"

**Scion 对比**：Scion 目前的 system block 结构良好（system 放 role + problem + champion code，user 放 dynamic 内容），但缺少 CC 级别的缓存精细控制。

---

## 5. 对 Scion 的改进建议

### 优先级排序

| Priority | 改进项 | 预期收益 | 实现难度 |
|----------|--------|----------|----------|
| **P0** | 丰富 tool description | 直接提升代码质量 | 低 |
| **P0** | 添加代码质量负面约束 | 减少 LLM 过度工程 | 低 |
| **P1** | System prompt 分层和角色强化 | 提升推理质量 | 中 |
| **P1** | 添加 "先读后写" 语义 | 减少无上下文代码 | 中 |
| **P2** | 多层 cache_control 策略 | 降低 API 成本 | 中 |
| **P2** | 添加 examples 到 tool description | 减少 format error | 低 |
| **P3** | 输出风格约束 | 减少噪音 token | 低 |

---

### P0-1: 丰富 Tool Description

**当前 Scion**（`schemas.py`）:

```python
HYPOTHESIS_TOOL = {
    "name": "generate_hypothesis",
    "description": "Propose a single hypothesis for improving the solver operator pool",
    "input_schema": HYPOTHESIS_PROPOSAL_SCHEMA,
}

PATCH_TOOL = {
    "name": "generate_patch",
    "description": "Generate a code patch implementing the approved hypothesis",
    "input_schema": PATCH_PROPOSAL_SCHEMA,
}
```

**建议改为**:

```python
HYPOTHESIS_TOOL = {
    "name": "generate_hypothesis",
    "description": (
        "Propose ONE novel hypothesis for improving the VNS solver's operator pool.\n\n"
        "Usage:\n"
        "- Study ALL existing champion operators before proposing — avoid duplicating existing logic.\n"
        "- Check experiment history for approaches that already failed — do NOT repeat them.\n"
        "- Check sibling branches to avoid redundant exploration.\n"
        "- A hypothesis that sounds good but duplicates an existing operator will be REJECTED.\n\n"
        "Quality criteria:\n"
        "- Target a specific, named weakness in the current pool (not vague 'improvements').\n"
        "- The mechanism of improvement must be concrete and testable.\n"
        "- Consider the solver's execution model: your operator runs ~1000 times per solve, "
        "high variance is good, rare great outcomes beat frequent mediocre ones.\n"
        "- Prefer operators that provide a CAPABILITY the pool currently LACKS over "
        "incremental tweaks to existing operators.\n\n"
        "Common mistakes to avoid:\n"
        "- Proposing random order moves between arbitrary vehicles (unlikely to improve splits).\n"
        "- Ignoring feasibility constraints (your operator MUST produce feasible solutions).\n"
        "- Reinventing logic already present in an existing operator with different variable names.\n"
        "- Setting suggested_weight too high for unproven ideas (use 0.1-0.3 for new operators)."
    ),
    "input_schema": HYPOTHESIS_PROPOSAL_SCHEMA,
}

PATCH_TOOL = {
    "name": "generate_patch",
    "description": (
        "Generate the complete file contents implementing an approved hypothesis.\n\n"
        "Usage:\n"
        "- Write the COMPLETE file — not a diff, not a snippet. The entire file content.\n"
        "- Study the champion operator code for style, data model usage, and import patterns.\n"
        "- Follow the operator interface specification EXACTLY: "
        "subclass Operator, implement execute(self, solution, rng) -> Solution.\n\n"
        "Code quality requirements:\n"
        "- Deep-copy the solution FIRST: `new_sol = solution.deep_copy()`.\n"
        "- Skip locked orders: check `order.locked_vehicle_id is not None`.\n"
        "- Use `rng` for ALL randomness — do NOT import random directly.\n"
        "- NEVER use `list(set(...))` or iterate over set/dict in order-dependent ways — "
        "use `sorted()` for determinism. The solver runs twice with the same seed to verify.\n"
        "- Call `new_sol.remove_empty_vehicles()` before returning.\n"
        "- Maintain assignment dict consistency: update BOTH vehicle.order_ids and solution.assignment.\n\n"
        "Common rejection causes:\n"
        "- Feasibility violation: dropping or duplicating orders.\n"
        "- Non-determinism: iterating over sets without sorting.\n"
        "- Import violation: using modules not in the whitelist.\n"
        "- Interface mismatch: wrong method signature or missing deep copy."
    ),
    "input_schema": PATCH_PROPOSAL_SCHEMA,
}

FIX_TOOL = {
    "name": "fix_patch",
    "description": (
        "Fix a code patch that failed verification.\n\n"
        "Usage:\n"
        "- Read the failure details carefully — fix the SPECIFIC issue reported.\n"
        "- Make MINIMAL changes to fix the failure. Do not refactor or 'improve' unrelated code.\n"
        "- Preserve the intended algorithmic logic — only fix the mechanical error.\n"
        "- If the failure is a feasibility check, ensure EVERY order remains assigned to exactly one vehicle.\n"
        "- Return the COMPLETE corrected file, not just the changed lines.\n\n"
        "Common patterns:\n"
        "- V3_feasibility: assignment dict and vehicle.order_ids are inconsistent — "
        "update BOTH when moving orders.\n"
        "- V5_state_leak: referencing original solution's mutable objects after deep_copy — "
        "re-derive from the copy.\n"
        "- V1_syntax: Python syntax error — check indentation, parentheses, colons.\n"
        "- V2_interface: missing Operator base class or wrong execute() signature."
    ),
    "input_schema": PATCH_PROPOSAL_SCHEMA,
}
```

### P0-2: 添加代码质量负面约束到 System Prompt

**当前 Scion** (`engine.py:_split_code_context()`):

```python
system_text = (
    "You are a software engineer implementing a VRP operator for a solver optimisation framework.\n"
    "Your task is to write the complete file contents that implement the approved hypothesis below.\n\n"
    ...
)
```

**建议在 system_text 中添加**:

```python
system_text = (
    "You are a software engineer implementing a VRP operator for a solver "
    "optimisation framework.\n"
    "Your task is to write the complete file contents that implement the "
    "approved hypothesis below.\n\n"
    
    "## Code Quality Rules\n"
    "- Write ONLY what the hypothesis requires. Do not add extra features, "
    "helper functions, or abstractions beyond the immediate need.\n"
    "- Do not add error handling for impossible cases. Trust the data model. "
    "Only validate at actual boundaries (e.g., empty vehicle lists).\n"
    "- Do not add comments explaining WHAT the code does — the code should be "
    "self-explanatory. Only comment on WHY a non-obvious choice was made.\n"
    "- Prefer simple, direct code over clever abstractions. Three similar lines "
    "of code are better than a premature helper function.\n"
    "- Match the coding style of the existing champion operators EXACTLY — "
    "variable naming, indentation, structure, import order.\n"
    "- Do NOT add logging, print statements, or debug output unless specified.\n\n"
    
    "## Feasibility is Non-Negotiable\n"
    "An operator that produces infeasible solutions is WORSE than no operator at all. "
    "Before returning any modified solution, mentally verify:\n"
    "1. Every order in the instance is assigned to exactly one vehicle\n"
    "2. assignment dict and vehicle.order_ids are consistent\n"
    "3. No vehicle exceeds its capacity\n"
    "4. Hazardous goods constraints are satisfied\n"
    "5. Region and category constraints hold\n\n"
    
    f"## Problem Summary\n{D['problem_summary']}\n\n"
    ...
)
```

### P1-1: System Prompt 分层重构

**当前 Scion**：system_blocks 是单个 text block + cache_control。

**建议**：借鉴 CC 的 static/dynamic 分离，拆分为两个 system block：

```python
def _split_hypothesis_context(context):
    D = _DefaultDict(context)
    
    # Block 1: Static role + problem spec (高命中率缓存)
    static_block = {
        "type": "text",
        "text": (
            "You are a research agent optimising a combinatorial optimisation "
            "solver's operator pool.\n\n"
            "## Code Quality Rules\n"
            "...(同上)...\n\n"
            "## Problem Summary\n"
            f"{D['problem_summary']}\n\n"
            "## Operator Interface Specification\n"
            f"{D['operator_interface_spec']}\n\n"
            "## How the VNS Solver Uses Operators\n"
            "...(solver mechanics — 不变)...\n\n"
        ),
        "cache_control": {"type": "ephemeral"},
    }
    
    # Block 2: Champion code (变化频率: 仅在 champion 升级时)
    champion_block = {
        "type": "text",
        "text": (
            f"## Current Champion Operator Code\n"
            f"Study these carefully — avoid duplicating existing logic.\n\n"
            f"{D['champion_operators_code']}\n\n"
            f"## Champion State\n{D['champion_stats']}\n"
        ),
        "cache_control": {"type": "ephemeral"},
    }
    
    system_blocks = [static_block, champion_block]
    
    # User prompt: 每次不同的 experiment history 等
    user_prompt = (
        f"## Experiment History — This Branch\n{D['experiment_history']}\n\n"
        f"## Globally Blacklisted\n{D['blacklist_summary']}\n\n"
        ...
    )
    
    return system_blocks, user_prompt
```

**收益**：当 champion 未升级时，两个 block 都命中缓存，节省 ~70% input tokens。

### P1-2: 添加 "先读后分析" 语义

**灵感来源**：CC 的 "you MUST use the Read tool first before editing" 模式。

**Scion 场景**：hypothesis 阶段的模型经常不够仔细地分析现有代码就提出重复方案。

**建议**：在 hypothesis system prompt 中添加明确的分析步骤：

```python
"## Analysis Steps (follow in order)\n"
"1. Read EVERY champion operator code carefully. For each, note:\n"
"   - What move type it performs (swap, relocate, merge, split, etc.)\n"
"   - What objective it primarily targets (splits, cost, or both)\n"
"   - What solution structures it can and cannot improve\n"
"2. Identify specific GAPS — what types of solution improvements are IMPOSSIBLE "
"with the current pool?\n"
"3. Check experiment history — which attempts at filling these gaps failed, and WHY?\n"
"4. Only then propose a hypothesis targeting an identified gap.\n\n"
"If your hypothesis duplicates an existing operator's capability (even partially), "
"it will be REJECTED. Novel mechanism is required.\n"
```

### P2-1: 多层 Cache Control

**当前 Scion**：

```python
_CACHE_5M = {"type": "ephemeral"}  # 单一策略
```

**建议**：保持当前策略（Anthropic 的 ephemeral cache 对 Scion 的调用模式已足够），但在 LLMClient 中添加 cache hit 监控：

```python
# 在 llm_client.py 的 call_with_tool 中，添加 cache 命中率追踪
class LLMClient:
    def __init__(self, ...):
        ...
        self._cache_stats = {"total": 0, "cache_read": 0, "cache_create": 0}
    
    def get_cache_stats(self) -> dict:
        total = self._cache_stats["total"]
        if total == 0:
            return {"hit_rate": 0, **self._cache_stats}
        return {
            "hit_rate": self._cache_stats["cache_read"] / total,
            **self._cache_stats,
        }
```

如果监控发现 cache hit rate < 50%，说明 system block 变化太频繁，需要进一步拆分。

### P2-2: 添加 Examples 到 Tool Description

**灵感来源**：CC 的 AgentTool 包含完整的 `<example>` blocks。

**建议**：在 PATCH_TOOL description 中添加一个简短示例：

```python
"Example of a well-formed operator:\n"
"```python\n"
"class MergeSubcategoryVehicles(Operator):\n"
"    \"\"\"Merge two partially-filled vehicles of the same subcategory.\"\"\"\n"
"    \n"
"    def execute(self, solution: Solution, rng: Random) -> Solution:\n"
"        new_sol = solution.deep_copy()\n"
"        # ... implementation ...\n"
"        new_sol.remove_empty_vehicles()\n"
"        return new_sol\n"
"```\n"
"Note: deep_copy first, remove_empty_vehicles last, rng for randomness.\n"
```

### P3: 输出风格约束

**当前问题**：LLM 有时在 hypothesis_text 中过于冗长。

**建议**：在 tool description 中加入长度约束：

```python
"input_schema": {
    ...
    "properties": {
        "hypothesis_text": {
            "type": "string",
            "description": (
                "Detailed explanation of the hypothesis. 3-5 sentences. "
                "Include: what the operator does, why it's different from existing ones, "
                "and the expected mechanism of improvement. Do NOT pad with generic phrases."
            ),
        },
        ...
    }
}
```

---

## 附录 A: CC 源码关键文件索引

| 文件路径 | 内容 |
|---------|------|
| `src/constants/prompts.ts` | 主 system prompt 组装逻辑 |
| `src/constants/system.ts` | CLI system prompt 前缀、attribution header |
| `src/constants/systemPromptSections.ts` | Section 缓存机制 |
| `src/constants/cyberRiskInstruction.ts` | 安全指令 |
| `src/tools/BashTool/prompt.ts` | Bash 工具描述（含 git 操作） |
| `src/tools/FileWriteTool/prompt.ts` | 文件写入工具描述 |
| `src/tools/FileEditTool/prompt.ts` | 文件编辑工具描述 |
| `src/tools/FileReadTool/prompt.ts` | 文件读取工具描述 |
| `src/tools/AgentTool/prompt.ts` | Agent 工具描述（含 fork/examples） |
| `src/tools/EnterPlanModeTool/prompt.ts` | Plan mode 进入逻辑 |
| `src/Tool.ts` | Tool 接口定义 |
| `src/services/api/claude.ts` | API 调用 + cache_control 构建 |
| `src/utils/api.ts` | `splitSysPromptPrefix()` 缓存拆分 |
| `src/memdir/memdir.ts` | MEMORY.md 加载和截断 |

## 附录 B: Scion vs CC 关键设计对比

| 维度 | CC | Scion 当前 | 建议 |
|------|-----|----------|------|
| System prompt 结构 | 15+ 个模块化 section | 单个 text block | 拆分为 static + champion + dynamic |
| Tool description 长度 | 300-4000 字/工具 | 1 行/工具 | 扩展到 200-500 字 |
| 负面约束 | 大量具体的 "Don't" 指令 | 几乎没有 | 添加代码质量 Don't 列表 |
| Examples | tool 级别的 XML examples | 无 | 至少为 patch tool 添加 |
| 先读后写 | 4 层防御 | 无显式机制 | 在 hypothesis prompt 中添加分析步骤 |
| Cache 策略 | 3 层 (global/org/none) | 1 层 (ephemeral) | 保持但添加监控 |
| 输出格式控制 | 长度锚点 "≤25 words between tools" | 无 | 在 field description 中加长度提示 |
| 代码质量哲学 | System prompt 中完整的 YAGNI 指令 | 无 | 移植核心约束 |

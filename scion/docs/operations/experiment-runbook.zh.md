# Scion v0.4 direct-v3 实验运行与验收手册

*适用范围：当前 v0.4 direct-V3 研究工作树*
*最后更新：2026-08-21*

本手册只描述当前 direct-v3 runtime。唯一架构边界是
`scion/design/scion-architecture-v3.md`；
`scion/design/scion-architecture-v3-v0.4-direct-runtime-addendum.md` 只是
当前轻量实现说明，不能覆盖 V3。当前任务与状态分别见 `scion/TASK.md`、
`scion/docs/status/current-state.md`。

当前阶段只验收 Warehouse 与 CVRP solver research。分发、部署、安装、打包、
构建、root/systemd，以及 Trust/Hash、对象身份、租约、签发/登记和重复闭包，
都不属于本手册的运行前置或完成条件。

## 1. 正式实验的定义

当前正式研究路径是：

```text
完整且安全的问题/源码上下文
  -> 可选有限 Hypothesis research actions，或 direct one-shot
  -> 每个 attempt 最多导出一个 tainted H
  -> Hypothesis Contract
  -> 通过后，可选有限 Code research actions，或 direct one-shot
  -> 每个 attempt 最多导出一个 tainted C
  -> Patch Contract
  -> Workspace
  -> Verification
  -> Protocol
  -> Safe Features
  -> deterministic Decision
```

正式实验必须同时满足以下条件：

- 从明确记录的当前源码状态运行；同一 campaign 运行期间不得改变框架源码；
- 不绑定 surface、action 或 target file；
- 不恢复旧 campaign 的 mutable branch/champion/provider-session state；显式、
  有序的 H-only `research_history` 是普通输入，不是 reopen；
- warehouse 与 CVRP 的 `parameter_search.enabled` 都必须显式为 `false`；
  CLI 对配置不完整或启用状态 fail-closed；
- 先运行 warehouse control，确认框架闭环后再运行 clean/open CVRP；
- 用真实 Hypothesis、代码、执行行为和 Protocol 结果判断研究有效性，不能只凭测试通过或进程正常退出。

正式入口有两个窄定义。自主 H/C campaign 使用
`python -m scion.cli.main run`；已冻结 exact candidate 的 provider-free estimand
只使用 `run_fixed_candidate_funnel.py`，导出 H/C 与 provider call 均为零，但仍走
同一 complete-pair canary -> Protocol -> Safe Features -> Decision 科学链。下文
“warehouse control 先行”只约束自主 H/C control，不约束这种 provider-free fixed
funnel。

正式运行没有算法质量、novelty 或 retry budget。启用的 Creative session
必须声明有限 provider-turn、read/search、public-test、output、transcript 与共享
provider-call 资源上限；它们只负责 fail-closed，不能选择机制、静默截断上下文或
影响 Protocol/Decision。`--rounds` 是操作员明确选择的“typed formal Protocol
evaluated rounds”目标，不是模型调用次数上限或自动重试次数。每个已记录的
Contract/Verification `RESEARCH_REJECTED` 是独立 typed event：该 H/C 结束、不计
formal round，scheduler-forward 到 exact clean base 上的新 H；只有其他未进入
`EVALUATED` 的结果才会在未达到目标轮数时停止当前 invocation。
`--time-limit-sec` 是每次 solver/subprocess 的科学运行边界，必须随实验记录。

Anthropic transport 要求的 `max_tokens` 仅是 provider transport ceiling。它不是
研究质量 gate，也不授权截断、压缩或省略上下文。provider SDK retry 保持为零；
每个 deliberate provider turn 最多写一个 best-effort terminal trace，trace 不是
receipt/call identity，不能由隐藏的 SDK 重放产生，也不能改变有效 provider 结果。

v0.4 production Scheduler 默认最多允许三个 active research branches，并按
state priority/FIFO 选择 runnable branch。一个 branch 仍表示一个可持续深入的
自然研究方向，不用 host-authored diversity/mechanism gate 强制分流。Contract
与 Verification 通过且 screening 完成后，`CONTINUE_EXPLORE`（包括 screening
fail）在下一轮复用同一个 branch 的 verified provisional head：第二个 H 能看到
上一轮 canonical screening evidence，第二个 C 能从普通 path/content source
mapping 看到该 branch 已验证的当前源码。只有 Verification 失败才回退到最后一个 clean branch source，
从未验证成功的 branch 才回到 champion。这个设置不限制轮数、调用、token、
文件或持续时间。

## 2. 运行环境

### 2.1 Server `claw`

用于聚焦测试和一次正式运行：

```bash
export SOURCE_REPO=/home/clawd/research/or-autoresearch-agent
export REPO_ROOT="$SOURCE_REPO/scion"
export PY=/home/clawd/miniconda3/envs/claw/bin/python
export EXPERIMENTS_ROOT=/home/clawd/research/scion-experiments
export SCION_MODEL=gpt-5.6-terra
export SCION_BASE_URL=http://127.0.0.1:8080
```

`REPO_ROOT` 可以是当前开发工作树；必须在报告中诚实记录 Git revision 与工作树是否
有未提交改动。revision 只帮助定位源码，不签发、授权或验收实验对象，也不
要求另建 detached worktree、mirror、source acceptance 或 root-owned receipt。
实验开始后保持该源码不变，并为每次运行使用新的 campaign directory。

warehouse 数据默认位于：

```text
/home/clawd/research/scion-data
```

该默认根对应 production split。使用 `problem.yaml`、`protocol.yaml`、
`split_manifest.yaml` 的 synthetic control 时必须显式设置：

```bash
export SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/surrogate
```

CVRP 使用现有只读数据根：

```text
/home/clawd/research/or-autoresearch-agent/vrp
```

### 2.2 WSL `scion`

只在重新确认连接、代码同步和当前 CLI 配置后用于大型或并发验证：

```text
repo:        /home/xjy-ubuntu/research/or-autoresearch-agent
runner copy: /home/xjy-ubuntu/research/or-autoresearch-agent-v04dev-runner-20260629
Python:      /home/xjy-ubuntu/miniconda3/envs/scion/bin/python
```

不要把 server 的 `claw` 路径直接复制到 WSL。两个环境都必须记录各自实际
runtime source，并创建独立 campaign；不得跨机器复用 campaign state 或运行产物。

## 3. 正式运行前的共同检查

当前入口不再使用 launcher、prepared/readiness 或 postrun 工具。先在目标
runner 的当前 runtime checkout 中执行：

```bash
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT"
test -n "$SCION_API_KEY"
"$PY" -m scion.cli.main run --help
```

本机 `codex-proxy` 可能使用独立 client key；shell 中已有的其它 OpenAI key
不能代替它。可从 localhost-only `/auth/status.proxy_api_key` 临时读入环境变量，
但不得打印或写入文档/实验 artifact。启动前应用该 key 只读验证 `/v1/models`
并确认目标模型可见。

检查问题数据与配置文件后，自主 H/C run 使用新的、独立的 `CAMPAIGN_DIR`；
provider-free fixed funnel 使用新的、原本不存在的 output directory。不要跨机器
或跨运行复用 campaign/output state。

## 4. Warehouse control：CLI 直跑

warehouse 必须先运行。下面命令直接启动 campaign；它不生成 `run.sh` 或
prepared root。

```bash
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT"
export CAMPAIGN_DIR="$EXPERIMENTS_ROOT/warehouse-control-$(git rev-parse --short HEAD)"
export SCION_WAREHOUSE_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/surrogate

"$PY" -m scion.cli.main run \
  --problem problems/warehouse_delivery/problem.yaml \
  --protocol problems/warehouse_delivery/protocol.yaml \
  --split problems/warehouse_delivery/split_manifest.yaml \
  --seeds problems/warehouse_delivery/seed_ledger.yaml \
  --campaign-dir "$CAMPAIGN_DIR" \
  --rounds 2 \
  --time-limit-sec 30
```

运行结束后，只使用 CLI 的 `inspect` 和 `report` 命令读取 campaign 证据；
不要把旧工具或旧 campaign 当作当前入口。

## 5. 自主 H/C control 在 Warehouse 通过后才进入 CVRP

在启动自主 CVRP H/C control 前，确认 warehouse 的 ordinary H/C refs、typed step
outcome、可用 per-turn trace、Contract、Verification、Protocol 与 Decision 都可
追溯，且结果具有可归因的 solver 证据。若发现框架错误，修复后从新的源码状态
创建新的 campaign。provider-free fixed funnel 不生成 H/C，也不借用这条要求伪造
proposal evidence。

## 6. Clean/open CVRP：CLI 直跑

CVRP 使用与通过 warehouse control 相同的 runtime 源码状态，并从新的
`CAMPAIGN_DIR` 开始：

```bash
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT"
export SCION_PROBLEM_DATA_ROOT=/home/clawd/research/or-autoresearch-agent/vrp
export CAMPAIGN_DIR="$EXPERIMENTS_ROOT/cvrp-open-$(git rev-parse --short HEAD)"

"$PY" -m scion.cli.main run \
  --problem scion/problems/cvrp/problem.yaml \
  --protocol scion/problems/cvrp/formal/protocol.yaml \
  --split scion/problems/cvrp/formal/split_manifest.yaml \
  --seeds scion/problems/cvrp/formal/seed_ledger.yaml \
  --campaign-dir "$CAMPAIGN_DIR" \
  --rounds 2 \
  --time-limit-sec 30
```

open CVRP 不绑定 successor、surface、action 或 target file。

## 7. 低频监控与当前产物

自主 H/C run 可低频读取 campaign 状态；不要秒级轮询或自行重启：

```bash
"$PY" -m scion.cli.main inspect campaign --campaign-dir "$CAMPAIGN_DIR"
"$PY" -m scion.cli.main report summary --campaign-dir "$CAMPAIGN_DIR" --markdown
"$PY" -m scion.cli.main report failures --campaign-dir "$CAMPAIGN_DIR"
```

主要证据位于 `$CAMPAIGN_DIR/`，包括 `campaign_summary.json`、
`run_status.json`、`scion.db`、`llm_traces/`、`metrics/` 和
`workspaces/`、`champions/`。它们是诊断与研究验收的输入，但不替代对实际
Hypothesis、当前 branch source、solver 行为和 Protocol 结果的审查。当前 active
campaign 不为每次 screening 另建 formal-candidate identity/hash 闭包。
provider-free fixed funnel 的普通证据是其 fresh output 下的 `input.json`、Protocol
metrics、可选 promoted snapshot 与单一 `terminal.json`；它没有 H/C trace、campaign
DB 或 mutable reopen state。

## 8. 旧运行手册说明

本文件先前关于 direct launcher、prepared root、readiness、`run.sh` 与
postrun 工具的流程已 superseded，不能执行或用作当前验收依据。

## 9. 从 H/C 到 Decision 的诊断顺序

不要先从最后一个 reason code 猜原因。按职责边界逐层检查。

### 9.1 H/C research turns、ordinary history 与 typed outcome

先从 `campaign_summary.json`/status 的 typed step outcome 判断 H/C 是否导出，
再查看可选的 `llm_traces/` terminal diagnostics 和本 campaign 的普通
`research_history.jsonl`。trace 写入是 best-effort，缺少 trace 不能把有效结果
改写为失败；trace 也不是 call identity、receipt 或另一份事实账本。

列出可用 trace 与普通历史：

```bash
find "$CAMPAIGN_DIR/llm_traces" -maxdepth 1 -type f -name '*.json' -print | sort
test ! -e "$CAMPAIGN_DIR/research_history.jsonl" || \
  wc -l "$CAMPAIGN_DIR/research_history.jsonl"
```

应看到：

- 每个 deliberate provider turn 至多有一个 terminal trace，并计入共享 cap；
- 一个 attempt 最多导出一个 H，H 通过 Contract 后最多导出一个与该 exact H
  绑定的 C；内部 research turns 不构成 retry；
- `research_history.jsonl` 只保存安全、H-visible 的普通研究记录，不含
  validation/frozen/raw/private state，也不恢复 mutable campaign state；
- 失败保持原始 typed 分类，不被改写成研究否决或自动再调用；合法的
  Contract/Verification `RESEARCH_REJECTED` 记录后 scheduler-forward 到新 H，且
  不计 formal round。

### 9.2 Hypothesis 与 Patch Contract

Contract 只判断结构和控制边界：schema、surface/locus、editable/frozen path、
当前 source binding、action、import/API/interface，以及 patch 是否绑定获批 H。
它不应因为研究风格、机制偏好、遥测描述或“新颖性不足”而否决。

快速看每一步：

```bash
jq '.steps[] | {
  round, branch_id, hypothesis,
  contract_passed, contract_diagnostics,
  code_archive_ref, failure_stage, failure_detail,
  execution_outcome, execution_outcome_reason_code
}' "$CAMPAIGN_DIR/campaign_summary.json"
```

### 9.3 Verification

Verification 判断候选代码能否正确执行：语法、接口、状态泄漏、feasibility、
objective consistency、nondeterminism、crash、timeout 和 solver output。
缺失的诊断遥测本身不能让一个正确 solver 结果失败。

```bash
jq '.steps[] | {
  round, branch_id,
  verification_passed, verification_detail,
  canary_result, failure_stage, failure_detail
}' "$CAMPAIGN_DIR/campaign_summary.json"
```

### 9.4 Protocol

Protocol 组件只负责 comparative scientific judgment。检查 stage、case/seed、
attempted/valid/failed pairs、win/loss/tie、median delta、CI、runtime，以及
`raw_metrics_ref`。不要从 provider 自由文本或诊断遥测重算 Decision。

```bash
jq '.steps[] | {
  round, branch_id,
  protocol_result: (.protocol_result // null)
}' "$CAMPAIGN_DIR/campaign_summary.json"
```

按 `raw_metrics_ref` 打开 `campaign/metrics/*.json`，核对聚合值与 pair 级证据、
case/seed 和实际 candidate/champion source。`statistical expand` 是 Protocol 对预注册样本的动作，不是 provider retry。

### 9.5 Decision

Decision 只消费 Safe Features、Protocol gate outcome 和硬安全事实，并做确定性映射。核对 Protocol reason codes、Decision reason codes 和最终 action；不要允许自由文本、遥测完整性或 scheduler prose 改写科学结论。

```bash
jq '.steps[] | {
  round, branch_id,
  protocol_gate: (.protocol_result.gate_outcome // null),
  protocol_codes: (.protocol_result.protocol_reason_codes // []),
  decision, decision_reason_codes,
  decision_features
}' "$CAMPAIGN_DIR/campaign_summary.json"
```

Scheduler 只负责 branch state、priority/FIFO 和 active slot；若它改变 Protocol/Decision 结论或向模型注入机制偏好，应按框架错误处理。

如果某次 screening 结果是 `CONTINUE_EXPLORE`，下一次 evaluated candidate
还必须核对：

- `branch_id` 与上一轮相同；
- 第二个 H 的 canonical `experiment_history` 恰好包含该 branch 的上一条
  screening evidence；
- 第二个 C 的 editable source context 对上一轮触及的文件使用 branch-current
  path/content value；
- 每个 attempt 最多导出一个 H 和一个 C；有限 deliberate Creative turns 全部
  计入共享 cap，不构成 retry，也不会产生第二个导出值。

当前 solver-improvement 验收不投资 campaign reopen。若 live campaign 无法在
现有 branch state 与 workspace 上继续，保留现场并显式启动 fresh campaign；
不得为继续运行补建 identity、签发、租约、hash 链或 reopen proof，也不能静默
回退到 champion 后伪装成同一研究分支。

继续核对 branch workspace 中的实际源码与 step history 所记录的 H/C、Contract、
Verification、Protocol 和 Decision 是否一致。阶段复用直接使用该 workspace；
不得为此补建 identity manifest、digest 链或 cumulative closure。

## 10. 结束后的 CLI 验收

结束后通过 CLI 读取 campaign：

```bash
cd "$REPO_ROOT"
export PYTHONPATH="$REPO_ROOT"

"$PY" -m scion.cli.main inspect campaign --campaign-dir "$CAMPAIGN_DIR"
"$PY" -m scion.cli.main report summary --campaign-dir "$CAMPAIGN_DIR" --markdown
"$PY" -m scion.cli.main report failures --campaign-dir "$CAMPAIGN_DIR"
```

已知 branch/hypothesis id 时再使用：

```bash
"$PY" -m scion.cli.main inspect branch '<branch-id>' --campaign-dir "$CAMPAIGN_DIR"
"$PY" -m scion.cli.main inspect hypothesis '<hypothesis-id>' --campaign-dir "$CAMPAIGN_DIR"
```

## 11. 有效研究的验收标准

框架验收与研究验收必须分开。

框架层至少证明：

- 已记录的当前源码状态与 campaign 配置一致；
- deliberate provider turns、导出的普通 H/C refs、可用 trace 与 typed outcome
  符合 direct-v3；
- Contract、Verification、Protocol、Decision 没有越权；
- multi-file patch 如有需要可完整物化、执行，并按 typed Decision 保留或回退；
- screening continuation 确实在同一 branch 上利用上一轮实验和 verified source，
  而不是创建互不知情的新分支；
- ordinary branch source、step lineage 与 Protocol evidence 一致，未把 no-op
  或 patch composition 悄悄当成有效 solver 证据；
- campaign artifacts 完整，failure lane 没有混淆。

研究层至少回答：

- H 是否提出具体、可证伪并与当前源码相符的算法假设；
- C 是否真正实现该机制，而非注释、参数微调或无关重排；
- solver 行为是否能归因到修改后的执行路径；
- complete paired observations 是否只把 problem-owned mechanism-family
  association 暴露给后续 H；该 association 不是因果、exact activation、host
  mechanism selection、Protocol gate、Safe Feature 或 Decision input；
- Protocol 是否提供足够的 case/seed/pair、质量与 runtime 证据；
- 结果是可复现的收益、有信息量的无收益，还是框架/基础设施失败；
- warehouse 和 open CVRP 是否都表明同一小型 runtime 能进行实际研究。

若只有正常退出、HTTP 200、测试通过或生成了一份 patch，不能关闭 v0.4。
有效的负结果可以关闭一个预注册实验 rung，但不能关闭当前 `TASK.md`。当前阶段
还必须取得 Warehouse 连续晋升及独立 replay，并取得 CVRP 的
screening -> validation -> frozen 晋升及对原始 B0 的独立比较。

## 12. 诊断运行与正式证据隔离

自主 campaign 的当前 CLI 直跑不暴露旧 launcher 的 forced-target、prepare 或
resume 路径；provider-free fixed funnel 同样不调用旧 launcher。若需要诊断，
创建独立输出目录，并明确把它与 warehouse/CVRP formal control 的研究证据隔离。

## 13. 失败处理

失败后按以下顺序保全证据：

1. 不删除或覆盖 campaign directory；
2. 记录 `git rev-parse HEAD`、实际 CLI 参数和 `run_status.json`；
3. 读取 `run_status.json`、`campaign_summary.json` 与 CLI report 输出；
4. 检查 typed step outcome、ordinary H/C refs/research history 与可用 per-turn trace；
5. 确认失败层：provider/infra、Contract、Verification、Protocol 或 Decision；
6. 若需代码修复，修改完成后创建新的 campaign，不复用旧 campaign state；
7. 只有操作员显式决定后才启动新的 invocation。

不要把“请求轮数未完成”自动解释为需要重试。先看最后一个 typed
`execution_outcome` 和 `transition_reason`：finalized proposal、Contract 或
Verification 的 `RESEARCH_REJECTED` 是 attempt-terminal、formal count 为零，并
scheduler-forward 到 clean base 上的新 H；其他非 `EVALUATED` category 才停止或
hold 当前 invocation。

## 14. 最终清单

Warehouse：

- [ ] campaign 记录实际源码状态与明确的 CLI 配置，运行期间源码未改变；
- [ ] ordinary H/C refs、typed outcome、可用 per-turn trace、Contract、Verification、Protocol、Decision 全部可审计；
- [ ] 研究结果有实际算法与 solver 证据。
- [ ] 同一不中断 campaign 达到至少 v3，且独立 replay 支持最终 champion
  优于 v1 和 immediate predecessor；production transfer 按 `TASK.md` 得到晋升
  或预注册 matched resolution。

CVRP：

- [ ] 若为自主 H/C control，warehouse 已先通过；若为 provider-free fixed
  funnel，已记录 H/C/provider calls 为零；
- [ ] 使用同一 runtime 源码状态，从 fresh campaign 或 fixed-funnel output 开始；
- [ ] 自主 campaign 使用当前 CLI 直跑；exact fixed candidate 只使用
  `run_fixed_candidate_funnel.py`；两者都不使用旧 launcher 参数；
- [ ] 无 successor 目标绑定或 mutable 历史 campaign 恢复；若使用
  `research_history`，其显式路径、顺序与 H-only 边界已记录；
- [ ] 低频监控不干预运行；
- [ ] open research direction、代码实现、Protocol 和 full-solver 行为可归因；
- [ ] 一个 exact candidate 完整通过 screening、validation 和 frozen，确定性晋升，
  且独立比较支持其优于原始 B0，不引入 feasibility/fleet regression。

只有两组 control 都完成并经过上述验收后，才更新 `TASK.md` 和
`current-state.md` 的正式实验结论。

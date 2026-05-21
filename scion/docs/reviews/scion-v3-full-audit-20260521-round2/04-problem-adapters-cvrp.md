# Problem Adapters 与 CVRP 审核

审计重点：CVRP/ALNS/VNS/route/fleet/total_distance 等是否只通过 adapter/problem provider 暴露；CVRP novelty false-positive 修复后是否仍有设计风险；agent 是否能充分研究 CVRP 对象。

## 总体判断

CVRP adapter 已经承担 v3 要求的问题域能力入口：surface、prompt provider、active solver facts provider、contract provider、smoke provider、mechanism novelty provider 和 runtime telemetry declaration 都位于 problem-owned package 或 problem surface 中。generic proposal/runtime 不再需要直接理解 `solver_algorithm_total_distance`、`fleet_violation` 等字段。

已知 cluster removal novelty false-positive 在 `e04b1de` 后有明显收敛：CVRP novelty provider 要求 exact contradicted span / matched span，能识别 allowed variant，结果携带 fact ids 与 digests。剩余风险是该 provider 仍然高度 regex/pattern 驱动，模块体量超过 1000 行，false-positive/false-negative 的长期治理需要更强的结构化测试和模块拆分。

## 发现 C-01

Severity：P2

模块：CVRP mechanism novelty

证据：

- `scion/scion/problems/cvrp/mechanism_novelty/provider.py:80`
- `scion/scion/problems/cvrp/mechanism_novelty/provider.py:560`
- `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair.py:145`
- `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair.py:579`
- `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair.py:636`
- `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider.py`

问题：

CVRP novelty false-positive 的已知实例已被修复，但 `destroy_repair.py` 仍达 1208 行，集中承载大量 pattern、span extraction、variant classification 和 semantic matching。provider 以 exact span 作为降噪条件是正确的，但底层仍偏正则和启发式，长期看容易在 Or-opt、cluster、removal/savings、negated premise 等近义表达上反复出现 false-positive/false-negative。

风险：

- 新增 CVRP mechanism family 时，pattern 交叉影响难以审计。
- regression test 虽然覆盖已知 case，但缺少按 mechanism taxonomy 组织的 corpus，难以证明“不把 allowed variant 判 duplicate”。
- 大文件修改成本高，容易把 CVRP domain reasoning 继续堆进一个 provider。

建议修复：

按 mechanism family 拆分 novelty matcher：destroy/repair、local search、acceptance、noise/randomization、route construction 等。建立 problem-owned novelty regression corpus，样例至少包含 duplicate、contradiction、allowed variant、negated premise、insufficient evidence。provider facade 继续返回现有 `MechanismNoveltyResult`，generic proposal 不需要变化。

## 发现 C-02

Severity：P2

模块：CVRP solver design provider

证据：

- `scion/scion/problems/cvrp/adapter.py:53`
- `scion/scion/problems/cvrp/solver_design_provider.py`
- `scion/scion/proposal/context_manager/manager.py:493`
- `scion/scion/proposal/engine/solver_design_prompts.py:217`

问题：

CVRP solver design provider 已通过 adapter 暴露，是正确边界。但 provider 文件本身 872 行，混合 prompt、API manifest、integration files、active solver design context、adapter-specific guidance。这个问题不违反 generic core 边界，却增加 problem adapter 的维护和审计难度。

风险：

- agent 上下文变化不易定位到 prompt fragment、tool manifest 还是 integration path policy。
- 其他 problem adapter 可能复制该大型 provider 模式。

建议修复：

保持 adapter 对外 facade 不变，内部拆成 `prompt_fragments.py`、`api_manifest.py`、`integration_policy.py`、`active_design_context.py`。新增 adapter contract test，保证 generic context manager 只依赖 provider protocol，而不依赖 CVRP 文件结构。

## 发现 C-03

Severity：P2

模块：CVRP telemetry declaration / validation feedback

证据：

- `scion/scion/problems/cvrp/problem-v1.yaml:141`
- `scion/scion/problems/cvrp/solver_runtime/algorithm_runtime.py`
- `scion/scion/runtime/telemetry_guard/contract.py:139`
- `scion/scion/core/decision.py:68`

问题：

CVRP telemetry fields 与 roles 已被 problem surface 声明，runtime adapter 负责发射 `solver_algorithm_*` 字段，这符合 v3。剩余风险是 feedback path 对 telemetry activation failure 的可操作性仍依赖 guard guidance 与 proposal feedback，而 top-level decision reason 不携带足够细分信息。

风险：

- agent 能看到“telemetry failed”，但不一定能从 branch summary 直接区分是 activation missing、effect field misuse、outcome field protected，还是 emitted undeclared field。
- C11 类 telemetry activation 失败仍可能在多个 round 中重复出现。

建议修复：

将 surface declaration id、runtime role、mechanism template id、missing/invalid emitted field 放入 typed telemetry failure payload，并在 problem adapter 层提供简短、问题域化的 repair hint。generic decision 只转发 typed payload，不解释 CVRP 字段语义。

## 发现 C-04

Severity：P3

模块：CVRP active facts coverage

证据：

- `scion/scion/proposal/active_solver_snapshot.py`
- `scion/scion/problems/cvrp/adapter.py:53`
- `scion/scion/problems/cvrp/mechanism_novelty/provider.py:80`

问题：

active solver snapshot 已支持 branch workspace、champion snapshot、problem spec root，并生成 fact packet digest。当前风险不是明显缺陷，而是 coverage drift：当 CVRP solver implementation 增加新 operator/module 后，fact extraction 是否同步覆盖，需要 problem-owned tests 保证。

风险：

- agent 与 novelty gate 仍同源，但同源 fact packet 可能漏掉新机制，导致 gate 不能识别 duplicate 或 agent 不能看到现有设计。

建议修复：

在 CVRP adapter 测试中增加 “active solver implementation -> fact packet” 覆盖表，每个 problem-owned operator/mechanism family 至少有一个 fact id。新增 solver module 时必须更新 active facts expectation。

## 正向对齐点

- CVRP runtime field declarations 位于 `problem-v1.yaml`，不是 generic runtime hardcode。
- `MechanismNoveltyResult` 携带 `variant_allowed`、`contradicted_fact_ids`、span、digest 和 provenance，使 rejection 可审计。
- provider 在缺少 active fact packet 时不会自行“看更多”，而是要求同源 facts。


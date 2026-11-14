# 模块化与测试组织债务审核

审计重点：大文件、模块职责、测试组织是否仍构成架构债；是否影响 v3 boundary、agentic flow、evidence/lineage 可审计性。

## 总体判断

v0.4 的关键逻辑已经形成，但多个生产文件超过 1000 行，且集中在 deterministic kernel、proposal LLM client、evidence recorder、explore pipeline 和 CVRP novelty。按 onboarding 的约束，超过 1000 行属于 active debt；超过 3000 行才是 stop-the-line。本轮没有超过 3000 行的单文件，但 P1/P2 模块化债已经影响审计清晰度。

本轮统计到的主要超大文件：

| 文件 | 行数 | 说明 |
| --- | ---: | --- |
| `scion/scion/proposal/llm_client.py` | 1240 | LLM 调用、schema repair、retry、provider glue 聚合 |
| `scion/scion/core/evidence_recorder.py` | 1211 | status、summary、progress、lineage、telemetry counts 聚合 |
| `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair.py` | 1208 | CVRP novelty pattern/matcher 聚合 |
| `scion/scion/core/explore_step_pipeline.py` | 1128 | branch step orchestration 聚合 |
| `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider.py` | 1260 | oversized test corpus |
| `scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py` | 1040 | oversized smoke tests |

## 发现 M-01

Severity：P1

模块：core evidence / pipeline modularity

证据：

- `scion/scion/core/evidence_recorder.py`
- `scion/scion/core/explore_step_pipeline.py`

问题：

`evidence_recorder.py` 同时处理 campaign status、summary、in-flight protocol snapshot、partial metrics redaction、formal telemetry failure count、lineage-ish reporting 等职责。`explore_step_pipeline.py` 聚合 branch step orchestration、proposal handling、contract/smoke/screening dispatch、decision finalization 等路径。两者都超过 1000 行，且位于 v3 deterministic kernel 的审计核心。

风险：

- evidence/lineage/telemetry 的边界在一个大文件中交错，修复 T-01/T-03 时容易引入回归。
- explore step 的 deterministic protocol 与 agentic proposal glue 难以分层审计。

建议修复：

拆分 `evidence_recorder.py` 为 `status_writer`、`summary_builder`、`protocol_progress_recorder`、`telemetry_summary`、`artifact_refs` 等内部模块。拆分 `explore_step_pipeline.py` 为 proposal step、pre-protocol gates、protocol execution、decision finalization glue。保持 public API 兼容，先做机械拆分，再做行为修复。

## 发现 M-02

Severity：P1

模块：proposal LLM client

证据：

- `scion/scion/proposal/llm_client.py`

问题：

`llm_client.py` 1240 行，集中处理 provider invocation、structured JSON repair、schema validation、retry/backoff、response normalization、error taxonomy 等。v3 将 LLM 限定为 proposer，不应让 LLM client 成为隐含 policy 层；当前文件体量使“调用适配”和“proposal policy/repair”边界不够清晰。

风险：

- schema/contract failure 与 provider transport failure 的语义容易混在一起。
- 新模型/provider 接入时可能修改 proposal policy，而不只是 transport adapter。

建议修复：

拆分为 provider transport、structured response parser、schema repair/retry policy、error taxonomy、test fixtures。proposal engine 只依赖窄接口：`generate_structured(prompt, schema, phase_context) -> typed result / typed failure`。

## 发现 M-03

Severity：P2

模块：CVRP novelty modularity

证据：

- `scion/scion/problems/cvrp/mechanism_novelty/destroy_repair.py`
- `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider.py`
- `scion/scion/tests/unit/test_mechanism_novelty.py`

问题：

CVRP novelty provider 的生产 matcher 与测试 corpus 都过大。近期 false-positive 修复依赖新增启发式与 regression tests，但模块结构仍不利于持续添加 mechanism family。

风险：

- 新增一个 allowed variant 可能影响不相关 family。
- oversized tests 难以定位失败属于 parser、matcher、variant policy 还是 provider result assembly。

建议修复：

按 novelty family 拆分 matcher 与测试文件。引入 table-driven corpus fixture，每条 case 标明 active fact id、candidate premise、expected classification、span expectation、allowed variant reason。

## 发现 M-04

Severity：P2

模块：contract / schema / campaign

证据：

- `scion/scion/contract/gate.py`
- `scion/scion/proposal/schemas.py`
- `scion/scion/core/campaign.py`
- `scion/scion/proposal/agentic_grounding.py`

问题：

这些文件处于 800 行左右，虽未超过 1000 行 active-debt 阈值，但承担 v3 contract/schema/campaign control 的关键职责。`contract/gate.py` 还包含 legacy problem-domain allowlist，`schemas.py` 汇集多 phase schema，`campaign.py` 同时处理 status/state/progress callbacks。

风险：

- 后续修复 boundary 或 telemetry reason 时，这些文件容易跨职责膨胀并超过 1000 行。
- schema 与 phase-specific policy 继续聚合，会让 two-stage proposal contract 不够直观。

建议修复：

在 P1 大文件拆分后，将这些文件列为 P2 预防性拆分：contract path policy、contract schema validation、proposal schema per phase、campaign status/progress callbacks 分离。

## 发现 M-05

Severity：P2

模块：test organization / boundary enforcement

证据：

- `scion/scion/tests/unit/test_v3_problem_boundary_no_cvrp_terms_in_generic_layers.py`
- `scion/scion/tests/unit/test_cvrp_mechanism_novelty_provider.py`
- `scion/scion/tests/unit/test_agentic_solver_design_algorithm_smoke.py`

问题：

边界测试存在，但扫描范围遗漏 generic evidence；CVRP novelty 和 agentic smoke 测试过大。测试组织目前能防部分回归，但不利于把 v3 约束表达成小而稳定的 contract。

风险：

- 新增 generic evidence CVRP 泄漏不会被 test 捕捉。
- 大测试文件失败时定位成本高，开发子agent容易做局部 patch 而不是修清边界。

建议修复：

扩展 boundary sentinel 到 evidence/lineage generic 包；将大型 novelty/smoke tests 拆成 contract tests、fixtures、regression corpus、phase-specific smoke tests。每个 v3 invariant 保持独立失败信号。


# P5b 固定矩阵：冻结配置与运行记录

*2026-11-15 · 用户本轮明确授权真实 provider 研究；下列参数先于首次 dispatch 固定*

遵循 [P5 合同](../../../design/v0.5/v0.5-p5-process-assessment.md)。这里只研究
能力是否实际出现，不估计 E3 的机制因果效果，不进行 E4 外部确认。
所有失败、未产出、无收益、资源中止均保留；不追加槽位、不修复后替换失败运行。

## 冻结输入

研究根：`/home/clawd/research/scion-experiments/v05-p5b-process-study-20261115`。
其中 [run-plan.json](/home/clawd/research/scion-experiments/v05-p5b-process-study-20261115/run-plan.json)
保存每项实际 argv、非秘密环境、模型策略、输入路径和硬件/依赖版本；
[preflight-results.json](/home/clawd/research/scion-experiments/v05-p5b-process-study-20261115/preflight-results.json)
记录八项 CLI parse、正式实例存在性和带正式排除清单的公开闭包复制结果。
模型密钥仅运行时从本机 proxy 取得，不写入配置或文档。

- 源码：`6ef924e6` 加当前 P0–P5a 未提交变更，共 2484 个普通文件完整复制到
  `source/`，保存 `source-at-freeze.diff`、`source-status.txt`、`source-files.json`。
  本批只执行该副本；不从后续工作树动态 import，不恢复任何旧 campaign。
- baseline：该副本的 `scion/scion/problems/cvrp` 与 `surrogate` 完整树；不是 R22 C3、
  unchanged B0 或晋升候选。各 fresh campaign 独立复制相同起点。
- CVRP：既有 R7 split 的 6 screening / 6 validation / 12 frozen / 1 canary，
  共 25 个实际文件复制至 `inputs/cvrp/formal-data`。原入口 formal split 的另一套
  37 个实例并非本机当前可用数据，未假装已使用它。采用 R26 seeds 和 Protocol
  的样本/门槛配置，具体内容随运行保存；这些是开发已见人口，不能冒充独立确认。
- Warehouse：默认 split 的 17 / 10 / 17 / 3，共 47 个文件复制至
  `inputs/warehouse/formal-data`；默认 seeds/Protocol。两个问题原 spec 自有 canary
  仍在冻结问题树中，也进入公开执行排除清单。
- Protocol 只调整本次实验声明的时间策略：所有阶段 diagnostic=1 秒、open=5 秒，
  无 dimension/glob 覆盖。否则旧 CVRP 的 60–240 秒规则会覆盖 CLI 参数。
  统计门槛、feasibility/objective、Decision 与正式暴露边界不修改。
- 两问题 `parameter_search=false`，O+M 开启，production 三 branch 默认调度。
  CVRP 保持完整 solver-design editable 空间；Warehouse 保持既有 operator editable
  边界、完整 solver 执行。后者是独立问题控制，不能声称已经验证任意 solver 架构改写。
- 初始 formal history 为空；公开输入仅单题导出，没有评审答案。03 仅导入相应 01
  实际 `public_research/continuity` 全集，不筛选、补写或导入候选 source；若没有
  可用材料，明确记录 M 机会缺失，不能用手写正确答案替代。

## 模型与资源

本机 `http://127.0.0.1:8080` OpenAI-compatible proxy，显式请求 `gpt-6.1-sol`、
reasoning=`high`，八项一致；模型列表已确认包含此名称。不做额外 inference health call。
SDK retry=0，Scion redispatch=0；H timeout=180s，C/finalize=300s。
temperature/top_p 和 max output tokens 按现有 transport 省略，provider 管理输出与
context ceiling；proxy 没有披露精确价格、账户 spend cap 或后端模型快照版本。
因此冻结的是请求模型/策略，不能声称锁定了不可变后端或精确货币费用。
按实际 usage 报告 token；未知细项保留 null，不当作零。

Python `/home/clawd/miniconda3/envs/claw/bin/python`；每项顺序独占研究运行，不启动
并行 solver/test。OMP/OpenBLAS/MKL/NUMEXPR 各 1 线程。硬件与包版本见 run-plan。

|顺序|槽位|provider cap|outer wall|formal rounds / solve 秒|材料导入|
|---|---|---:|---:|---|---|
|1|cvrp-01|48|1800s|1 / 1|无|
|2|warehouse-01|48|1800s|1 / 1|无|
|3|cvrp-02|48|1800s|1 / 1|无|
|4|warehouse-02|48|1800s|1 / 1|无|
|5|cvrp-03|48|1800s|1 / 1|cvrp-01 全部实际公开材料|
|6|warehouse-03|48|1800s|1 / 1|warehouse-01 全部实际公开材料|
|7|open-cvrp|192|7200s|3 / 5|无|
|8|open-warehouse|192|7200s|3 / 5|无|

总上限 672 次 physical dispatch、7 小时 outer wall、3480 秒公开研究 CPU、
7 GiB 公开研究材料；各槽位额度不可互转。subject/analysis/checker、输入/输出、
AS/scratch、source/storage、读写和 H/C session 限额逐字段保持 P5a 的配置副本。
正式评估/test_patch 计入 outer wall、成本单列。外部独立确认次数为 0。

单槽位按原 typed 路径于 formal 目标完成、资源上限、auth/quota、基础设施故障、
用户中止或边界违规中最先发生者结束。局部拒绝可在剩余额度内进入新 H，不能
修补已导出 H/C。普通 resource stop/研究失败后继续下一预定槽位；auth/quota、
隔离泄漏或确认影响整批的基础设施故障停止余下槽位，保持 not_run 并写原因。
不因为观察正负而加时、换模型、重跑或调整预算。

## 运行和分析记录

现有 CLI 直接运行，每项独立 `runs/<run_id>`；tmux 仅承载进程，不新增 launcher
或 runtime authority。`logs/<run_id>.log`、pane exit、原 status/summary、全部 traces、
materials/source、metrics 均保留。不得覆盖终态目录或打开 live SQLite。

按原 rubric 核验调查前预测、实际请求与观察、解释变化和下一行动，以及旧材料
是否实际读取并核对 source/input。工具成功、只写笔记、只存在索引均不算复用。
成本缺失和外部干预显式报告。当前只有本轮分析者；独立第二评审尚未完成，不把
同一分析者重复判断伪装成双盲/双评审，也不提前标记 E2 通过。
运行和分析后的实际状态在另列 postrun 中更新，不重写上述启动前参数。

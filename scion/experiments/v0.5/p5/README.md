# P5 诊断材料与离线复核

设计和 D01–D12 验收在 [P5 合同](../../../design/v0.5/v0.5-p5-process-assessment.md)。
本目录是开发题库/配置，**没有真实 provider 运行结果，不是已冻结的启动记录**。
`plan.json` 定义六个诊断和两个开放运行的槽位；不可删失败槽位或临时补成功样本。
具体 P5b 的冻结参数与实际结果另见[实验索引](../../../docs/experiments/v0.5/README.md)，
不将事后结果或评审内容写回本题库。

`cvrp/public/` 和 `warehouse/public/` 由各问题维护公开数据，解是手工样本，
不是 solver 测量。`evaluator/answers.json` 是评审答案，不能导入 agent，不能加入
formal split。微型输入不用历史 held-out 数据。参考的距离/容量/字典序值由真实
隔离 checker 验证，但 checker PASS 不证明 agent 理解了问题。

在仓库根使用当前交接的 Python，可导出**单题**普通 research input：

```bash
env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python scion/tools/p5_assessment.py export cvrp-01 /tmp/p5-cvrp-01.json
env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python scion/tools/p5_assessment.py export open-warehouse /tmp/p5-open-warehouse.json
env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python scion/tools/p5_assessment.py template /tmp/p5-review.json
```

输出不覆盖已有文件。六个诊断的示例 JSON 放在 current_question，observations 为空，
不冒充已有 prior-research observation schema。open 题只有问题，未指定算法步骤。
若要给新 H 导入 01 的材料，使用其**实际 continuity 导出目录**，不导整个 campaign
或本题库根。没有材料则如实记录；不能给模型补写参考答案。

`config/*-public-research.json` 可交给已有 `--public-research`，
`code-research-limits.json` 可交给 `--code-research-limits`；`*-run.json` 是记录参数，
**不是 CLI 新增配置入口**：将 resource_envelope 对应值展开为已有的
`--provider-call-cap / --outer-hardwall-sec / --provider-transient-retries`，以及
`--rounds / --time-limit-sec`。既有 CLI 参数先 parse；完整 source、provider/model、
正式数据/Protocol/split/seeds、硬件和 actual dirty code 仍须写入本次具体启动记录。
不新增 launcher，不用这份 README 作为 launch 授权。

评审人员填写 template 的每个槽位；每维给证据、理由和 rating，两人独立评审。
引用 `{path,start,end,quote}` 使用相对指定 evidence-root 的路径和 UTF-8 字节偏移
（end 不包含），quote 必须与原字节完全相同。路径不能越界或含 symlink。
root 是 operator 评审目录，可包含原始 provider trace；禁止向 agent 暴露。

```bash
env PYTHONPATH=scion:. /home/clawd/miniconda3/envs/claw/bin/python scion/tools/p5_assessment.py review /tmp/p5-review.json --evidence-root /tmp
```

未运行的空模板也可以复核，结果仍是八行 not_run，绝不输出 E2_PASS。
工具保留两份评分、所有分歧、缺失成本原因和终态引用，不自动判断引用是否证明
解释、时序、读取或因果关系。评审者必须核对原始请求/响应和实际 source/input；
工具可验证引用字节，但不能识别另一人伪造的“真实轨迹”。

评审校准先用以下**构造故事**，不混入运行数据：

|材料|应如何评，为什么|
|---|---|
|CVRP 14→12，分别核验可行且声明只限此解；没有此前预测|conclusion 可 supported；revision/investigation 仍 insufficient|
|Warehouse 顺序互换后成本仍 800；仍声称省钱|conclusion contradicted，即使脚本打印 PASS|
|capacity 改为 1，却复述旧合并解 12；仅索引包含旧笔记|interpretation contradicted；continuity insufficient，索引不等于读取|
|新 H 实际读旧记录，明确核对 source/input，观察不可行后修正解释并换下一行动|可支持 continuity/revision，但必须引先后原记录；只有这段故事本身不支持|
|timeout 无完整输出，结论是此次未取得足够信息|执行 incomplete；范围结论可正确，不写 solver 无收益|

工程测试：`-m pytest -q scion/scion/tests/test_p5_assessment.py`。
覆盖参考校验、实际 runner、公开导出、显式预算、缺失/错误引用/分歧；没有付费
provider 调用。真实盲评、O/M 见证和开放研究留在 P5b，P6/P7 的效果参数另行冻结。

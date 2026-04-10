# Scion 实验基线管理规范

*创建日期: 2026-04-10*
*最后更新: 2026-04-10*

---

## 1. 核心原则

**每次实验 campaign 必须从一个确定性的、可追溯的 baseline 启动。**

不允许：
- 在上一次 campaign 的产出上继续跑新 campaign
- 用被 Scion 优化过的算子作为"baseline"
- 不记录 baseline 版本就跑实验

## 2. Baseline 版本管理

### 2.1 Git Tag 命名规范

```
baseline-v1    ← 原始 6 算子，均匀权重，v3 benchmark（22 instances）
baseline-v2    ← （未来）如果手动重构了 solver/算子后的新起点
```

### 2.2 当前 Baseline

**baseline-v1**（tag: `baseline-v1`）
- 6 个算子：MoveOrder, SwapOrders, ChangeVehicleType, MergeVehicles, SplitVehicle, DestroyRebuild
- 均匀权重（0.20/0.20/0.15/0.15/0.15/0.15）
- 22 个 v3 benchmark instances（10 screening + 6 validation + 4 frozen + 2 canary）
- 位置：`surrogate/operators/` + `surrogate/registry.yaml`

### 2.3 恢复 Baseline 的方法

```bash
# 恢复 surrogate 到 baseline-v1 状态
git checkout baseline-v1 -- surrogate/operators/ surrogate/registry.yaml

# 确认恢复正确
git diff baseline-v1 -- surrogate/operators/ surrogate/registry.yaml
```

## 3. 实验 Campaign 工作流

### 3.1 启动前

```bash
# 1. 确认 surrogate baseline 干净
git diff HEAD -- surrogate/operators/ surrogate/registry.yaml
# 应该无输出（如果有，说明被上次实验污染了）

# 2. 如果被污染，恢复
git checkout baseline-v1 -- surrogate/operators/ surrogate/registry.yaml

# 3. 初始化 campaign（会从 surrogate 复制 baseline 到 workspace）
python3 -m scion.cli.main init --problem problems/warehouse_delivery/problem.yaml \
    --campaign-dir campaign_<实验标识>
```

### 3.2 运行中

Campaign 运行时，**只修改 campaign workspace 中的代码**，不修改 surrogate/ 目录。

这是 Scion 的设计保证——`WorkspaceMaterializer` 在 campaign workspace 中操作，surrogate/ 是只读引用。

### 3.3 结束后

```bash
# 记录实验环境
echo "baseline: baseline-v1" >> campaign_<实验标识>/experiment_meta.txt
echo "scion_version: $(git rev-parse --short HEAD)" >> campaign_<实验标识>/experiment_meta.txt
echo "date: $(date -Iseconds)" >> campaign_<实验标识>/experiment_meta.txt
```

## 4. API Key 安全规范

### 4.1 绝对禁止

- ❌ 在 .py / .md / .yaml / .json 文件中写入 API key
- ❌ 在 git commit message 中包含 key
- ❌ 在 exec 命令参数中直接写 key（会留在 shell history）

### 4.2 正确做法

```bash
# 通过环境变量传递（SCION_API_KEY 是 Scion LLM client 的首选变量）
export SCION_API_KEY="..."

# 或写入不被 git 追踪的 .env 文件（已在 .gitignore 中）
echo "SCION_API_KEY=..." >> .env
```

### 4.3 Scion LLM Client 的 Key 查找顺序

1. 构造函数参数 `api_key=`
2. `SCION_API_KEY`
3. `ANTHROPIC_AUTH_TOKEN`
4. `ANTHROPIC_API_KEY`

**推荐统一使用 `SCION_API_KEY`**。

## 5. 版本对比实验设计

论文化需要回答的四个问题：

| 问题 | 实验方法 |
|---|---|
| 结构搜索 alone 的收益 | baseline-v1 → v0.2 campaign（均匀权重） |
| 参数搜索 alone 的收益 | baseline-v1 + 手动权重优化（不加新算子） |
| 结构 + 参数叠加收益 | baseline-v1 → v0.2 campaign（promote 后自动权重优化） |
| 某类算子的收益来源 | ablation：去掉单个 promoted 算子，对比 frozen holdout |

**所有对比实验都必须从同一个 baseline tag 出发。**

## 6. Baseline 升级流程

如果需要创建新的 baseline（比如手动重构了 solver）：

1. 确保所有进行中的实验已完成
2. 提交 surrogate 变更
3. `git tag -a baseline-v2 -m "描述变更内容"`
4. `git push origin baseline-v2`
5. 更新本文档的 §2.2

---

*本文档是实验可复现性的保障。每次实验前必须确认 baseline 版本。*

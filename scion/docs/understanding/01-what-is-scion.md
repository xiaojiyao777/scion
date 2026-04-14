# 01 — Scion 是什么

## 名字含义

Scion = **嫁接的枝条**。好的算子改进被嫁接进 Champion Pool，延续并强化原有算法。

---

## 背景问题

有一个仓配协同优化求解器，使用 VNS（Variable Neighborhood Search）+ Solution Pool 架构。求解器由一批**算子（Operator）**驱动——每个算子是一种"扰动策略"，比如：
- 订单级：重排订单、合并同品类订单、移动订单到其他车辆
- 车辆级：新增/减少车辆、换车型、整车重建

**算子的好坏直接决定解的质量**。手工设计算子很慢，依赖工程师直觉，周期长、难以系统化。

---

## Scion 的答案

让 LLM 来：
1. 提出改进假设（"我认为这个方向有效，因为……"）
2. 生成算子代码
3. 自动跑实验
4. 统计验证是否真的更好
5. 通过则晋升进 Champion Pool

整个过程**可信、可控、可追溯**——这是 Scion 区别于简单"让 LLM 写代码"的核心。

---

## 核心设计哲学

> LLM 是不可信的创意层，所有产出必须经过严格的门控和统计验证才能生效。

具体体现：
- LLM 输出全部视为 **tainted 数据**
- 代码必须过 Contract Gate（静态检查）+ Verification Gate（运行验证）
- 晋升决策只基于数字（DecisionFeatures），不基于 LLM 的文字
- 实验结论必须统计显著（win_rate + median_delta + bootstrap CI）

---

## 系统边界

**Scion 做的：**
- 自动提假设、写代码、跑实验、做决策
- 多分支并行探索（最多 3 个）
- 可追溯的 lineage（SQLite，append-only）

**Scion 不做的：**
- 定义优化问题本身（问题定义是人的工作）
- 直接上生产（需要 shadow deployment 验证）
- 保证找到全局最优（它是在启发式设计空间里搜索，不是在解空间里）

---

## 项目结构

```
scion/
  scion/           # Python 包
    core/          # Campaign 主循环、分支状态机、决策引擎
    contract/      # Contract Gate（C1-C10 静态检查）
    verification/  # Verification Gate（动态验证）
    protocol/      # 三级实验协议
    proposal/      # LLM 客户端、Context Manager
    runtime/       # Runner（subprocess 隔离）、WorkspaceMaterializer
    lineage/       # SQLite Registry
    config/        # Pydantic 配置模型
    parameter/     # Weight Optimizer
  problems/
    warehouse_delivery/  # 仓配协同问题定义
  docs/            # 文档
  run_v3_campaign.py   # 入口脚本
```

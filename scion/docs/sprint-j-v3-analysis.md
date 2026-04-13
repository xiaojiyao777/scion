# Sprint J-v3 验证实验分析报告

*日期：2026-04-14 01:20 GMT+8*
*实验参数：30r, claude-opus-4-6, v3/v4 benchmark*
*运行时间：23:01 → 00:58 GMT+8（约 1h57min）*

---

## 一、实验结果摘要

| 指标 | 结果 |
|---|---|
| 总 branch 数 | 12 |
| 晋升次数 | 3（v2/v3/v4） |
| Abandoned | 9 |
| 进入 validation | 4 |
| 进入 frozen | 4（1次 frozen 失败） |
| 最终 champion | v4 |
| hypothesis 平均长度 | 1132 chars（不截断 ✅） |

## 二、Champion 演化

| 版本 | 新增算子 | wr | md |
|---|---|---|---|
| v1→v2 | subcategory_consolidate + subcategory_aware_swap | 1.00 | 3925K |
| v2→v3 | subcategory_destroy_rebuild | 1.00 | 3400K |
| v3→v4 | destroy_rebuild (modify, subcategory-aware) | 1.00 | 77K |

delta 从 3925K → 3400K → 77K：**清晰饱和曲线**，splits 空间被充分压缩，v4 只带来成本层面改善。

## 三、框架修复验证

- **Sprint I (stagnation 修复)**：✅ 跑满 30r 无提前终止
- **hypothesis 不截断**：✅ 平均 1132 chars（hypotheses 表）
- **Research Log v3**：✅ Block1 cache 7666→14068→17254，随晋升增长
- **Frozen holdout**：✅ global_subcat_repack (wr=0.75, md=3K) 被正确拦截

## 四、搜索行为分析

### 值得关注：global_subcat_repack frozen 失败
- screening wr=0.70 → validation wr=0.83 → frozen wr=0.75, md=3K → abandon
- Frozen holdout 正确识别边缘改进，**holdout 机制有效**

### 局部收敛期（16:18-16:42，24分钟7次 abandon）
- cost_downgrade_chain 全 tie（vehicle type 已被 change_vehicle_type 优化完）
- 5次 splits 方向新尝试全失败（splits 已接近局部最优）
- 最终通过 modify destroy_rebuild 找到突破口

### 信息注入效果
- 假设多样性好，无重复，loop detection 未触发
- 连续 abandon 期间未能快速识别"splits 方向已耗尽"→ saturation signal 在 200r 实验中发挥空间更大

## 五、结论

实验完全符合预期，所有 Sprint J 修复生效。
下一步通过 Sprint F4 200r 观察长期稳定性和 saturation 引导 cost 转向。

---

## 附：Sprint F4 Group B 生成器 bug（同次发现）

**问题**：generate_production.py 按每订单随机分 pickup_city，导致同一委托单内 44.7% 的委托单有跨 SZ/DG 混合，H2 约束强制产生不可消除 splits。

**真实数据**：同一委托单跨城市率仅 9.0%。

**修复**：pickup 改为委托单级别分配（booking_pu_idx 提前到 for loop 外）。

**影响**：Group B 前 18 次全部 abandon 根因为此 bug，已停止重新生成实例并重启。

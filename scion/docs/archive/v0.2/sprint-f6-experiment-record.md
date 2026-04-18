# Sprint F6 实验记录

*Date: 2026-04-14 18:34 → 22:57*
*Branch: v0.2-dev @ 02d9637 (Sprint M)*
*Purpose: Sprint M 修复验证 + Weight Optimization 25-eval 效果验证*

---

## 实验配置

| Group | 数据 | Protocol | SPLITS_WEIGHT | 轮数 | 启动时间 |
|---|---|---|---|---|---|
| A | 合成基线 (split_manifest.yaml) | protocol.yaml (wr≥0.60) | 100000 (默认) | 100r | 18:34 |
| B | 生产风格 (split_manifest_prod.yaml) | protocol_prod.yaml (wr≥0.55) | 100000 (默认) | 100r | 18:35 |
| C | 生产风格 (split_manifest_prod.yaml) | protocol_prod.yaml (wr≥0.55) | **1000** | 30r | 21:56 |

模型: claude-opus-4-6 via aihubmix
Weight opt: n_initial_random=8, n_iterations=16 (total 25 evals, Sprint M T5)

## 结果汇总

| | Group A | Group B | Group C |
|---|---|---|---|
| 完成时间 | 22:57 (4.4h) | 20:49 (2.2h) | 22:40 (0.7h) |
| Rounds | 98/100 | 100/100 | 30/30 |
| Champion | v4 (3 promotes) | v2 (1 promote) | v1 (0 promotes) |
| Experiments | 88 | 64 | 24 |
| C10 novelty | 9 | 31 | 3 |
| V-failures | 0 | 0 | 2 (V6_perf_guard) |
| Weight opt improved | **3/3** | 0/1 | N/A |

## Sprint M 修复验证

| Fix | A | B | C | 结论 |
|---|---|---|---|---|
| T1 Blacklist dedup | 0bl/0vf | 0/0 | 2bl/2vf=**1:1** | ✅ (C组验证, F5是2:1) |
| T2 BranchStore | 54 records | 62 | 18 | ✅ (F5全是0) |
| T3 V-fail events | 0 | 0 | **2 records** | ✅ (C组验证, F5是0) |
| T4 ChampionStore | 3 records | 1 | 0 | ✅ |
| T5 Weight opt 25次 | **3/3 improved** | 0/1 | N/A | ✅ (F5全是0/4) |
| T6 403 graceful | 未触发 | 未触发 | 未触发 | — |

## Group A 详细

### Champion 演化

1. v1→v2 (R4): ConsolidateSubcategory — frozen wr=1.0, md=3,575,000
2. v2→v3 (R9): ChainConsolidate — frozen wr=1.0, md=2,450,000
3. v3→v4 (R57): DestroyRebuild subcat-aware — frozen wr=1.0, md=500,000

### Weight Optimization

- v2: improved=1, best=100K (splits维度), 被discard(v3 promote更快)
- v3: improved=1, best=3.3K (cost维度), 47.2min, **实际生效**, marked 1 branch stale
- v4: improved=1, best=3.3K, 最终权重: consolidate_subcat(2.05) >> chain_consolidate(0.07)

## Group B 详细

- v1→v2 (R4): CostAwareRepack — frozen wr=0.75, md=55,100
- 对比F5-B SmartDownsizePair md=12,350 → **改善4.5倍**
- Weight opt v2: improved=0 (SPLITS_WEIGHT=100K 淹没 cost 信号)
- Post-promote 96轮: 60 abandon, 59/60 wr=0.0

## Group C 详细

- 0 promotions in 30r (最高 wr=0.400, 未达 0.55 threshold)
- SPLITS_WEIGHT=1K 效果: abandon wr median=0.167 (B组=0.000), cost信号更连续
- 2次 V6_perf_guard → 验证了 T1(blacklist 1:1) 和 T3(vfail events)
- 结论: 30r不够触发promote, 需更长实验或更宽松threshold

## 实验产物

- 目录: `~/research/scion-experiments/sprint-f6/`
- 日志: `group_{a,b,c}.log`
- 数据库: `group_{a,b,c}/scion.db`
- 可视化: `figures/01-04_*.png`
- Champion 快照: `group_{a,b,c}/champions/champion_v*/`

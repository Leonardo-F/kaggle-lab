# Kaggle Lab 项目进展

更新日期 2026-11-23

| 竞赛 | 当前里程碑 | 进展记录 |
| --- | --- | --- |
| Squares in Squares | 最佳 CSV 的官方 v20 本地总分为 **22.816306311**，全部 1,000 题通过验证；上一版 22.849664303 的 11-23 Kaggle 榜单为 **22.8496643031**（提交时排名 1817）。公开逐题榜还差 0.709074771，差距集中在 `n−k²` 在 11–30 的 274 题。 | [历次方案、得分和复现](competitions/squares-in-squares/docs/progress.md) |
| Google 量子电路编译 | `invsqrt` 全域 Kickmix 回放通过，单题成本估算 **447,866**。DQI 小码全域回放通过，正式尺寸的扫描模块用 **45,045** 个 Toffoli 类门。DFTHCSOS 已有 ANGLE 原型。 | [三题实验、验证范围和下一步](competitions/google-quantum-circuit-compilation/docs/progress.md) |
| Santa 2026 · The Elf Calculator | 正式 1,000 题全部回放通过，总指令数 **269,369**（比上一版 270,450 少 1,065 步，比官方示例少 **81.9%**）。新增值图改写器，并对公开前沿（128,513）做分档差距与结构分析：该分数是社区逐题最优程序的并集，剩余差距需全局共享中间值搜索。 | [解题思路、验证和后续实验](competitions/santa-2026/docs/progress.md) · [公开前沿对比分析](competitions/santa-2026/docs/frontier-analysis.md) |

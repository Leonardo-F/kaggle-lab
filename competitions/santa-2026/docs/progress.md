# Santa 2026 · 解法与实验进展

当前生产算法 V11：冻结研究全量 **158,955 步**，1,000 题独立验证合法，最长 348；较 V10 Full 的 164,306 省 5,351 步（3.26%，848 改善 / 70 持平 / 82 退化）。`r8` 单组 161,446、`basis` 单组 161,711。V11 是报告支持、未附正式 CSV 的研究记录；可下载最佳归档仍是 V10（164,306）。V8+V9 混合归档 174,884 与 V8–V11 归档择优 158,585 都只是后处理结果，不是算法版本，也不计入独立版本曲线。当前运行代码只有一套按职责组织的 V11，历史版本从 Git 提交复现。历代算法、分数、消融及复现命令见[算法演进](algorithm-evolution.md)。

## 2026-11-29 · V11 等价重构与教学系统同步

从 main `01567f3` 建立 `refactor/santa-current-solver`，把 V11 冻结研究的运行代码合并为按职责组织的单一生产求解器：

- 删除 `v9.py`/`v10.py`/`v11.py`/`rewrite.py`、`v11_frozen_fulltest/` 与七个旧内核，只保留八个冻结 C++17 内核和 `solver`/`portfolio`/`basis`/`construct`/`graph`/`schedule`/`schedule_local`/`optimize`/`common` 模块；唯一 CLI 为 `src/graph_solver.py`。
- 检查点升级为 schema 5，绑定两组组任务、输入、全部生产源码、八个内核、构建脚本、实际二进制和工具链；`--stop-after` 语义为新组任务数。旧数据库不能续跑。
- 同步教学 Markdown、互动 HTML、模拟器、架构图与成绩图、README、`AGENTS.md`、Web 构建与 CI；V11 新增完整教学章节，历史 V9/V10 章节保留原名、分数与复现提交。
- 新增 `docs/reports/v11.json`（`artifact_status: "report-only"`）并与 `docs/v11/validation.json`、`audit.json` 逐字段核对；`submissions/latest.json` 仍指向真实存在的 V10 CSV，构建器拒绝把 report-only 记录当作可下载最佳。
- 验证：四题冒烟原版/重构版均为 739 步且 CSV 字节相同；固定 Dev100 两版均为 15,948 步且输出字节相同（研究记录为 Linux/GCC 15,936，本机同工具链对照确认差异来自环境）。holdout100 与千题复跑结果见[重构验收](refactor-acceptance.md)。本次千题从官方题、全新 schema 5 检查点独立求解：**159,057 步**、1,000/1,000 合法、最长 354、4 进程墙钟约 1,378.6 秒；相对 V10 归档为 838 改善 / 81 持平 / 81 退化。与原研究 158,955 的 102 步差异来自工具链/墙钟环境，基线 worktree 的同环境千题输出与重构版**逐字节相同**（159,057、最长 354、逐题差异 0），确认差异来自环境而非重构回归。

## 2026-11-28 · V11 冻结 R16 研究结果

V11 改为两组独立候选：R8 多图组合组（`order`/`factor`/`bilayer`/`congruence` → 超图联合 MILP → 二步/三步合成）与自由基底组（`order` + 自由基底 → 三步/四步合成），两组候选逐题回放取最短。

- 正式 1,000 题：**158,955 步**、1,000/1,000 合法、最长 348；相对 V10 为 848 改善 / 70 持平 / 82 退化，共省 5,351 步（3.26%）。
- 单组：`r8` 161,446、`basis` 161,711；`r8` 严格胜 508 题、`basis` 严格胜 399 题、93 题等长。
- 固定 Dev100：15,936（V10 16,494、`r8` 16,161）。
- 2,000 个组任务，组内耗时合计约 10,464.6 秒；MILP 0.7 秒墙钟限时，跨机器复跑可能不同。
- 证据：[validation.json](v11/validation.json)、[audit.json](v11/audit.json)、[FULLTEST_REPORT.md](v11/FULLTEST_REPORT.md)；V8–V11 归档择优 158,585 见 [merged_validation.json](v11/merged_validation.json)。

## 2026-11-27 · V10 Full 合入与全量回放

V10 在 V9 的两内核/四路线/两阶段调度之上增加七个构造器和三层选择：

- **Stage 1 / joint**：四条 wide/mitm 路线全部参与调度，而不是只调度编译最短的一条；每条路线的 raw 与两轮 polish 都进入候选，按 `(nodes, length)` 排序后重新调度，严格更短才替换。
- **pressure**：`constructor_pressure` 用 `0.12·min(2,age/64)·min(4,depth)` 给字典值定价，按 `plan_cost = |P| + Σ p(外部操作数)` 选叶子和更新候选；6:3 与 6:4 两模式各试 raw/polish。
- **joint / cf**：`constructor_joint` 用 $t=ah+r, u=bh+s$ 共享枢轴，按联合代价提案；`constructor_cf` 用 $u/t$ 的连分数半收敛项生成有界比例。两者都先通过依赖完整性检查，再交给 8 序编译与 Stage 2 调度。
- **精确反馈修复**：最多两轮，统计重复计算值，枚举反推表达式补丁，按 `nodes + 0.08·excess + 0.004·area` 排序，最多 8 次编译/调度尝试；只有实际 replay 更短才接受。
- **Order Fast / Order CF**：按 `readiness(t) − 0.35·min(4, benefit(t))` 选择下一个目标；Order CF 额外对被选目标做 CF 枢轴提案。Full 在 Stage 3、order_fast、order_cf 三者中取严格最短。

正式 1,000 题结果：**V9 175,604 → V10 Stage 3 165,110 → V10 Full 164,306**；改善/持平/退化 **857/143/0**，最长 349；order_fast 胜 102 题、order_cf 胜 131 题、Stage 3 胜 767 题。逐题分数归档为 [v10-full1000-metrics.csv](reports/v10-full1000-metrics.csv)，正式报告为 [v10.json](reports/v10.json)。

固定留出集 100 题消融：V9 18,192；Stage 1 17,023；Stage 3 16,912；Stage 3+Order 16,902；Stage 3+Hybrid 16,844；Adaptive 16,874；Full **16,842**。Full 的 worker 秒数约 1,958.9（4 进程）；正式 1,000 题逐题秒数合计 18,524.7，中位数 10.44 秒。

本次工程验收实际执行：交付 CSV 全量回放 1,000/1,000=164,306（最长 349）；七个内核编译；V10/V9 CLI、检查点/恢复、独立验证；本机 10 道代表性题（含 order_fast/order_cf 胜出题，总分 1,565）和固定留出集 100 题（总分 16,842，与归档一致；本机重解 20 改善/80 持平/0 退化，归档消融记为 19/81）独立重解。4 道逐题分数差异在本机用冻结研究代码重跑后与本移植版逐程序一致，归因于工具链/容器迭代顺序。**未执行**：本次合入没有在 macOS/Apple Clang 上重跑完整 1,000 题，因此不声称独立复现 164,306；研究运行是 Linux/GCC 14.2.0 + Python 3.13.5。检查点升级为 schema 4（`v10-functional`），V9 仍可用 `--version v9`，但旧 schema 3 检查点需回到产生它的提交恢复。计划偏离与未完成项见 [V10 偏离记录](santa-v10-task-deviations.md)。

以下记录早期参考程序实验。

## 问题建模

每题的状态由当前寄存器值和已覆盖目标组成。每条指令读取两个寄存器，再写入一个寄存器，写入位置可以与输入相同。加减乘除每次均计一步，除法要求整除。每题最多 4,096 步，提交 CSV 的每个程序单元格最多 128 KiB。1,000 题的步数直接求和，任何一题非法会导致整份提交被拒绝。

例如初值为 3、目标为 9、27、81 时，先算 3×3 得到 9，再用 9×3 得到 27，最后用 9×9 得到 81。三个目标都未出现在初值中，每步最多引入一个新目标，因此这三步已达该题下界。

## 早期参考程序的求解方法

1. 先用当前寄存器中的值直接生成目标。搜索停滞时，枚举一步可达的中间值，优先选择能让多个未覆盖目标下一步变得可达的中间值。
2. 对剩余目标用多进制拆解。宽进制方案尝试 31、48、64、81、128、256 和 512，按需构造余数。需要时用 `bq − r` 代替 `bq + r`，前提是乘积不超过该题的上限。构造相邻目标时可复用商、余数和中间积。
3. 保留首次覆盖目标的指令及其依赖，然后根据后续使用重新分配寄存器，复用原本需要重新生成的数值。逐条回放，逐题保留最短的合法候选。

4. 对不足 25 个合法数值的小题，用 A* 搜索最少指令。对较大题，根据寄存器内已有的商和余数在多个进制间切换。最后回看生成的算术链，用已有数值替换只为某个结果服务的中间计算，回放后逐题选优。

## 1,000 道正式题结果

| 方案 | 总指令数 |
| --- | ---: |
| 官方示例提交 | 1,490,379 |
| 第一版多进制基线 | 425,694 |
| 第一版加中间值搜索、带符号余数及寄存器复用 | 391,003 |
| 第一版加宽进制方案 | 285,527 |
| 上一版逐题选优 | 285,288 |
| 混合进制、算术链重写与小题精确搜索 | 272,748 |
| 官方示例起点压缩（自产结果连续三轮 `--refine`） | 270,450 |
| 值图改写器（锚点 ± 偏移 + 双指令重推，迭代三轮） | 269,706 |
| 值图改写器多轮 + 逐题取最短合并 | 269,611 |
| 锚点变体搜索（跨度/方向/倍增）+ 两轮合并 | 269,474 |
| 追加变体 6/7 与倍增变体 5 后再合并 | 269,413 |
| 有理链改写 `t = (a·p + c)/q` + 合并 | 269,385 |
| 有理链 p,q 上限放宽到 256 后再合并 | 269,369 |
| 历史参考程序加入两步中间值，做共享值图搜索 | 266,406 |
| GitHub 269,369 版单独做同样搜索 | 264,773 |
| 两个共享值图搜索结果与 GitHub 基线逐题合并 | **263,575** |

早期从本地 285,288 步提交文件继续优化，少 12,540 步（4.40%）。有 951 道题变短。求解器和独立回放器均验证了全部 1,000 道题，最长程序 526 步。该分数为本地计数，待上传 Kaggle 核对。

随后改为从官方 `sample_submission`（1,490,379 步）出发：先生成一版，再以自产结果为起点连续压缩三轮，逐题保留更短程序，得到 **270,450**。1,000 题全量回放通过。该版提交为 `elf-calculator-score-270450.csv`（历史 CSV 已移出工作区，可从提交 `64db409` 取回），与官方示例逐题比较，1,000 题均为更短程序、无一逐字节相同。

## 共享值图大邻域搜索（2026-11-24）

搜索从自研的 270,771 步和 269,369 步提交分别出发。对每个值枚举之前出现的操作数，再从按位宽优先选取的 72 个候选值中构造额外的两步中间值，每个节点最多尝试 24 个此类替代项。每题运行 1,000 轮，随机扰动一小组活跃依赖并以全部目标共用的节点数择优。搜索后的图尝试三种求值顺序，每个程序回放后再与参考比较。两路输出分别为 266,406 和 264,773 步，逐题保留最短合法程序后为 **263,575** 步。正式 1,000 题通过仓库回放和独立回放，453 题较原 GitHub 基线更短，547 题持平，最长 525 步。

历史提交 CSV 为 `elf-calculator-score-263575.csv`（提交 `64db409`）。

## 公开前沿方案对比（2026-11-23）

对公开前沿提交（128,513，见 [对比分析](frontier-analysis.md)）做了逐格阅读与差距测量：该 notebook 只校验并复制一份公开的"逐题最短程序"数据集，不含求解算法。按目标位宽分档对比，我们的每题目标平均指令数在各档都约为其 1.8 倍；对 1,000 题的随机性与共享结构检验显示目标基本是随机大整数，差距来自联合搜索而非某种解析结构。

当时的值图改写器（见[历史实验代码](https://github.com/Leonardo-F/kaggle-lab/blob/378f74bda50672bc298a636a9a0032c92fd3bcf5/competitions/santa-2026/legacy/graph_polisher.py)）把程序产出的所有值当作操作数做单/双指令重推、锚点 ± 偏移重推（偏移递归构造），每步回放校验、只保留更短结果；多轮结果再逐题取最短合并。修正"锚点改写只按整题长度择优"后，对正式集迭代打磨、再做锚点变体搜索（跨度 4–16、单向/双向、`anchor*k ± gap` 倍增锚点）并逐题取最短合并，得到 **270,450 → 269,369**（少 1,081 步，−0.40%；281 题变短、719 题持平、0 题变长，最长程序 525 步），独立回放 1,000 题通过。归档为 `elf-calculator-score-269369.csv`（中间版本 269,706、269,611、269,474、269,413、269,385 同样在提交 `64db409` 中；本地 `submissions/` 只保留 V7 与 V8 的 CSV）。

各轮总步数为 269,911、269,804、269,741、269,739、269,739，逐题合并后为 269,611。各变体单独结果为 269,422–269,609，合并后为 269,474。追加变体、倍增锚点与有理链改写后，分别达到 269,413、269,385 和 269,369。

仍与公开前沿（128,513）差约 2.1 倍：该分数是社区逐题最优程序的并集，单算法难以匹配；剩余差距需要"全局共享中间值搜索"而非继续加局部改写规则。

当前独立算法的复现命令见[算法演进](algorithm-evolution.md)。

[官方题面与评分](https://www.kaggle.com/competitions/santa-2026/overview) · [数据与规则](https://www.kaggle.com/competitions/santa-2026/data)

## 2026-11-25 · V6 完整复跑

仓库版 V6 以原始题目为唯一输入，4 进程、180 轮节点搜索和 300 轮路径搜索，耗时 1015.1 秒。1,000 / 1,000 题合法，总计 **204,255 步**、最长 587 步；每题长度和输出 SHA-256 均与交接包一致。交接包的阶段消融与样本统计详见[算法演进](algorithm-evolution.md)，本次复跑证据见 [V6 报告](reports/v6.json)。结果为本地验证，未提交 Kaggle。

## 2026-11-25 · V7 完整复跑与检查点框架

仓库版 V7 只读官方 `puzzles.csv`，用 9 个进程和本轮新建的 SQLite 检查点全量求解 1,000 题，耗时 **878.73 秒**。阶段总分为 **204,255 → 200,987 → 200,034 → 199,675 → 199,675 → 198,388**；717 题改善、283 题持平、0 题变差，最长 564 步，独立回放 1,000 / 1,000 通过。生成的 CSV 与交接包内的 `elf-calculator-independent-v7.csv` **逐字节一致**（SHA-256 `0bd4c26ac3ba32c5fb6aced54e14e6269fde836dbfe671f51cbdb116eb7dacef`，本地归档为 `submissions/elf-calculator-independent-v7-score-198388.csv`），每题程序也逐条相同。

本轮同时把交接包的 `v6_trace.py` 合并为 V6 的可选 `trace=True` 返回接口，避免维护两份 V6 实现；`src/checkpoint.py` 与 `graph_solver.py` 的 `--checkpoint / --resume / --stop-after` 支持断点续跑，检查点绑定输入 SHA-256、源码 SHA-256、Python 版本和全部搜索参数，`--jobs` 可以变化。`PRAGMA integrity_check` 返回 `ok`，1,000 条记录全部重放通过。实验日志和 SQLite 只保留在本地；V7 的答案 CSV 已入库为 `submissions/elf-calculator-independent-v7-score-198388.csv`。

来源包为 `santa_v7_work_handoff_repacked_198388.zip`。60 题消融、`--retain-v6-graphs` 对照和 4 进程 2,002.7 秒的恢复耗时是交接包记录，本次没有重跑这些样本；本次复跑只读官方题目，历史 CSV 仅在求解完成后用于逐题审计。

## 2026-11-25 · V8 Final 完整复跑

仓库版 V8 Final 只读官方 `puzzles.csv`，用 9 个进程和本轮新建的 SQLite 检查点全量求解 1,000 题，耗时 **1174.13 秒**。冻结管线的阶段总分为 **198,388 → 198,374 → 195,705 → 195,090 → 194,881 → 194,819 → 194,797 → 194,444**；775 题较 V7 改善、225 题持平、0 题退化，最长 535 步，独立回放 1,000 / 1,000 通过。

本次输出与提供的 `submission_v8.csv` **逐字节一致**（SHA-256 `6f15091bcfddf4335f69126c2088696dfa7a9a3fcb9c4de6dbaa448aca1279fd`），每题程序也逐条相同；该 CSV 仅在求解完成后用于审计，未作为任何求解输入。研究包的 8 题冻结样本（`06_v8_final_lab_dev8`，1,619 步）也逐题复现。`PRAGMA integrity_check` 返回 `ok`，1,000 条记录全部重放通过。

V8 的正式管线由 `v8_rewrite`（双运算改写与图编译）、`v8_three`（三运算改写）、`v8_group`（严格／等成本成组重构）、`v8_register`（寄存器优化）和入口 `v8.py` 组成。开发期的模拟退火、共享中性重写和额外组合候选没有合入 main。来源包为 `santa_v8_research_final.zip`；包中的 100 / 60 / 28 题抽样只用于机制验证，全量成绩以本次逐题指标累加为准。

## 2026-11-25 · V8 等价重构与全量复现

在 `refactor/santa-v8` 分支上，把 `src/algorithms/` 从 14 个按版本组织的文件重构为 7 个按职责组织的模块：`common`（运算、回放、固定进制、共享 DAG 编译）、`construct`（自适应构造、反查、邻近商、乘积/模余数）、`graph`（提取、闭包、融合、路径选择）、`rewrite`（双/三运算、等成本、成组修复）、`schedule`（三种编译/调度）和 `solver`（唯一公开 `solve`）。V1/V2 等不在 V8 调用链上的重复实现删除；历史 V1–V8 由提交 `9337a354` 的独立 worktree 复现。V4/V5 两个近乎相同的构造器合并为同一参数化实现，关闭乘积与模余数开关时与 V4 完全一致；共享的值 DAG 编译器从 4 份内联副本抽为 1 个函数。文件数减少 50%，物理行数因可读排版由 2,126 增至 2,525，但运行依赖从多级版本转发压缩为功能模块 DAG。

重构后的默认入口只运行当前求解器，`--version v8` 为兼容别名；旧版本参数会明确报错并给出固定提交的 worktree 命令。检查点绑定输入、CLI、检查点、验证器与 `algorithms/` 全部源码、Python 版本和全部搜索参数，旧布局 SQLite 会被明确拒绝。

2026-11-25 用 6 个进程和新建的 SQLite 检查点从官方 `puzzles.csv` 独立全量求解 1,000 题，耗时 **2,421.59 秒**（同时另有一个 4 进程的冻结基线复跑，非等资源 benchmark）。结果 **194,444 步**、1,000/1,000 合法、最长 535 步；八阶段总分为 **198,388 → 198,374 → 195,705 → 195,090 → 194,881 → 194,819 → 194,797 → 194,444**，775 题较 V7 改善、225 题持平、0 题退化。输出 CSV 与归档 V8 **逐字节一致**（SHA-256 `6f15091bcfddf4335f69126c2088696dfa7a9a3fcb9c4de6dbaa448aca1279fd`），1000 条检查点记录全部重放通过，`PRAGMA integrity_check` 为 `ok`。冻结基线另一次全量复跑用于逐题八阶段指标对照；逐题程序、指标、测试、文件统计和命令见 [重构报告](reports/v8-refactor.json)。另用 practice 数据独立核验 200/200 题合法，40,207 步，最长 557 步，耗时 373.0 秒（8 进程）。重构只做等价迁移，没有混入 V9 算法改动。

## 2026-11-26 · V9 合入与全量独立复跑

在分支 `feat/santa-v9` 上把冻结 V9 移植进功能化模块并完成发布验收。基线 HEAD 为 `2875199`（V8 功能化布局与全量验收记录），历史 V1–V7 仍固定在提交 `9337a3549bea09257cbf36ae1f8da2cbd452942b`。

算法上，V9 用两个冻结的 C++17 原生构造内核（`algorithms/native/constructor_wide.cpp`、`constructor_mitm.cpp`，RNG 1909、每个目标反向递归深度 5、每值最多 3 条表达式）替换 V8 的 Python 构造与重写链：Stage 1 严格按 `wide 6:3 → wide 6:4 → mitm 6:3 → mitm 6:4` 四条路线构造，每条路线先用 8 个确定性顺序编译（seed 919），再经两轮 polish（每轮只评估 top 20 值）重新编译，严格更短才替换、等长保留先到路线；Stage 2 从 Stage 1 程序提取首现 DAG，用种子 202609、32 次根置换、压力三元组 `(overflow, peak, area)` 排序取前 12 个顺序，每组再试 6 种淘汰/求值策略，所有候选实际回放，只有严格更短才替换 incumbent，达到 DAG 节点下界即提前停止。冻结管线没有 LNS、全局锚点或大整数构造；`nodes` 只是固定 DAG 的下界。

工程上，`SOLVER_VERSION = "v9"` 是唯一版本权威（CLI `DEFAULT_VERSION` 引用）；`native/build.py` 在求解前构建内核到 git-ignored 的 `experiments/native-build/`，把编译器/版本/flags/源码哈希/二进制 SHA-256 写入 manifest；检查点升级为 schema 3，绑定输入 SHA、全部生产 Python、两个 `.cpp`、兼容头、`build.py`、实际二进制哈希、编译器/平台/参数，旧 V8/schema 2 检查点拒绝恢复并提示 V8 基线提交 `2875199`；`web/build/build.py` 用 AST 静态读取唯一版本字面量并把 cpp/header/build.py 纳入源码清单（普通构建不编译求解器）；模拟器回放槽位更新为 V1–V9（当前 V9，混合 CSV 用自定义标签回放）。新增独立后处理工具 `src/merge_submissions.py`，不属于求解管线。

**本次独立全量复跑（正式 1,000 题，从零）：** 分数 **175,604**、1,000/1,000 合法、最长程序 **415**；Stage 1 总分 **182,205**、Stage 2 节省 **6,601**（3.6228%）；对 Stage 1 **394 改善 / 606 持平 / 0 退化**；对 V8 **833 改善 / 30 持平 / 137 退化**，较 V8 节省 **18,840**（9.689%）。本机 Apple Clang 21.0.0（C++17、`-O3`，通过 `native/compat/bits/stdc++.h` 兼容头）+ Python 3.13.2，6 个进程，`session_elapsed_seconds` 约 **443.85 秒**，使用新 SQLite schema 3 检查点、无 resume。本机输出 CSV SHA-256 `05e7b630f9b9a26889a74e09dbc1317ece799e5d28d948ce28c02b99b0660cb8`。完整记录见 [v9.json](reports/v9.json)；逐题位宽桶与阶段对照见[算法演进](algorithm-evolution.md)。

**与冻结研究记录的对照：** 原始研究包 archive SHA-256 为 `b1d338d2…`，其全量报告 `v9_stage2_full_report.json` 记录 1,000 题、175,604、Stage1 182,205（resume 8 行、剩余 992 行 797.97 秒，Python 3.13.5/GCC 14.2 构建信息），原始研究配置/日志/耗时不能与本次本机复跑直接比较；逐题对照 CSV 与运行日志哈希见 [v9-stage2-ablation.json](reports/v9-stage2-ablation.json)。本机输出与冻结研究包 CSV（SHA-256 `5ab0b72c170272591f4d9485730b9805c82d9b2b857827bc017ab53ca3f3ce63`）**不是逐字节相同**：逐题程序 999/1000 相同，唯一差异题 `scored_0775` 两版程序等长（均 181 步）但寄存器选择不同；两阶段总分、逐题分数/节点/调度尝试数与逐题选择性差异桶完全一致。用冻结研究源码在本机重新编译运行会得到与移植版完全相同的程序，因此该差异归因于本机 Apple Clang 工具链与冻结记录 Linux GCC 工具链在等分候选平局时的顺序差异，不是移植逻辑差异。**不声称逐字节复现或"精确复现 5ab0b72"**。

**练习集与混合归档：** 练习 200 题独立复跑为 **36,045 步**、200/200 合法、最长 413、Stage 1 为 37,742、Stage 2 节省 1,697（86 改善/114 持平/0 退化），约 131.15 秒；V8 重构报告记录的练习成绩为 40,207 步。练习集是独立数据集，不能与正式题混算。V8+V9 混合归档为 **174,884 步**、最长 392：V8 严格更短 137 题、V9 胜出 863 题（其中 30 题平局按"平局取 V9"），较独立 V9 再省 720 步；由 `src/merge_submissions.py`（独立后处理工具，先完整验证两份输入再逐题取短）生成，不是算法版本、不进入正式独立版本曲线。混合 CSV SHA-256 `fe973ac4ed3ec8a587e18ce31b922daae4ec1060ad2bdc511d2130960978942a`，归档路径 `submissions/elf-calculator-merged-v8-v9-score-174884.csv`，报告 [v8-v9-merged.json](reports/v8-v9-merged.json)；与用户上传的参考混合文件 999/1000 程序相同（同 `scored_0775` 等长差异），分数与最长步数一致。

**测试、构建与验证状态（全部实际执行）：**
- Santa Python：`python3 -m unittest discover -s tests -p 'test_*.py'` → **98 tests OK**；Santa Node：`node --test tests/test_replay.cjs` → **7/7 pass**。
- 统一 Web：`python3 -m unittest discover -s web/tests -p 'test_*.py'` → **17 tests OK**；`python web/build/build.py --check` → exit 0。
- 报告构建：`python3 docs/build_report.py` → 重建 `Santa-2026-Interactive-Report.html`；`python3 docs/build_report.py --check` → exit 0（up to date）。
- 原生构建：`python3 src/algorithms/native/build.py` → 两个内核构建成功并写入 manifest；重复 `ensure_built(force=True)` 二进制 SHA 稳定。
- 其他赛题（共享 Web 构建后回归）：装箱 Python **27 tests OK**、装箱 Node **15/15 pass**、量子 Python **13 tests OK（无 skip）**（本机用 `/tmp` 临时依赖目录安装 requirements，未改动仓库）。
- 浏览器真实验收（Google Chrome 158.0.8127.88 headless，macOS 27.0.1 arm64）：模拟器页 **23/23** 项通过（V1–V9 槽位、三步教学解、BigInt、V7/V8/V9/混合 CSV 回放、自定义槽位、非法 CSV 反馈）；互动报告/统一入口/互动页 **26/26** 项通过（V9 成绩与独立曲线、混合单列、MathML、V9 章锚点、V8 重构面板、内嵌模拟器回放、390px 窄屏、`#santa`/`#squares`）。三份单文件在 `file://` 下打开且拦截全部 http(s) 请求；互动页用本地 HTTP 检查相对路径。未在 Safari/Firefox 或真实手机设备上验证。
- 归档 CSV 独立复核：V9 `175,604`、V8 `194,444`、V8+V9 混合 `174,884`，三者均 1,000/1,000 合法；`git diff --check` 通过。
- 提交链：`c404706`（V8 报告校验收尾）、`d3f4cae`（V9 功能化合入，即 [v9.json](reports/v9.json) 的 `solver_commit`），后续提交记录复现证据与文档/Web 重建。分步提交中的中间态不单独视为可发布构建，最终分支以完整测试与 `--check` 为准。

**限制与未完成项：** 175,604 是本地独立验证的指令总数，不是 Kaggle 榜单成绩，未做 Kaggle 提交；全局最优未知，`nodes` 只是固定 DAG 下界；本机工具链有 1/1000 等长程序平局差异（分数不变）；冻结 V9 未使用 LNS/锚点/大整数构造；V10 已在此后合入，见本条之后的 2026-11-27 记录；仓库内互动报告 HTML 与统一入口由根代理重建并做浏览器验收，本文档不声称已重建或已人工逐项验证。

**V8 重构任务书收尾：** 原 `docs/santa-v8-refactor-plan.md` 的收尾要点已并入本记录与[算法演进](algorithm-evolution.md)：V8 等价重构已完成并通过 1,000 题逐题/八阶段一致验收（报告 [v8-refactor.json](reports/v8-refactor.json)，固定对照 [v8.json](reports/v8.json)，代码重构提交 `0ec0ec0`，基线提交 `9337a354`、V8 功能化布局基线 `2875199`）；V9 直接从功能模块演进而非新增版本文件；全部算法从官方题目独立求解、历史答案仅用于回放与回归比较；未获明确同意不推送。该任务书在记录完成后从工作树移除，历史原文可从固定提交查看：[santa-v8-refactor-plan.md](https://github.com/Leonardo-F/kaggle-lab/blob/287519977aa85a19ef9e3074e6bfd2b9e578b5c3/competitions/santa-2026/docs/santa-v8-refactor-plan.md)。


## 2026-11-26 · V9 最终验收（Linux + GCC 参考工具链）

在 V9 合入远程 `main`（`8858a6a`）之后，从最新 main 建立本地分支 `fix/santa-v9-final-acceptance` 完成最终验收；本轮不修改冻结 V9 的搜索策略。

**原生编译器缓存修复（P0-1）：** 发现并修复 `native/build.py` 的两处真实问题——`_manifest_matches()` 不比较显式 `SANTA_CXX`（缓存 Clang 构建可能静默满足 GCC 请求），以及 `_build_locked()` 在因其他原因重建时优先复用旧 manifest 编译器。修复后显式编译器经 PATH/绝对路径/symlink 解析后拥有最高优先级；manifest schema 2 比较 resolved 路径/版本/family/flags/compat/源码与二进制哈希；显式编译器缺失或不可用会明确报错且不回退；`construct.py` 的二进制缓存按 manifest 签名失效；AppleDouble `._*` 元数据排除出源码指纹。新增 `tests/test_native_build.py` 15 个回归测试，覆盖缓存复用、Clang↔GCC 切换、显式编译器不存在/不可用、源码变化、二进制篡改、`--force`、manifest 字段冲突、检查点因编译器变化拒绝恢复等场景（本机 macOS 与 Linux GCC 双环境实际通过）。

**Linux + GCC 参考工具链全量复现（P0-2）：** Ubuntu 25.04 / Linux 6.14 aarch64（6 vCPU）/ `g++-14 (Ubuntu 14.2.0-19ubuntu2) 14.2.0` / glibc 2.41 / `libstdc++-14-dev` / Python 3.13.3；`SANTA_CXX=/usr/bin/g++-14`、`-O3 -std=c++17`、GCC 二进制 `constructor_wide 9682b6e6…`、`constructor_mitm 8379e5b3…`。全新 schema 3 检查点、6 进程、从官方 1,000 题独立求解：**175,604 步、最长 415、1,000/1,000 合法、Stage 1 182,205、Stage 2 节省 6,601（394/606/0）、耗时 443.96 秒**；检查点 1,000 条、`PRAGMA integrity_check=ok`。输出 CSV SHA-256 为 `5ab0b72c170272591f4d9485730b9805c82d9b2b857827bc017ab53ca3f3ce63`，与冻结 V9 记录**逐字节一致**；7 个位宽桶与逐题指标 0 差异。历史归档 CSV 不被替换：仓库中的 V9 CSV 仍是 macOS 独立运行的 `05e7b630…`，两者都是合法独立的 175,604 结果。

**同工具链全量等价性（P0-3）：** 在完全相同的 VM/Python/GCC/源码/flags/参数/种子下，用冻结研究实现（本地重建 GCC 二进制，耗时 429.97 秒）与当前功能化移植实现分别独立求解 1,000 题。逐题对照：最终程序 **0/1,000 差异**、Stage 1/Stage 2/DAG 节点/调度尝试/四条路线（含失败状态）全部 0 差异，两者与冻结记录互相一致，三份 CSV（冻结、参考实现、移植实现）逐字节相同；`scored_0775` 在 GCC 下三者也完全相同（181 步）。因此同工具链全量等价性验收通过，macOS 差异确认为工具链平局行为。

**归档回放与混合重建（P1-1）：** 用官方题与 `src/verify.py` 完整回放 V8 1,000/1,000=194,444（535）、V9 1,000/1,000=175,604（415）、混合 1,000/1,000=174,884（392），哈希与报告一致；用 `src/merge_submissions.py` 重建混合到临时目录，137/863/30 平局、公式错误 0、与归档文件逐字节一致。

**验收证据与 CI（P1-2/P0-4/P1-3）：** 新增 [v9-integration.json](reports/v9-integration.json) 工程验收报告（不进入 V1–V9 成绩曲线）与 `tests/test_acceptance_report.py` 一致性测试；已合入 main（`8858a6a`）的 GitHub Actions [run 45673883392](https://github.com/Leonardo-F/kaggle-lab/actions/runs/45673883392) 实际结果为 **success**，含 C++17 原生构建步骤，全部 16 个步骤通过。历史指纹抽查：`v8.json` 4/4、`v8-refactor.json` 10/10 与记录提交一致。

**文档与生成物（P1-4/P2）：** 更新本文件、赛题 README、报告目录说明、AGENTS 规则；重建互动报告与统一 Web 入口并 `--check`；按流程刷新 `web/build/santa-review.json`；`version-scores.png` 已由更新后的 `version-scores.mmd` 重新渲染为 V1–V9（不再保留"PNG 只覆盖 V1–V5"的过期说明）；`.gitignore` 增加 `._*`。

**最终测试计数（实际执行）：** 本机 macOS：Santa Python **120 tests OK**（含 7 个验收报告一致性测试、15 个原生构建缓存测试）、Santa Node 7/7、Web Python 17、装箱 Python 27 + Node 15、量子 Python 13；报告与统一入口 `--check` 均 exit 0；`git diff --check` 通过。Linux GCC 14.2.0 环境：Santa Python 同一套 **120 tests OK**（test_verify 5、test_merge 11、test_checkpoint 11、test_solver 27、test_native_build 15、test_report 44、test_acceptance_report 7）；原生构建在两种编译器下均成功。浏览器：上一轮验收中离线自动化矩阵为模拟器 23/23、报告/统一入口/互动页 26/26；本轮重建后用 Chrome 158 headless 冒烟复核通过（报告页含 V9、175,604、参考工具链复现说明与 9 条成绩条，无页面错误；统一入口可离线加载）。本轮完整 Playwright 矩阵在重建后复核时遇到 headless 会话挂起，已终止并如实记录。

**合入与 CI：** 本轮验收已合入远程 `main`（merge `0d23ea1`），GitHub Actions [run 45710069227](https://github.com/Leonardo-F/kaggle-lab/actions/runs/45710069227) 全部步骤 success。**限制：**GCC 环境为 Ubuntu 25.04/GCC 14.2.0/Python 3.13.3（冻结记录 Python 3.13.5）；浏览器仅 Chrome 158 headless；历史指纹为抽查；V9 无全局最优性证明；未开始 V10。

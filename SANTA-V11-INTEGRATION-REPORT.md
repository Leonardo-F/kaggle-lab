# Santa V11 工程合入报告

基线为远程 main 的 `c8979036ea72aa8eddb38c32a8bee1d3431e518a`。合入分支为 [feat/santa-v11-integration](https://github.com/Leonardo-F/kaggle-lab/tree/feat/santa-v11-integration)。以压缩包内 `MERGE_PROMPT.md` 为执行计划。ZIP 完整性检查通过，清单中的 803 个 SHA-256 均匹配。

| 来源 | 落点及适配 |
|---|---|
| `production/v11_frozen_fulltest/` | `competitions/santa-2026/src/algorithms/v11_frozen_fulltest/`。除 `build.sh` 外与附件逐字节相同。构建脚本支持 `SANTA_CXX` 并复用仓库的标准库头文件兼容层。 |
| 正式运行入口 | `src/algorithms/v11.py` 适配冻结两组路线。统一入口默认 V11，V9/V10 显式可选。V1–V8 保留原 Git 历史入口。带检查点的 V11 调用原官方固定分层 runner。 |
| `research_snapshots/`、`production/resume_full.sh` | 保留于用户原始 ZIP。统一入口提供空库初始化和续算。实验快照仅供研究查阅。 |
| `docs/` | `competitions/santa-2026/docs/v11/`，包括 17 轮记录、复现说明、成绩验证摘要和原始清单。 |
| 浏览器 | 赛题拥有的 `src/simulator.html` 增加默认 V11 CSV 槽位。沿用离线比较、指令回放、寄存器和目标覆盖显示。同源重建互动报告和统一入口。 |

## 成绩及证据

| 项目 | 题数及合法性 | 步数 |
|---|---:|---:|
| V10 独立，已有项目记录 | 1,000/1,000 | 164,306 |
| V11 独立，附件冻结研究运行 | 1,000/1,000 | 158,955 |
| V8 + V9 + V10 + V11 历史逐题择优，附件记录 | 1,000/1,000 | 158,585 |
| 本次 V11 独立重解固定 Dev100 | 100/100 | 15,948 |
| 同一 Dev100 的 V10 归档回放 | 100/100 | 16,494 |

附件 V11 千题结果较 V10 省 5,351 步（3.2567%），改善 848 题、持平 70 题、退化 82 题，最长 348 步。四版本历史择优归档另省 370 步，求解阶段只读取原始题目。本次 Dev100 最长 334 步，较附件 Dev100 记录 15,936 多 12 步。实际使用 Darwin arm64、Apple Clang 21.0.0、Python 3.13.2、NumPy 2.4.3、SciPy 1.17.1。工具链和 MILP 墙钟预算可能影响结果，未隔离 12 步差异的具体原因。

## 实际验证

- 用 `bash src/algorithms/v11_frozen_fulltest/build.sh` 在赛题目录编译八个构造器，全部成功。Clang 报告未限定的 `std::move` 及捕获结构化绑定扩展警告。
- 运行 `python src/graph_solver.py data/puzzles.csv --checkpoint /private/tmp/santa-v11-dev.sqlite --split dev --jobs 4 --output /private/tmp/santa-v11-dev.csv --stop-after 4`。空库运行四个组任务，完成两题 185 步。用相同输入、分层、数据库及输出路径改为 `--jobs 6 --resume`，最终完成 100 题并导出。
- 直接调用冻结 `variants/frozen17/run.py`，以 `--limit 0 --export` 请求导出未完成的 Dev 分层，返回 `refuse to export incomplete submission`，未生成文件。复用同一库改为 Holdout 分层，返回 `configuration changed`。
- `python src/verify.py /private/tmp/santa-v11-dev-puzzles.csv /private/tmp/santa-v11-dev.csv` 通过 100/100。冻结输入题库 SHA-256 为 `b0c70d849eca078a0e1cf9a4f7b47fd40b7435663f6f84de6725f84724500428`。本次导出 SHA-256 为 `53f6ecb0c62f6d87f08d05a6011574fe03ca908512448f1cc73bcdfe151c7d6e`。
- `node --test tests/test_replay.cjs` 通过 7 项。另在 Node 中加载原 HTML 的内联回放代码，逐题回放同一 Dev100 的 V11 与 V10 输出，验证指令数为 15,948 和 16,494。没有操作浏览器图形界面。
- `python -m unittest discover -s ../../web/tests -p 'test_*.py' -v` 通过 17 项。`python docs/build_report.py --check` 和 `python ../../web/build/build.py --check` 通过。

本轮未重新运行官方 1,000 题，未重新求解历史 V1–V8，未提交 Kaggle。附件没有分发 V11 成绩 CSV，因此 `submissions/latest.json` 继续引用仓库中已有可回放且可复核的 V10 全量产物。新增文件中没有官方题库、逐题答案、提交 CSV、数据库或二进制。原有 CSV 处于远程基线历史，本分支不修改这些文件。

- 自造小题验证加、减、乘和整除，覆盖目标被覆写仍有效、非整除、正整数上下限和寄存器索引越界。
- Santa 全量单元套件执行 123 项。122 项通过，原“未知版本”用例仍将已发布的 `v11` 当做未知版本，随后改用 `unreleased` 并单独验证该分支返回状态码 2。V9/V10 显式求解与 V10 检查点回归通过。

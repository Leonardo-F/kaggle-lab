# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

当前默认独立求解器是 **V11**。冻结研究运行覆盖正式 1,000 题，全部合法，得分 **158,955**，较 V10 Full 的 **164,306** 少 5,351 步（3.26%）。历史 V8 + V9 + V10 + V11 答案逐题择优为 **158,585**，1,000 题全部合法，属于独立的归档后处理。见 [V11 数学构造、消融及复现](docs/v11/README.md)。当前运行代码仅保留 V11；V1–V10 的旧实现通过 Git 历史复现，归档成绩与回放文件继续保留。158,955 是原研究记录，不是本次重构的千题复跑成绩。

## 互动算法报告

下载 [Santa-2026-Interactive-Report.html](Santa-2026-Interactive-Report.html) 后用浏览器离线打开。互动报告展示 V1–V11 的算法演进、全量成绩与当前 V11 架构，包括两组候选、超图联合、自由基底、三/四步合成和寄存器调度，并内嵌 V1–V11 程序回放模拟器。V11 只有研究报告和独立验证记录（未附 CSV），页面把它标为 report-only，不显示可下载提交；V8+V9 混合提交（174,884 步）与 V8–V11 归档择优（158,585 步）只作为后处理结果单独展示，不属于独立版本曲线。

正文唯一来源是[算法演进](docs/algorithm-evolution.md)，工程验收记录见[等价重构验收](docs/refactor-acceptance.md)。HTML 已用固定文档依赖在本机重建，`--check` 与测试保证它与 Markdown、报告数据和模拟器同步。`docs/build_report.py` 从该 Markdown、`docs/report_template.html`、`docs/reports/*.json`、`submissions/latest.json` 和原始模拟器生成报告：数学公式在构建期转成 MathML，图片内嵌为 data URI，`--check` 用于发现过期产物。构建依赖固定为 `Markdown==3.10.2` 与 `latex2mathml==3.81.1`，生成的报告不需要网络或客户端公式渲染器。

```bash
python -m pip install -r docs/requirements-docs.txt
python docs/build_report.py
python docs/build_report.py --check
```

## 离线模拟器

下载 [simulator.html](src/simulator.html)，用浏览器打开。输入初始值、目标值和数值上限后，即可逐步查看指令、计算结果和寄存器状态。结果等于目标值时会在页面标出。可复制 JSON 指令或打印结果。

在 **Python 版本回放** 区导入官方题目 CSV，再把各版本实际输出放入 V1–V11 槽位。默认选中 **V11**；选同一题号即可比较合法性、指令数和计算图规模（唯一中间值、共享值、重算步），切换版本查看寄存器并逐条回放。导入文件时会显示该 CSV 的总步数、覆盖题数、未知题号、无法解析的程序和未提供程序的题数。导入 [V10 提交 CSV](submissions/elf-calculator-independent-v10-score-164306.csv) 可逐题回放真实 V10 结果并显示 164,306 步总分。

V1–V10 是已归档 CSV 的回放槽位，V11 是当前算法槽位。页面还可添加**当前会话内**的自定义结果标签（1–40 字符、不可与已有标签重复），用于回放 V8+V9 混合提交等非算法版本结果，也可移除；自定义数据不上传、不持久化，默认槽位不可删除。自定义题由页面内置的 JavaScript 教学求解器处理，V11 回放需要导入 CLI 结果；仓库没有 V11 正式 CSV，页面不会伪造 V11 回放结果。

## 当前算法：独立求解

使用 POSIX（Linux 或 macOS）、C++17 编译器（支持 `__int128`，参考工具链 GCC）及 Python。依赖采用冻结研究环境的 NumPy/SciPy 版本，推荐 Python 3.13。官方输入放在本地 `data/`，不提交到 Git。每道题完全从其初值和目标构造候选，不读历史提交。

```bash
python -m pip install -r requirements.txt
# 可选：提前编译，CLI 也会自动检查/构建八个内核
python src/algorithms/native/build.py
python src/graph_solver.py data/puzzles.csv --jobs 4 --output experiments/current.csv
python src/verify.py data/puzzles.csv experiments/current.csv
```

### 断点与固定抽样

```bash
python src/graph_solver.py data/puzzles.csv --jobs 4 --checkpoint experiments/current.sqlite --output experiments/current.csv --stop-after 32
python src/graph_solver.py data/puzzles.csv --jobs 4 --checkpoint experiments/current.sqlite --output experiments/current.csv --resume
```

`--stop-after` 保持冻结 V11 的语义：限制新组任务数（每题两组），有该参数时不导出。`--split dev` 或 `--split holdout` 要求原始官方 CSV 的 SHA-256 完全匹配，使用独立检查点与输出文件。默认 `all` 可运行任意练习或正式输入。

检查点 schema 5 绑定输入、固定分组、生产源码、编译器、二进制、Python、NumPy/SciPy 及线程环境，重新回放并校验每个已完成组的摘要；全题完成且独立验证通过后才原子导出。旧 V9/V10 或冻结 V11 数据库不能续跑新代码。MILP 有墙钟时限，环境与负载可能改变结果。`--version v11` 作为兼容参数保留，不再支持 V9/V10 或 `--policy`。

## 源码结构

```text
src/
├── graph_solver.py              # 唯一 CLI
├── checkpoint.py                # 唯一批处理、SQLite、导出逻辑
├── verify.py                    # 独立合法性验证
├── merge_submissions.py         # 归档后处理，不进入求解流程
├── simulator.html              # 历史与当前程序回放
└── algorithms/
    ├── solver.py                # 当前组合算法、候选择优
    ├── portfolio.py             # 图构造、超图合并、MILP、局部合成
    ├── basis.py                 # 自由基底及三步/四步合成
    ├── construct.py             # 原生内核调用和图协议
    ├── graph.py                 # DAG 编译
    ├── schedule.py              # 寄存器压力调度、共享候选评价
    ├── schedule_local.py        # 调度次序局部搜索
    ├── optimize.py              # 限时超图 MILP
    ├── common.py                # 算术与内部回放
    ├── splits.json              # 原冻结分层 ID 与官方输入哈希
    └── native/                  # 八个独立 C++17 算法内核及构建
```

八个原生内核保持冻结研究源码字节一致：`order`、`factor`、`bilayer`、`congruence`、`hyper`、`synth`、`basis`、`synth_extended`。编译产物位于 `experiments/native-current/`，不入库。两个有效候选组合均保留，不把历史的 V9/V10 算法作为兜底。

详见[当前架构及迁移记录](docs/current-architecture.md)和[V11 数学构造](docs/v11/README.md)。未来算法优化直接修改职责模块，通过 Git 提交或标签保留历史，而非新增一套 `v12.py`。

## 历史归档

`submissions/` 与历史报告保持原样。本仓库没有 V11 正式提交 CSV；`submissions/latest.json` 仍指向真实存在的 V10 正式归档（164,306），不能改指不存在的文件。V11 158,955 与历史择优 158,585 的原始研究报告位于 `docs/v11/`。本次重构的基线是 main `01567f3`；历史 V1–V10 从对应 Git 提交复现，V1–V8 的固定提交详见[历史算法演进](docs/algorithm-evolution.md)。

## 测试

```bash
python -m unittest discover -s tests -v
node --test tests/test_replay.cjs
python -m unittest discover -s ../../web/tests -p 'test_*.py' -v
python docs/build_report.py --check
python ../../web/build/build.py --check
```

[历史实验与验证记录](docs/progress.md) · [公开前沿对比与搜索实验](docs/frontier-analysis.md) · [Kaggle 题面](https://www.kaggle.com/competitions/santa-2026/overview) · [数据格式](https://www.kaggle.com/competitions/santa-2026/data)

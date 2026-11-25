# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

## 互动算法报告

下载 [Santa-2026-Interactive-Report.html](Santa-2026-Interactive-Report.html) 后用浏览器离线打开。报告展示 V1–V9 的算法演进、全量成绩、V9 的四路线构造与两阶段寄存器调度，并内嵌 V1–V9 程序回放模拟器。V8+V9 混合提交（174,884 步）只作为归档后处理结果单独展示，不属于独立版本曲线。

正文唯一来源是[算法演进](docs/algorithm-evolution.md)。`docs/build_report.py` 从该 Markdown、`docs/report_template.html`、`docs/reports/*.json`、`submissions/latest.json` 和原始模拟器生成报告：数学公式在构建期转成 MathML，图片内嵌为 data URI，`--check` 用于发现过期产物。构建依赖固定为 `Markdown==3.10.2` 与 `latex2mathml==3.81.1`，生成的报告不需要网络或客户端公式渲染器。

```bash
python -m pip install -r docs/requirements-docs.txt
python docs/build_report.py
python docs/build_report.py --check
```

## 离线模拟器

下载 [simulator.html](src/simulator.html)，用浏览器打开。输入初始值、目标值和数值上限后，即可逐步查看指令、计算结果和寄存器状态。结果等于目标值时会在页面标出。可复制 JSON 指令或打印结果。

在 **Python 版本回放** 区导入官方题目 CSV，再把各版本实际输出放入 V1–V9 槽位。选同一题号即可比较合法性、指令数和计算图规模（唯一中间值、共享值、重算步），切换版本查看寄存器并逐条回放。导入文件时会显示该 CSV 的总步数、覆盖题数、未知题号、无法解析的程序和未提供程序的题数。

V1–V8 是历史结果槽位，V9 是当前独立求解器。页面还可添加**当前会话内**的自定义结果标签（1–40 字符、不可与已有标签重复），用于回放 V8+V9 混合提交等非算法版本结果，也可移除；自定义数据不上传、不持久化，默认槽位不可删除。自定义题由页面内置的 JavaScript 教学求解器处理，它与 Python/C++ V9 不是同一实现。

## 独立求解

使用 Python 3.11+ 和 C++17 编译器（需要 `__int128`；Linux 上推荐 GCC/libstdc++）。接受赛题规则后从 Kaggle 下载官方 `puzzles.csv`，放在本目录的 `data/`。官方题目数据不入库。

```bash
# 1) 求解前先显式构建两个冻结 C++17 构造内核（输出到 git-ignored 的 experiments/native-build/）
python src/algorithms/native/build.py

# 2) 当前唯一独立求解器（V9）；写到 experiments/，不覆盖已存在文件
python src/graph_solver.py data/puzzles.csv --output experiments/v9.csv --jobs 8
python src/verify.py data/puzzles.csv experiments/v9.csv

# 3) 显式版本参数与默认入口等价
python src/graph_solver.py data/puzzles.csv --version v9 --output experiments/v9-alias.csv --jobs 8

# 4) 直接复核归档的独立提交 CSV
python src/verify.py data/puzzles.csv submissions/elf-calculator-independent-v9-score-175604.csv
```

V9 本地全量 **175,604 步**，1,000 题全部通过独立回放：Stage 1 为 182,205 步，Stage 2 调度再省 6,601 步（394 题改善、606 持平、0 退化）；较 V8 Final 的 194,444 步改善 833 题、持平 30 题、退化 137 题，共省 18,840 步（9.69%）。最长程序 415 步。V8 为 194,444 步，V7 为 198,388 步。以上都是本地验证的指令总数，不是 Kaggle 榜单成绩。完整 CSV 见 [submissions/README.md](submissions/README.md)，另有[成绩索引](submissions/latest.json)、[复跑报告](docs/reports/)和[算法演进](docs/algorithm-evolution.md)。

本次 V9 从官方题目用全新 SQLite 检查点独立全量复跑：1,000/1,000 合法、175,604 步、最长 415 步；逐题程序与冻结研究记录 999/1000 相同，唯一差异题 `scored_0775` 等长（均 181 步）但寄存器选择不同。用冻结研究源码在本机重新编译运行会得到与移植版相同的程序，因此该差异归因于本机 Apple Clang 21 工具链与冻结记录 Linux GCC 在等分候选平局时的顺序差异，不是移植逻辑差异；两阶段总分、逐题分数/节点/调度尝试数和选择桶全部一致。输出 CSV SHA-256 为 `05e7b630…`，与冻结交接包的 `5ab0b72c…` 不同，未声称逐字节复现。详见 [v9.json](docs/reports/v9.json) 和 [v9-stage2-ablation.json](docs/reports/v9-stage2-ablation.json)。

V8+V9 混合提交（逐题取两份独立结果中较短程序，平局取 V9）为 **174,884 步**、最长 392 步：137 题取 V8、863 题取 V9（含 30 道平局），比独立 V9 再省 720 步。它由独立于求解器的后处理工具生成，不是算法版本，也不进入正式版本曲线：

```bash
python src/merge_submissions.py data/puzzles.csv \
  submissions/elf-calculator-independent-v8-score-194444.csv \
  submissions/elf-calculator-independent-v9-score-175604.csv \
  -o experiments/v8-v9-merged.csv --expect-score 174884
```

耗时较长的全量运行可加 SQLite 检查点；中断后用同一命令加 `--resume` 继续，未满题数不会导出 CSV：

```bash
python src/graph_solver.py data/puzzles.csv \
  --output experiments/v9.csv --checkpoint experiments/v9.sqlite --jobs 8
python src/graph_solver.py data/puzzles.csv \
  --output experiments/v9.csv --checkpoint experiments/v9.sqlite --resume --jobs 8
# 也可以先跑一小批再恢复
python src/graph_solver.py data/puzzles.csv \
  --output experiments/v9.csv --checkpoint experiments/v9.sqlite --stop-after 32
```

检查点 schema 3 绑定输入 SHA-256、CLI/检查点/验证器/`algorithms/` 全部生产 Python、两个 `.cpp` 源、兼容头、`native/build.py`、实际编译出的二进制 SHA-256、编译器身份与 flags、平台、Python 版本与求解参数。V1–V8 旧布局或 V8 功能化布局（schema 2）的 SQLite 不能续算，会提示使用原提交或新建检查点。

## 源码结构

`src/algorithms/` 按职责组织，`native/` 保存冻结的 C++17 构造内核：

| 文件 | 职责 |
|---|---|
| `common.py` | 共享算术与内部 replay 合法性检查 |
| `construct.py` | 四路线原生构造调用与严格协议解析 |
| `graph.py` | 首现值 DAG 提取 |
| `rewrite.py` | 冻结两轮 polish 图改写 |
| `schedule.py` | Stage 1 八序编译与 Stage 2 寄存器压力调度 |
| `solver.py` | 唯一公开入口 `solve`、`SOLVER_VERSION = "v9"`、冻结配置与阶段指标 |
| `native/constructor_wide.cpp` | 动态可达值字典 + 逆向残差构造内核 |
| `native/constructor_mitm.cpp` | 同上并增加全字典商邻域匹配 |
| `native/build.py` | 求解前原生构建、依赖探测与源码/二进制指纹 manifest |

`src/merge_submissions.py` 是独立的提交归档后处理工具，不属于求解管线，也不被检查点或默认 CLI 引用。

V1–V8 的历史实现保存在提交 `9337a3549bea09257cbf36ae1f8da2cbd452942b`（V8 功能化重构基线为 `2875199`）。用独立 worktree 复现旧版本，不把旧代码重新变成 main 的运行依赖：

```bash
git worktree add --detach ../kaggle-lab-santa-history 9337a3549bea09257cbf36ae1f8da2cbd452942b
cd ../kaggle-lab-santa-history/competitions/santa-2026
version=v7
python src/graph_solver.py /absolute/path/puzzles.csv --version "$version" \
  --output "experiments/${version}-rerun.csv" --jobs 8
python src/verify.py /absolute/path/puzzles.csv "experiments/${version}-rerun.csv"
```

历史 V8 等价重构的验收记录是可选的 `docs/reports/v8-refactor.json`：存在且通过一致性校验时，互动报告会展示其逐题/阶段结果；固定对照 `docs/reports/v8.json`，缺失时继续使用原始 V8 记录，不阻塞构建。

## 测试

```bash
python -m unittest discover -s tests -v
node --test tests/test_replay.cjs
python -m unittest discover -s ../../web/tests -p 'test_*.py' -v
python docs/build_report.py --check
python ../../web/build/build.py --check
```

[历史实验与验证记录](docs/progress.md) · [公开前沿对比与搜索实验](docs/frontier-analysis.md) · [Kaggle 题面](https://www.kaggle.com/competitions/santa-2026/overview) · [数据格式](https://www.kaggle.com/competitions/santa-2026/data)

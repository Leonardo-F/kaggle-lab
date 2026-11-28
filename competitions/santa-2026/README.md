# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

当前默认独立求解器是 **V11**。冻结研究运行覆盖正式 1,000 题，全部合法，得分 **158,955**，较 V10 Full 的 **164,306** 少 5,351 步（3.26%）。历史 V8 + V9 + V10 + V11 答案逐题择优为 **158,585**，1,000 题全部合法，属于独立的归档后处理。见 [V11 数学构造、消融及复现](docs/v11/README.md)。V9/V10 可显式选择，V1–V8 通过历史提交复现。

## 互动算法报告

下载 [Santa-2026-Interactive-Report.html](Santa-2026-Interactive-Report.html) 后用浏览器离线打开。报告展示 V1–V10 的算法演进、全量成绩、V9 的四路线构造与两阶段调度、V10 的七个构造器/联合调度/目标顺序，并内嵌 V1–V10 程序回放模拟器。V8+V9 混合提交（174,884 步）只作为归档后处理结果单独展示，不属于独立版本曲线。

正文唯一来源是[算法演进](docs/algorithm-evolution.md)。`docs/build_report.py` 从该 Markdown、`docs/report_template.html`、`docs/reports/*.json`、`submissions/latest.json` 和原始模拟器生成报告：数学公式在构建期转成 MathML，图片内嵌为 data URI，`--check` 用于发现过期产物。构建依赖固定为 `Markdown==3.10.2` 与 `latex2mathml==3.81.1`，生成的报告不需要网络或客户端公式渲染器。

```bash
python -m pip install -r docs/requirements-docs.txt
python docs/build_report.py
python docs/build_report.py --check
```

## 离线模拟器

下载 [simulator.html](src/simulator.html)，用浏览器打开。输入初始值、目标值和数值上限后，即可逐步查看指令、计算结果和寄存器状态。结果等于目标值时会在页面标出。可复制 JSON 指令或打印结果。

在 **Python 版本回放** 区导入官方题目 CSV，再把各版本实际输出放入 V1–V11 槽位。默认选中 **V11**；选同一题号即可比较合法性、指令数和计算图规模（唯一中间值、共享值、重算步），切换版本查看寄存器并逐条回放。导入文件时会显示该 CSV 的总步数、覆盖题数、未知题号、无法解析的程序和未提供程序的题数。导入 [V10 提交 CSV](submissions/elf-calculator-independent-v10-score-164306.csv) 可逐题回放真实 V10 结果并显示 164,306 步总分。

V1–V10 是历史结果槽位，V11 是当前默认回放槽位。页面还可添加**当前会话内**的自定义结果标签（1–40 字符、不可与已有标签重复），用于回放 V8+V9 混合提交等非算法版本结果，也可移除；自定义数据不上传、不持久化，默认槽位不可删除。自定义题由页面内置的 JavaScript 教学求解器处理，V11 回放需要导入 CLI 结果。

## V9/V10 历史独立求解

使用 Python 3.11+ 和 C++17 编译器（需要 `__int128`；Linux 上推荐 GCC/libstdc++）。接受赛题规则后从 Kaggle 下载官方 `puzzles.csv`，放在本目录的 `data/`。官方题目数据不入库。

```bash
# 1) 求解前先显式构建七个冻结 C++17 构造内核（输出到 git-ignored 的 experiments/native-build/）
python src/algorithms/native/build.py

# 2) 显式选择 V10 Full；写到 experiments/，不覆盖已存在文件
python src/graph_solver.py data/puzzles.csv --version v10 --output experiments/v10.csv --jobs 4
python src/verify.py data/puzzles.csv experiments/v10.csv

# 3) 显式版本与策略参数
python src/graph_solver.py data/puzzles.csv --version v10 --policy full --jobs 4 \
  --output experiments/v10-explicit.csv
python src/graph_solver.py data/puzzles.csv --version v9 --jobs 4 \
  --output experiments/v9.csv

# 4) 直接复核归档的独立提交 CSV
python src/verify.py data/puzzles.csv submissions/elf-calculator-independent-v10-score-164306.csv
```

V10 本地全量 **164,306 步**，1,000 题全部通过独立回放，最长 349；V9 175,604、最长 415。V10 相对 V9 改善 857 题、持平 143 题、0 退化，共省 11,298 步（6.43%）；V10 Stage 3 为 165,110，Full 再加 Order Fast/CF 再省 804 步。以上都是本地验证的指令总数，不是 Kaggle 榜单成绩。完整 CSV 见 [submissions/README.md](submissions/README.md)，另有[成绩索引](submissions/latest.json)、[V10 报告](docs/reports/v10.json)、[逐题指标](docs/reports/v10-full1000-metrics.csv)和[算法演进](docs/algorithm-evolution.md)。

**口径（重要）：** 164,306 来自用户交付的 V10 研究运行（Linux/GCC 14.2.0 + Python 3.13.5）。本次工程合入用官方题目和 `src/verify.py` 对交付 CSV 做了 1,000/1,000 全量回放，并在本机对 10 道代表性题与固定留出集 100 题做了独立重解（10 题 1,565；留出集 100 题 16,842，与归档总分一致；差异题的逐题程序与本机冻结研究实现一致）；**没有**在本次合入中重新跑完整 1,000 题，因此不声称本次合入独立复现了 164,306。V9 的 Linux/GCC 参考工具链全量复现记录仍是 175,604（与冻结记录逐字节一致），见 [v9-integration.json](docs/reports/v9-integration.json)。

V8+V9 混合提交（逐题取两份独立结果中较短程序，平局取 V9）为 **174,884 步**、最长 392 步：137 题取 V8、863 题取 V9（含 30 道平局），比独立 V9 再省 720 步。它由独立于求解器的后处理工具生成，不是算法版本，也不进入正式版本曲线：

```bash
python src/merge_submissions.py data/puzzles.csv \
  submissions/elf-calculator-independent-v8-score-194444.csv \
  submissions/elf-calculator-independent-v9-score-175604.csv \
  -o experiments/v8-v9-merged.csv --expect-score 174884
```

耗时较长的全量运行可加 SQLite 检查点；中断后用同一命令加 `--resume` 继续，未满题数不会导出 CSV：

```bash
python src/graph_solver.py data/puzzles.csv --version v10 \
  --output experiments/v10.csv --checkpoint experiments/v10.sqlite --jobs 4
python src/graph_solver.py data/puzzles.csv --version v10 \
  --output experiments/v10.csv --checkpoint experiments/v10.sqlite --resume --jobs 4
# 也可以先跑一小批再恢复
python src/graph_solver.py data/puzzles.csv --version v10 \
  --output experiments/v10.csv --checkpoint experiments/v10.sqlite --stop-after 32
```

检查点 schema 4 绑定输入 SHA-256、CLI/检查点/验证器/`algorithms/` 全部生产 Python（含 `v9.py`/`v10.py`）、七个 `.cpp` 源、兼容头、`native/build.py`、实际编译出的二进制 SHA-256、编译器身份与 flags、平台、Python 版本与求解参数（V10 含 policy）。旧 V9 schema 3 / V8 schema 2 布局不能续算，会提示使用原提交或新建检查点。

## 源码结构

`src/algorithms/` 按职责组织，`solver.py` 做显式版本分发，`native/` 保存七个冻结的 C++17 构造内核：

| 文件 | 职责 |
|---|---|
| `common.py` | 共享算术与内部 replay 合法性检查 |
| `construct.py` | 原生构造调用与严格协议解析 |
| `graph.py` | 首现值 DAG 提取 |
| `rewrite.py` | 冻结两轮 polish 图改写 |
| `schedule.py` | Stage 1 八序编译与 Stage 2 寄存器压力调度 |
| `v9.py` | 冻结 V9 管线（`--version v9`） |
| `v10.py` | V10 Full 管线（联合调度、pressure、修复、joint/cf、Order Fast/CF） |
| `solver.py` | 版本分发、`SOLVER_VERSION = "v11"`、阶段与配置 |
| `native/constructor_wide.cpp` | 动态可达值字典 + 逆向残差构造内核 |
| `native/constructor_mitm.cpp` | 同上并增加全字典商邻域匹配 |
| `native/constructor_pressure.cpp` | 年龄 × 依赖深度的压力感知构造 |
| `native/constructor_joint.cpp` | 两目标共享枢轴的联合构造 |
| `native/constructor_cf.cpp` | 连分数半收敛比例的联合构造 |
| `native/constructor_order_fast.cpp` | readiness − 共享收益的目标顺序构造 |
| `native/constructor_order_cf.cpp` | 目标顺序 + CF 枢轴联合构造 |
| `native/build.py` | 求解前七内核构建、依赖探测与源码/二进制指纹 manifest |

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

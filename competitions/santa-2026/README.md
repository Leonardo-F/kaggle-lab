# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

## 互动算法报告

下载 [Santa-2026-Interactive-Report.html](Santa-2026-Interactive-Report.html) 后用浏览器离线打开。报告展示 V1–V8 的算法演进、全量成绩、V6–V8 管线与寄存器逐步演示，并内嵌 V1–V8 程序回放模拟器。

正文唯一来源是[算法演进](docs/algorithm-evolution.md)。`docs/build_report.py` 从该 Markdown、`docs/report_template.html`、`docs/reports/*.json`、`submissions/latest.json` 和原始模拟器生成报告：数学公式在构建期转成 MathML，图片内嵌为 data URI，`--check` 用于发现过期产物。构建依赖固定为 `Markdown==3.10.2` 与 `latex2mathml==3.81.1`，生成的报告不需要网络或客户端公式渲染器。

```bash
python -m pip install -r docs/requirements-docs.txt
python docs/build_report.py
python docs/build_report.py --check
```

## 离线模拟器

下载 [simulator.html](src/simulator.html)，用浏览器打开。输入初始值、目标值和数值上限后，即可逐步查看指令、计算结果和寄存器状态。结果等于目标值时会在页面标出。可复制 JSON 指令或打印结果。

在 **Python 版本回放** 区导入官方题目 CSV，再把各版本实际输出放入 V1–V8 槽位。选同一题号即可比较合法性、指令数和计算图规模（唯一中间值、共享值、重算步），切换版本查看寄存器并逐条回放。导入文件时会显示该 CSV 的总步数、覆盖题数、未知题号、无法解析的程序和未提供程序的题数。

V1–V8 是历史结果槽位；当前 Python 求解器只有一套 V8 等价实现。页面还可添加**当前会话内**的自定义结果标签（1–40 字符、不可与已有标签重复），导入自己的 CSV 参与比较，并可移除；自定义数据不上传、不持久化，默认槽位不可删除。自定义题由页面内置的 JavaScript 教学求解器处理，它与 Python V8 不是同一实现。

## 独立求解

使用 Python 3.11+。接受赛题规则后从 Kaggle 下载官方 `puzzles.csv`，放在本目录的 `data/`。官方题目数据不入库。在赛题目录运行：

```bash
# 当前唯一求解器（V8 等价），写到 experiments/；不覆盖已存在文件
python src/graph_solver.py data/puzzles.csv --output experiments/v8-refactored.csv --jobs 8
python src/verify.py data/puzzles.csv experiments/v8-refactored.csv
# 兼容别名，与默认入口相同
python src/graph_solver.py data/puzzles.csv --version v8 --output experiments/v8-alias.csv --jobs 8
# 直接复核归档的提交 CSV
python src/verify.py data/puzzles.csv submissions/elf-calculator-independent-v8-score-194444.csv
```

V8 Final 本地全量 **194,444 步**，1,000 题全部通过独立回放：775 题较 V7 改善、225 题持平、0 题退化。V7 为 **198,388 步**（较同轮 V6 改善 717 题），V6 为 204,255 步，V5 为 216,404 步。以上都是本地验证的指令总数，不是 Kaggle 榜单成绩。V7、V8 的完整 CSV 见 [submissions/README.md](submissions/README.md)，另有[成绩索引](submissions/latest.json)、[复跑报告](docs/reports/)和[算法演进](docs/algorithm-evolution.md)。

耗时较长的全量运行可加 SQLite 检查点；中断后用同一命令加 `--resume` 继续，未满 1,000 题不会导出 CSV：

```bash
python src/graph_solver.py data/puzzles.csv \
  --output experiments/v8.csv --checkpoint experiments/v8.sqlite --jobs 8
python src/graph_solver.py data/puzzles.csv \
  --output experiments/v8.csv --checkpoint experiments/v8.sqlite --resume --jobs 8
```

检查点绑定输入、CLI/验证器/`algorithms/` 全部源码、Python 版本与求解参数。旧版 V1–V8 布局创建的 SQLite 不能续算，会提示使用原提交或新建检查点。

## 源码结构

`src/algorithms/` 按职责组织，不再按版本堆叠模块：

| 文件 | 职责 |
|---|---|
| `common.py` | 基础运算、回放、固定进制构造、值 DAG 编译 |
| `construct.py` | 自适应构造、反查、邻近商、乘积与模余数 |
| `graph.py` | 依赖图提取、闭包、共享融合与路径选择 |
| `rewrite.py` | 双/三运算重写、等成本探索、成组切断修复 |
| `schedule.py` | 三种合法编译与寄存器调度 |
| `solver.py` | 唯一公开求解流程 `solve`、`SOLVER_VERSION`、配置与阶段指标 |

V1–V8 的历史实现保存在提交 `9337a3549bea09257cbf36ae1f8da2cbd452942b`。用独立 worktree 复现旧版本，不把旧代码重新变成 main 的运行依赖：

```bash
git worktree add --detach ../kaggle-lab-santa-history 9337a3549bea09257cbf36ae1f8da2cbd452942b
cd ../kaggle-lab-santa-history/competitions/santa-2026
version=v7
python src/graph_solver.py /absolute/path/puzzles.csv --version "$version" \
  --output "experiments/${version}-rerun.csv" --jobs 8
python src/verify.py /absolute/path/puzzles.csv "experiments/${version}-rerun.csv"
```

等价重构的全量复现报告是可选的 `docs/reports/v8-refactor.json`：存在且通过一致性校验时，互动报告会展示其逐题/阶段结果；缺失时继续使用原始 V8 记录，不阻塞构建。本次只做等价重构，没有混入 V9 算法改动。

## 测试

```bash
python -m unittest discover -s tests -v
node --test tests/test_replay.cjs
python -m unittest discover -s ../../web/tests -p 'test_*.py' -v
```

[历史实验与验证记录](docs/progress.md) · [公开前沿对比与搜索实验](docs/frontier-analysis.md) · [Kaggle 题面](https://www.kaggle.com/competitions/santa-2026/overview) · [数据格式](https://www.kaggle.com/competitions/santa-2026/data)

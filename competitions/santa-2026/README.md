# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

## 互动算法报告

下载 [Santa-2026-Interactive-Report.html](Santa-2026-Interactive-Report.html) 后用浏览器离线打开。报告展示 V1–V8 的算法演进、全量成绩、V6–V8 管线与寄存器逐步演示，并内嵌 V1–V8 程序回放模拟器。更详细的数学推导见[算法演进](docs/algorithm-evolution.md)。

## 离线模拟器

下载 [simulator.html](src/simulator.html)，用浏览器打开。输入初始值、目标值和数值上限后，即可逐步查看指令、计算结果和寄存器状态。结果等于目标值时会标红。可复制 JSON 指令或打印结果。

在 **Python 版本回放** 区导入官方题目 CSV，再把各版本实际输出放入 V1–V8 槽位。选同一题号即可比较合法性、指令数和计算图规模（唯一中间值、共享值、重算步），切换版本查看寄存器并逐条回放。导入文件时还会显示该 CSV 在全部题目上的指令总数。自定义题由页面内置的 JavaScript 求解器处理。

## 独立求解

使用 Python 3.11+。接受赛题规则后从 Kaggle 下载官方 `puzzles.csv`，放在本目录的 `data/`。在赛题目录运行以下命令。统一入口默认运行 V8 Final，可用 `--version` 选择 V1–V8 中的任一版本。

```bash
# 复跑写到 experiments/（求解器不覆盖已存在文件）
python src/graph_solver.py data/puzzles.csv --version v8 --output experiments/v8-rerun.csv --jobs 8
python src/verify.py data/puzzles.csv experiments/v8-rerun.csv
# 直接复核归档的 Kaggle 提交 CSV
python src/verify.py data/puzzles.csv submissions/elf-calculator-independent-v8-score-194444.csv
```

V8 Final 本地全量 **194,444 步**，1,000 题全部通过独立回放：775 题较 V7 改善、225 题持平、0 题退化。V7 为 **198,388 步**（较同轮 V6 改善 717 题），V6 为 204,255 步，V5 为 216,404 步。以上都是本地验证的指令总数，不是 Kaggle 榜单成绩。官方题目不入库；V7、V8 的完整 CSV 已随仓库提供（见 [submissions/README.md](submissions/README.md)），另有[成绩索引](submissions/latest.json)、[复跑报告](docs/reports/)和[算法演进](docs/algorithm-evolution.md)。

耗时较长的全量运行可加 SQLite 检查点；中断后用同一命令加 `--resume` 继续，未满 1,000 题不会导出 CSV：

```bash
python src/graph_solver.py data/puzzles.csv --version v8 \
  --output experiments/v8.csv --checkpoint experiments/v8.sqlite --jobs 8
python src/graph_solver.py data/puzzles.csv --version v8 \
  --output experiments/v8.csv --checkpoint experiments/v8.sqlite --resume --jobs 8
```

[历史实验与验证记录](docs/progress.md) · [公开前沿对比与搜索实验](docs/frontier-analysis.md) · [Kaggle 题面](https://www.kaggle.com/competitions/santa-2026/overview) · [数据格式](https://www.kaggle.com/competitions/santa-2026/data)

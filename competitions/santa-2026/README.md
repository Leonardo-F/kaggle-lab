# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

## 离线模拟器

下载 [simulator.html](src/simulator.html)，用浏览器打开。输入初始值、目标值和数值上限后，即可逐步查看指令、计算结果和寄存器状态。结果等于目标值时会标红。可复制 JSON 指令或打印结果。

## 独立求解

使用 Python 3.11+。接受赛题规则后从 Kaggle 下载官方 `puzzles.csv`，放在本目录的 `data/`。在赛题目录运行以下命令。统一入口默认运行 V5，可用 `--version` 选择任一已集成版本。

```bash
python src/graph_solver.py data/puzzles.csv --version v5 --output submissions/v5-score-216404.csv --jobs 4
python src/verify.py data/puzzles.csv submissions/v5-score-216404.csv
```

V5 本地全量 **216,404 步**，1,000 题全部通过独立回放。官方题目和独立求解的完整 CSV 保存在本地，仓库提供[成绩索引](submissions/latest.json)、[复跑报告](docs/reports/)和[算法演进](docs/algorithm-evolution.md)。

在离线模拟器的 **Python 版本回放** 区导入官方题目 CSV，再将实际输出放入对应版本的槽位。选同一题号即可比较合法性和指令数，切换版本查看寄存器、命中目标或复制 JSON 指令。自定义题由页面内置的 JavaScript 求解器处理。

[历史实验与验证记录](docs/progress.md) · [公开前沿对比与搜索实验](docs/frontier-analysis.md) · [Kaggle 题面](https://www.kaggle.com/competitions/santa-2026/overview) · [数据格式](https://www.kaggle.com/competitions/santa-2026/data)

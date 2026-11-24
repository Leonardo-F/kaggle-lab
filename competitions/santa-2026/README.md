# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

## 离线模拟器

下载 [simulator.html](simulator.html)，用浏览器打开。输入初始值、目标值和数值上限后，即可逐步查看指令、计算结果和寄存器状态。结果等于目标值时会标红。可复制 JSON 指令或打印结果。

## 独立求解

使用 Python 3.11+。接受赛题规则后从 Kaggle 下载官方 `puzzles.csv`，放在本目录的 `data/`。统一入口默认运行 V1，可用 `--version` 选择任一已集成版本。

```bash
python graph_solver.py data/puzzles.csv --version v1 --output submissions/v1-score-250642.csv --jobs 4
python verify.py data/puzzles.csv submissions/v1-score-250642.csv
```

V1 本地全量 **250,642 步**，1,000 题全部通过独立回放。官方题目和独立求解的完整 CSV 保存在本地，仓库提供[成绩索引](submissions/latest.json)、[复跑报告](experiments/reports/)和[算法演进](docs/algorithm-evolution.md)。

在离线模拟器的 **Python 版本回放** 区导入官方题目 CSV，再将实际输出放入对应版本的槽位。选同一题号即可比较合法性和指令数，切换版本查看寄存器、命中目标或复制 JSON 指令。自定义题由页面内置的 JavaScript 求解器处理。

## 历史参考程序实验

使用 Python 3.11+，仅需标准库。接受竞赛规则后从 Kaggle 下载 `puzzles.csv`、`sample_submission.csv` 到本目录的 `data/`。`data/` 不入库；生成的提交存档在 `submissions/`，本地产物 `submission.csv` 被忽略。

```bash
python solve.py data/puzzles.csv --reference data/sample_submission.csv --output submission.csv --jobs 8
python solve.py data/puzzles.csv --check submission.csv
```

`--jobs` 控制并行进程数，默认 1。

对已有提交继续压缩时，将旧提交指定为参考。

```bash
python solve.py data/puzzles.csv --reference submission.csv --refine --output submission-refined.csv --jobs 8
```

`--refine` 跳过旧的构造策略，使用混合进制、小题精确搜索和算术链重写压缩参考程序。`--reference` 可选。给定参考 CSV 时，程序逐题选用更短的合法结果，指令数不会超过参考程序。练习时，将输入替换为 `data/practice_puzzles.csv` 并省略 `--reference`。

历史参考程序实验的最佳 CSV 为 **263,575** 步，正式数据 1,000 题全部通过本地回放。较上一版 269,369 步减少 5,794 步，其中 453 题更短。[完整 CSV](submissions/elf-calculator-score-263575.csv)

## 共享值图搜索

`dag_lns.py` 从已有合法程序提取有向无环值图，加入可复用的两步中间值，再成组替换依赖。它以全部目标共用的依赖节点数作为搜索成本，最后尝试三种寄存器分配顺序并回放。逐题保留最短的合法结果。[完整复现命令](docs/progress.md#共享值图大邻域搜索2026-11-24)

```bash
python dag_lns.py data/puzzles.csv --reference submissions/elf-calculator-score-269369.csv \
    --rounds 1000 --seed 20261124 --jobs 8 --output optimized.csv
python solve.py data/puzzles.csv --check optimized.csv
```

## 值图改写器

`legacy/graph_polisher.py` 把一份合法程序产出的所有值当作可用操作数，逐目标寻找更短的重新推导（单指令、双指令、锚点、隐藏锚点），循环到不动点后重新分配寄存器。每一步都用 `solve.replay` 校验，只保留更短的程序。

```bash
python legacy/graph_polisher.py data/puzzles.csv --reference submissions/elf-calculator-score-270450.csv \
    --one-sided --no-two-step --output a.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --reference a.csv --one-sided --output b.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --reference b.csv --output c.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --reference c.csv --one-sided --output d.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --reference d.csv --output e.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --merge \
    submissions/elf-calculator-score-270450.csv a.csv b.csv c.csv d.csv e.csv --output merged.csv
python legacy/graph_polisher.py data/puzzles.csv --check merged.csv
```

对正式集 1,000 题迭代打磨、再做锚点变体搜索（`--variant`、`--scaled`）并逐题取最短合并，得到 **270,450 → 269,369**（少 1,081 步，281 题变短、最长程序 525 步），`--check` 独立回放全部通过。完整命令见[进展文档](docs/progress.md)。详细测量、与公开前沿（128,513）的分档差距和结构检验见[对比分析](docs/frontier-analysis.md)。

[解题思路和验证范围](docs/progress.md) · [公开前沿对比与搜索实验](docs/frontier-analysis.md) · [Kaggle 题面](https://www.kaggle.com/competitions/santa-2026/overview) · [数据格式](https://www.kaggle.com/competitions/santa-2026/data)

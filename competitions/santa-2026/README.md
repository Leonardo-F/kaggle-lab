# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

## 离线模拟器

下载 [simulator.html](simulator.html)，用浏览器打开。输入初始值、目标值和数值上限后，即可逐步查看指令、计算结果和寄存器状态。结果等于目标值时会标红。可复制 JSON 指令或打印结果。

## 运行

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

用官方数据独立回放 1,000 道题，当前提交文件的总指令数为 **269,706**（本地计数，待上传 Kaggle 核对；上一版 270,450）。[完整 CSV](submissions/elf-calculator-score-269706.csv)

## 值图改写器

`graph_solver.py` 把一份合法程序产出的所有值当作可用操作数，逐目标寻找更短的重新推导（单指令、双指令、锚点、隐藏锚点），循环到不动点后重新分配寄存器。每一步都用 `solve.replay` 校验，只保留更短的程序。

```bash
python graph_solver.py data/puzzles.csv --reference submissions/elf-calculator-score-270450.csv --output polished.csv --jobs 8
python graph_solver.py data/puzzles.csv --check polished.csv
```

对正式集 1,000 题迭代打磨得到 **270,450 → 269,706**（少 744 步，230 题变短、0 题变长，最长程序 525 步），`--check` 独立回放全部通过。详细测量、与公开前沿（128,513）的分档差距和结构检验见[对比分析](docs/frontier-analysis.md)。

[解题思路和验证范围](docs/progress.md) · [公开前沿对比与搜索实验](docs/frontier-analysis.md) · [Kaggle 题面](https://www.kaggle.com/competitions/santa-2026/overview) · [数据格式](https://www.kaggle.com/competitions/santa-2026/data)

# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

## 运行

使用 Python 3.11+，仅需标准库。接受竞赛规则后从 Kaggle 下载数据，在本目录运行以下命令。

```bash
python solve.py /path/to/puzzles.csv --reference /path/to/sample_submission.csv --output /path/to/submission.csv
python solve.py /path/to/puzzles.csv --check /path/to/submission.csv
```

`--reference` 可选。给定参考 CSV 时，程序逐题选用更短的合法结果，指令数不会超过参考程序。练习时，将输入替换为 `practice_puzzles.csv` 并省略 `--reference`。

[解题思路和验证范围](../../docs/santa-2026.md) · [Kaggle 题面](https://www.kaggle.com/competitions/santa-2026/overview) · [数据格式](https://www.kaggle.com/competitions/santa-2026/data)

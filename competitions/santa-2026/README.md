# Santa 2026 · The Elf Calculator

用加、减、乘、整除编写最短算术程序。每题给出初始值和目标值，计算器有 48 个寄存器。每个目标只需在任一时刻出现一次，初值也算。所有中间值必须是正整数，且不得超过该题的上限。总分为 1,000 道计分题的指令数之和，越低越好。

## 离线模拟器

下载 [simulator.html](simulator.html)，用浏览器打开。输入初始值、目标值和数值上限后，即可逐步查看指令、计算结果和寄存器状态。结果等于目标值时会标红。可复制 JSON 指令或打印结果。

## 运行

使用 Python 3.11+，仅需标准库。接受竞赛规则后从 Kaggle 下载数据，在本目录运行以下命令。

```bash
python solve.py /path/to/puzzles.csv --reference /path/to/sample_submission.csv --output /path/to/submission.csv --jobs 8
python solve.py /path/to/puzzles.csv --check /path/to/submission.csv
```

`--jobs` 控制并行进程数，默认 1。

对已有提交继续压缩时，将旧提交指定为参考。

```bash
python solve.py /path/to/puzzles.csv --reference /path/to/previous-submission.csv --refine --output /path/to/refined-submission.csv --jobs 8
```

`--refine` 跳过旧的构造策略，使用混合进制、小题精确搜索和算术链重写压缩参考程序。`--reference` 可选。给定参考 CSV 时，程序逐题选用更短的合法结果，指令数不会超过参考程序。练习时，将输入替换为 `practice_puzzles.csv` 并省略 `--reference`。

用官方数据独立回放 1,000 道题，当前总指令数为 **272,748**。

[解题思路和验证范围](../../docs/santa-2026.md) · [Kaggle 题面](https://www.kaggle.com/competitions/santa-2026/overview) · [数据格式](https://www.kaggle.com/competitions/santa-2026/data)

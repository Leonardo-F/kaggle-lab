# Squares in Squares · 正方形装箱

把 `n=1…1000` 个可旋转的单位正方形放进尽可能小的轴对齐正方形，两两不得重叠。每题得分为 `L / sqrt(n) - 1`，其中 `L` 是外包边长。1,000 题得分求和，越低越好。[Kaggle 赛题](https://www.kaggle.com/competitions/squares-in-squares)

目前最佳布局的**本地官方 v20 总分为 22.923849921**。原始十进制和 pandas 数值读写两条路径均接受 1,000 题。[完整 CSV](submissions/rectangular_core-score-22.923849921.csv) · [逐题认证报告](submissions/rectangular_core-score-22.923849921-certification.json) · [上版 CSV](submissions/rectangular_core-score-22.940511772.csv) · [各版方案与得分](../../docs/squares-in-squares.md)

## 查看和导出布局

下载并打开[离线模拟器 HTML](simulator/SquarePackingStudio-standalone.html)，即可查看或导出已认证的 1,000 题和 500,500 行坐标。默认展示 810 块。点击「当前实例：重算并择优」可用命令行同款双边带构造重建布局。展开「实验性搜索」可现场枚举新的边带参数。未编辑时，模拟器按总分命名并导出与仓库逐字节相同的 CSV。编辑后导出文件名包含模拟器总分和 `-edited`。

## 重建和验证最佳解

本版从上版自研 CSV 出发，用双边带构造改善 67 题。首先枚举斜排容量发生变化的行偏移。在两条边带的接缝处也允许排布区域交叠，再通过二分图最大匹配移除最少的冲突方块。程序由几何参数计算坐标。公开 Notebook 用于了解构造思路和比较逐题边长。

在本目录生成完整 CSV 并复核。

```bash
python -m pip install -r requirements.txt
node algorithms/double_band.cjs submissions/rectangular_core-score-22.940511772.csv /tmp/packing-next.csv
python algorithms/certify.py --input /tmp/packing-next.csv --complete --workers 4 \
  --report /tmp/packing-next-certification.json
```

单题从零生成只需要方块数、两条边带宽度和角度。开启接缝交叠时，再给定外框边长的小数部分和交叠宽度。

```bash
node experiments/band_phase_search.cjs 304 2 8 76 52 /tmp/packing-304.csv
node experiments/band_phase_search.cjs --dock 551 5 5 70 70 .99 1.06 /tmp/packing-551.csv
```

## 开发与来源

整数网格可以用 `python algorithms/packing.py generate --output submissions/submission.csv` 生成，再用 `python algorithms/packing.py validate --input submissions/submission.csv --complete` 检查。开发测试使用上面的依赖。

```bash
python -m unittest discover -s experiments -v
node --test experiments/test_core.cjs
python simulator/build_standalone.py
```

模拟器源码入口为 `simulator/index.html`，单文件版由上述脚本生成。构造与模拟器代码独立实现，几何背景见 Erich Friedman 的 [单位正方形装箱综述](https://www.combinatorics.org/files/Surveys/ds7/ds7v1-1998.pdf)。未修改的官方评分器和许可说明见 [vendor/NOTICE.md](vendor/NOTICE.md)。

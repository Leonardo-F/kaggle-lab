# Squares in Squares · 正方形装箱

把 `n=1…1000` 个可旋转的单位正方形放进尽可能小的轴对齐正方形，两两不得重叠。每题得分为 `L / sqrt(n) - 1`，其中 `L` 是外包边长。1,000 题得分求和，越低越好。[Kaggle 赛题](https://www.kaggle.com/competitions/squares-in-squares)

目前最佳布局的**本地官方 v20 总分为 22.940511772**。原始十进制和 pandas 数值读写两条路径均接受 1,000 题。[完整 CSV](submissions/rectangular_core-score-22.940511772.csv) · [逐题认证报告](submissions/rectangular_core-score-22.940511772-certification.json) · [上版 CSV](submissions/rectangular_core-score-22.953899197.csv) · [各版方案与得分](../../docs/squares-in-squares.md)

## 查看和导出布局

下载并打开[离线模拟器 HTML](simulator/SquarePackingStudio-standalone.html)，即可查看或导出已认证的 1,000 题和 500,500 行坐标。默认展示 810 块。点击「当前实例：重算并择优」可用命令行同款双边带构造重建布局。展开「实验性搜索」可现场枚举新的边带参数。未编辑时，模拟器按总分命名并导出与仓库逐字节相同的 CSV。编辑后导出文件名包含模拟器总分和 `-edited`。

## 重建和验证最佳解

在本目录运行以下命令。从上一版已认证的布局出发，依次压紧旋转边带、对多个现有布局转向裁切，再做允许更大位姿变化的接触搜索。

```bash
python -m pip install scipy==1.17.0 -r requirements.txt
OPENBLAS_NUM_THREADS=1 python experiments/contact_polish.py \
  --input submissions/rectangular_core-score-22.953899197.csv \
  --output /tmp/packing-contact.csv --restart 378 418 754 810
OPENBLAS_NUM_THREADS=1 python experiments/rotated_windows.py \
  /tmp/packing-contact.csv /tmp/packing-crop.csv --witnesses --max-drop 28
OPENBLAS_NUM_THREADS=1 python experiments/contact_polish.py \
  --input /tmp/packing-crop.csv --output /tmp/packing-next.csv \
  --wide 54 69 123 129 154 236 503
python algorithms/certify.py --input /tmp/packing-next.csv --complete --workers 4 \
  --report /tmp/packing-next-certification.json
```

局部搜索含求解时间上限。仓库内的 CSV 对应已认证的固定版本。认证器用原始十进制文本和 pandas 数值读写两条路径验证完整 CSV。两条路径都通过时，报告的 `valid` 为 `true`。双边带用 `node algorithms/double_band.cjs 原始.csv 新版.csv` 重建。需要重新枚举其他构造参数时，用 C++17 编译运行 `algorithms/` 下的 `core_sweep.cpp`、`tilt_sweep.cpp` 或 `clipped_sweep.cpp`，将标准输出保存为参数表，再用相应的 `--core-witnesses`、`--tilt-witnesses` 或 `--clipped-witnesses` 指定该表。

## 开发与来源

整数网格可以用 `python algorithms/packing.py generate --output submissions/submission.csv` 生成，再用 `python algorithms/packing.py validate --input submissions/submission.csv --complete` 检查。开发测试使用上面的依赖。

```bash
python -m unittest discover -s experiments -v
node --test experiments/test_core.cjs
python simulator/build_standalone.py
```

模拟器源码入口为 `simulator/index.html`，单文件版由上述脚本生成。构造与模拟器代码独立实现，几何背景见 Erich Friedman 的 [单位正方形装箱综述](https://www.combinatorics.org/files/Surveys/ds7/ds7v1-1998.pdf)。未修改的官方评分器和许可说明见 [vendor/NOTICE.md](vendor/NOTICE.md)。

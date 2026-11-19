# Squares in Squares · 正方形装箱

把 `n=1…1000` 个可旋转的单位正方形放进尽可能小的轴对齐正方形，两两不得重叠。每题得分为 `L / sqrt(n) - 1`，其中 `L` 是外包边长。1,000 题得分求和，越低越好。[Kaggle 赛题](https://www.kaggle.com/competitions/squares-in-squares)

目前最佳布局的**本地官方 v20 总分为 23.040802440**。原始十进制和 pandas 数值读写两条路径均接受 1,000 题。[完整 CSV](submissions/rectangular_core.csv) · [逐题认证报告](submissions/rectangular_core-certification.json) · [各版方案与得分](../../PROGRESS.md)

## 查看和导出布局

下载并打开 [离线模拟器 HTML](simulator/SquarePackingStudio-standalone.html)，导入上面的 CSV 查看最佳布局。模拟器默认使用整数网格，内置旋转构造和小规模局部搜索。完整导出始终覆盖全部 1,000 题，含 500,500 行数据，字段为 `id,n,square_id,x,y,angle`，坐标取方块中心，角度用弧度。模拟器会拦截不确定的旋转接触。提交前用官方评分器验证最终 CSV。

## 重建和验证最佳解

在本目录运行。生成器使用 Python 标准库和仓库内的两份参数表。安装依赖仅用于官方认证。

```bash
python algorithms/core_search.py --output /tmp/rectangular_core.csv --manifest /tmp/core_manifest.json
python -m pip install -r requirements.txt
python algorithms/certify.py --input /tmp/rectangular_core.csv --complete --workers 4 --report /tmp/core_certification.json
```

生成器逐题比较网格、旋转方形核心、偏置与变角度斜带、旋转矩形核心。矩形核心由 `p × q` 个方块整体旋转 45°，四角分别填入轴对齐的阶梯，外侧可补整行或整列。枚举器消去核心中心坐标，求出固定构造的最小外包边长。删去外围方块可把布局用于较小的题，沿右边和上边补成 L 形可把布局迁移到较大的题。

`core_search.py --mode baseline` 可重建 23.445523069 版，`--mode square` 可重建只允许方形核心的对照。需要重新枚举参数时，编译运行 `algorithms/core_sweep.cpp` 和 `algorithms/tilt_sweep.cpp`，将输出分别通过 `--core-witnesses` 和 `--tilt-witnesses` 传给生成器。

## 开发与来源

```bash
python -m unittest discover -s experiments -v
node --test experiments/test_core.cjs
python simulator/build_standalone.py
```

模拟器源码入口为 `simulator/index.html`，单文件版由上述脚本生成。构造与模拟器代码独立实现，几何背景见 Erich Friedman 的 [单位正方形装箱综述](https://www.combinatorics.org/files/Surveys/ds7/ds7v1-1998.pdf)。未修改的官方评分器和许可说明见 [vendor/NOTICE.md](vendor/NOTICE.md)。

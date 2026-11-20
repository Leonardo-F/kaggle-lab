# Squares in Squares · 正方形装箱

把 `n=1…1000` 个可旋转的单位正方形放进尽可能小的轴对齐正方形，两两不得重叠。每题得分为 `L / sqrt(n) - 1`，其中 `L` 是外包边长。1,000 题得分求和，越低越好。[Kaggle 赛题](https://www.kaggle.com/competitions/squares-in-squares)

目前最佳布局的**本地官方 v20 总分为 22.994307851**。原始十进制和 pandas 数值读写两条路径均接受 1,000 题。[完整 CSV](submissions/rectangular_core.csv) · [逐题认证报告](submissions/rectangular_core-certification.json) · [各版方案与得分](../../docs/squares-in-squares.md)

## 查看和导出布局

下载并打开 [离线模拟器 HTML](simulator/SquarePackingStudio-standalone.html)，导入上面的 CSV 查看最佳布局。模拟器默认使用整数网格，内置旋转构造和小规模局部搜索。完整导出始终覆盖全部 1,000 题，含 500,500 行数据，字段为 `id,n,square_id,x,y,angle`，坐标取方块中心，角度用弧度。模拟器会拦截不确定的旋转接触。操作保存在页面内存中，关闭前请导出。提交前用官方评分器验证最终 CSV。

## 重建和验证最佳解

在本目录运行。生成器使用 Python 标准库和仓库内的参数表。安装依赖仅用于官方认证。

```bash
python algorithms/core_search.py --output /tmp/rectangular_core.csv --manifest /tmp/core_manifest.json
python -m pip install -r requirements.txt
python algorithms/certify.py --input /tmp/rectangular_core.csv --complete --workers 4 --report /tmp/core_certification.json
```

认证器用原始十进制文本和 pandas 数值读写两条路径验证完整 CSV。两条路径都通过时，报告的 `valid` 为 `true`。需要重新枚举参数时，用 C++17 编译运行 `algorithms/` 下的 `core_sweep.cpp`、`tilt_sweep.cpp` 或 `clipped_sweep.cpp`，将标准输出保存为参数表，再用相应的 `--core-witnesses`、`--tilt-witnesses` 或 `--clipped-witnesses` 指定该表。

## 开发与来源

整数网格可以用 `python algorithms/packing.py generate --output submissions/submission.csv` 生成，再用 `python algorithms/packing.py validate --input submissions/submission.csv --complete` 检查。开发测试使用上面的依赖。

```bash
python -m unittest discover -s experiments -v
node --test experiments/test_core.cjs
python simulator/build_standalone.py
```

模拟器源码入口为 `simulator/index.html`，单文件版由上述脚本生成。构造与模拟器代码独立实现，几何背景见 Erich Friedman 的 [单位正方形装箱综述](https://www.combinatorics.org/files/Surveys/ds7/ds7v1-1998.pdf)。未修改的官方评分器和许可说明见 [vendor/NOTICE.md](vendor/NOTICE.md)。

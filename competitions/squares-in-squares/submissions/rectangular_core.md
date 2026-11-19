# 旋转矩形核心与独立四角阶梯

## 实验结果

| 搜索范围 | 本地官方 v20 总分 ↓ | 边长缩小的题数 |
| --- | ---: | ---: |
| 变角度斜带与偏心方形核心基线 | 23.445523069 | — |
| 同一枚举框架，仅允许方形核心 | 23.445523069 | 0 |
| 允许方形和长方形核心 | **23.040802440** | **231** |

总分降低 **0.404720630**，约 **1.73%**。231 题中，203 题来自矩形构造或直接删块，28 题来自 L 形外扩。按边长差超过 (10^{-6}) 统计。对照组重新生成的 CSV 与 23.445523 版逐字节一致。两组共享角度、容器范围、阶梯和外侧补行列的限制，允许长方形时扫描的尺寸组合更多。C++ 在同一次运行中计算两组，合计约 1.9 秒。

| 方块数 | 原边长 | 新边长 | 核心尺寸 |
| ---: | ---: | ---: | --- |
| 18 | 4.884210 | 4.828427 | 1×4 |
| 19 | 4.974874 | 4.914214 | 2×4 |
| 29 | 6.000000 | 6.000000 | 整数网格 |
| 41 | 7.000000 | 6.949748 | 2×7 |
| 52 | 7.778175 | 7.707107 | 1×8 |
| 988 | 31.977020 | 31.949749 | 7×38 |

[提交 CSV](rectangular_core.csv) 覆盖 (n=1\ldots1000)，包含 500,500 行。未经修改的官方 v20 评分器在原始十进制和 pandas 数值读写两条路径上均接受全部 1,000 题，每题边长均小于或等于基线。提交文件 SHA-256 为 `6a1c0419f24973d7d0f490b957e36bb7d318227a80ccda84ea0f202e1edce9ec`。线上成绩待 Kaggle 实际评分。[逐题验证报告](rectangular_core-certification.json)

## 构造

把 (p\times q) 个单位正方形整体旋转 45°，放入内矩形。四角各放一个轴对齐的阶梯，深度为 (d) 时放入 (d(d+1)/2) 块。允许在右边和上边补整列或整行，合计最多两条。41 块的布局由中间 14 块加四角的 (10+1+1+15) 块组成，理想边长是 (2+7/\sqrt2)。

固定尺寸和阶梯深度后，以 (L) 为外边长，((x,y)) 为核心中心。四条核心边平行于 (x+y) 或 (y-x) 的等值线。左下角深度若为正，就需要 (x+y\ge d+1+p/\sqrt2)。其余三个角给出对应约束。相邻角的阶梯深度之和受公共边的长度限制。把矩形边界与四角约束交在一起，先消去 (y-x)，再消去 (x+y)，即可从几条线性不等式直接算出最小 (L)。该公式对固定的尺寸和阶梯成立。枚举器比较每种可行容量，生成器再择优合并、删块和外扩。程序独立生成坐标。

## 29 块局部搜索

从已生成的 28 或 29 块布局开始，每次重新插入一个小邻域的方块，允许方块独立转动。优化目标是分离轴检测得到的重叠量与越界量的平方和。对目标边长 5.9899 使用了 4 个随机种子，每个 128 次重启，最低目标函数值约为 (7.29\times10^{-6})，仍存在重叠或越界，最终 CSV 保留边长 6 的格点布局。公开目录给出的已知可行边长约为 5.933833，适合作为后续多倾角拓扑搜索的参照。[29 块公开记录](https://squaremath.org/cases/29.html)

## 复现

以下命令在 `competitions/squares-in-squares` 下运行。生成器直接读取仓库中附带的两份参数表，可以跳过第一、二行。使用 `--mode square` 可生成方形核心对照，使用 `--mode baseline` 可重建 23.445523 版。

```bash
c++ -O3 -std=c++17 algorithms/core_sweep.cpp -o core_sweep
./core_sweep > /tmp/core_witnesses.tsv
python algorithms/core_search.py --output /tmp/rectangular_core.csv --manifest /tmp/core_manifest.json
python -m pip install -r requirements.txt
python algorithms/certify.py --input /tmp/rectangular_core.csv --complete --workers 4 --report /tmp/core_certification.json
```

比较本机新扫出的参数时，在生成器加上 `--core-witnesses /tmp/core_witnesses.tsv`。

```bash
python -m pip install numpy==2.3.5 scipy==1.17.0
for seed in 29 3029 4129 81129; do
  python algorithms/refine_small.py /tmp/rectangular_core.csv "/tmp/n29-${seed}.json" \
    --seed "$seed" --target 5.9899 --attempts 128
done
```

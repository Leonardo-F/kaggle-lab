# 正方形装箱进展

[项目进展](../PROGRESS.md) · [赛题 README](../competitions/squares-in-squares/README.md) · [早期策略笔记](competition-strategies/01-square-packing.md)

正方形装箱目前的最好总分是 **23.040802440**。相对最初的整数网格 **28.937669917**，下降 **5.896867477**（约 **20.38%**）。最终 CSV 包含 500,500 行，模拟器重算了全部 1,000 题，官方 v20 评分器也在原始十进制和 pandas 数值读写两条本地路径上接受了全部布局。[最新版提交 CSV](../competitions/squares-in-squares/submissions/rectangular_core.csv) · [逐题认证报告](../competitions/squares-in-squares/submissions/rectangular_core-certification.json)

## 方案与历次总分

总分是把 1–1000 块的每道题分别计算 `L / √n − 1` 后求和，其中 `L` 是外包正方形的边长。分数越低越好。

「模拟器重跑」使用仓库中浏览器模拟器共用的 JavaScript 引擎 `packing-core.js`，对每个布局重新检查重叠、计算边长并合计。「官方 v20 本地」是未修改的赛题评分器在本地对完整 CSV 的验证结果。下表按九位小数展示，两种方法只在末尾的浮点舍入上有差别。Kaggle 榜单成绩暂无记录。

| 阶段 | 方案 | 模拟器重跑 ↓ | 官方 v20 本地 ↓ |
| --- | --- | ---: | ---: |
| 11-09 · 模拟器 v0.1 | 首个交互画布，整列排放的轴对齐网格，支持拖动和旋转。表中为默认网格的回放总分。 | 28.937669917 | 同一网格于 11-12 认证 |
| 11-10 · 模拟器 v0.2 | 中文离线单文件、完整 CSV 导出及更严格的本地几何校验。默认布局沿用网格。 | 28.937669917 | 28.937669917 |
| 11-12 · 模拟器 v0.3 与旋转构造 | 枚举 45° 方形核心与四角方阵/阶梯，删去外围方块以复用布局。可在模拟器里直接运行，改善 162 题。 | 26.993155239 | 26.993155239 |
| 11-19 · 偏置对角带 + L 形外扩 | 枚举 45° 斜排带、偏置和两角阶梯，用右边与上边的方块把有效布局迁移到更大的题。较上版改善 352 题。 | 23.634514815 | 23.634514815 |
| 11-19 · 变角度斜带 + L 形外扩 | 扫描不同倾角，允许各行沿斜带方向平移，并逐题保留更紧的布局。较上版改善 74 题。 | 23.592926108 | 23.592926108 |
| 11-19 · 再加偏心方形核心 | 把旋转方阵移到内矩形，四角填阶梯，补一列形成方形容器。与变角度斜带取优，较 23.634515 版累计改善 144 题。 | 23.445523069 | 23.445523069 |
| 11-19 · 矩形核心 + 独立四角阶梯 | 将核心推广为旋转的长方形，四角阶梯深度分别枚举。消去中心坐标求出固定构造的最小边长，再尝试删块和外扩。较上版改善 231 题。 | **23.040802440** | **23.040802440** |

模拟器 v0.3 自带网格和旋转构造。后续版本由 Python/C++ 生成，模拟器可以导入 CSV，查看每道题的摆放和本地分数。「模拟器重跑」用同一套几何接口复测了这些 CSV。

### 同轮对照

| 对照方案 | 模拟器重跑 ↓ | 官方 v20 本地 ↓ | 对应基线 |
| --- | ---: | ---: | --- |
| 仅加 L 形外扩 | 24.607212772 | 24.607212772 | 11-12 旋转构造 |
| 仅加 45° 偏置斜带 | 23.832669775 | 23.832669775 | 11-12 旋转构造 |
| 独立四角阶梯枚举中只允许方形核心 | 23.445523069 | 23.445523069 | 11-19 偏心方形核心。两份 CSV 逐字节相同。 |

## 复现历次结果

在赛题目录使用下表中的生成器。最佳版本的完整生成与认证命令见[赛题 README](../competitions/squares-in-squares/README.md#重建和验证最佳解)。

| 布局 | 重建入口 |
| --- | --- |
| 整数网格 | `algorithms/packing.py generate` |
| 旋转构造 | `algorithms/constructions.py` |
| 偏置对角带与 L 形外扩 | `algorithms/strip_search.py`，默认 `--method combined`。用 `--method border` 或 `--method diagonal` 重现单项对照。也可查看[该版完整 CSV](https://github.com/Leonardo-F/kaggle-lab/blob/2829780ec757ee92970173512dcadb26e0eff887/competitions/squares-in-squares/submissions/strip_search.csv)。 |
| 变角度斜带 | `algorithms/tilt_search.py` 的清单字段 `score_strip_with_border` 记录该阶段的独立得分。 |
| 偏心方形核心及方形对照 | `algorithms/core_search.py --mode baseline` 与 `--mode square` |
| 矩形核心 | `algorithms/core_search.py`，默认 `--mode rectangular` |

各生成器的输入、输出与参数见 `--help`。也可查看[早期网格与旋转构造认证](competition-strategies/2026-11-12-results.json)和[斜带与外扩认证](competition-strategies/strip-search-results.json)。

在仓库根目录执行下列命令可用模拟器核心重算当前 CSV 的总分。对照时可更换 CSV 路径。

```bash
node - competitions/squares-in-squares/submissions/rectangular_core.csv <<'JS'
const fs = require('node:fs');
const core = require('./competitions/squares-in-squares/simulator/packing-core.js');
const layouts = core.parseCsv(fs.readFileSync(process.argv[2], 'utf8'));
if (layouts.size !== core.MAX_N) throw Error('CSV 必须覆盖全部 1,000 题');
let total = 0;
for (let n = 1; n <= core.MAX_N; n++) {
  const result = core.evaluate(layouts.get(n));
  if (!result.valid) throw Error(`第 ${n} 题未通过模拟器检查`);
  total += result.score;
}
console.log(total.toFixed(9));
JS
```

## 构造细节与补充实验

### 旋转核心、偏置斜带和 L 形外扩

早期旋转构造枚举 45° 方形核心，在四角放方阵或阶梯。删去外围方块后，布局可以用于较小的题。偏置斜带改用 45° 的整行方块和两个对角阶梯，按半整数与整数除以根号二的断点枚举行长。若 `n` 块的布局边长为 `L`，令 `k=floor(L)`，就可沿右边和上边加宽 `t`，在边长 `L+t` 内再放入 `2kt+t²` 块。[偏置斜带与外扩的完整推导](https://github.com/Leonardo-F/kaggle-lab/blob/2829780ec757ee92970173512dcadb26e0eff887/docs/competition-strategies/strip-search.md)

### 矩形核心与独立四角阶梯

把 `p × q` 个单位正方形整体旋转 45°，放入内矩形。四角各放一个轴对齐的阶梯，深度为 `d` 时放入 `d(d+1)/2` 块。允许在右边和上边补整列或整行，合计最多两条。41 块的布局由中间 14 块加四角的 `10+1+1+15` 块组成，理想边长是 `2+7/√2`。

固定尺寸和阶梯深度后，以 `L` 为外边长，`(x,y)` 为核心中心。四条核心边平行于 `x+y` 或 `y-x` 的等值线。左下角深度若为正，就需要 `x+y ≥ d+1+p/√2`。其余三个角给出对应约束。相邻角的阶梯深度之和受公共边的长度限制。把矩形边界与四角约束交在一起，先消去 `y-x`，再消去 `x+y`，即可从几条线性不等式直接算出最小 `L`。该公式对固定的尺寸和阶梯成立。枚举器比较每种可行容量，生成器再择优合并、删块和外扩。程序独立生成坐标。

与总分为 23.445523069 的方形核心对照相比，矩形核心版改进 231 题。其中 203 题来自矩形构造或直接删块，28 题来自 L 形外扩。18 块的边长从 4.884210 降为 4.828427，41 块从 7 降为 6.949748。对比门槛为边长缩小超过 10⁻⁶。

### 29 块局部搜索

从已生成的 28 或 29 块布局开始，每次重新插入一个小邻域的方块，允许方块独立转动。优化目标是分离轴检测得到的重叠量与越界量的平方和。对目标边长 5.9899 使用了 4 个随机种子，每个 128 次重启，最低目标函数值约为 7.29 × 10⁻⁶，仍存在重叠或越界，最终 CSV 保留边长 6 的格点布局。公开目录给出的已知可行边长约为 5.933833，适合作为后续多倾角拓扑搜索的参照。[29 块公开记录](https://squaremath.org/cases/29.html)

在赛题目录将最佳 CSV 生成到 `/tmp/rectangular_core.csv` 后复现。

```bash
python -m pip install numpy==2.3.5 scipy==1.17.0
for seed in 29 3029 4129 81129; do
  python algorithms/refine_small.py /tmp/rectangular_core.csv "/tmp/n29-${seed}.json" \
    --seed "$seed" --target 5.9899 --attempts 128
done
```

### 矩形内的 45° 斜带与整数边框

固定外边长后，枚举一侧整数宽的网格边框、斜带行数和两个角的余量，在长方形内部按行计算容量。令整数网格边长为 k，扫描 k = 2…31。394 个方块数有容量超过 k² 的候选。按既有中心外扩系数 1.00000004 和 10⁻⁶ 的改进门槛逐题比较，新增改进 **0 题**，继续使用上版 CSV，总分 **23.040802440**。在装箱目录运行以下命令可重新生成候选表，各列依次为题号、理想边长、容量、边框宽、斜带行数、下侧余量。[枚举器](../competitions/squares-in-squares/algorithms/framed_strip_sweep.cpp)

~~~bash
c++ -O3 -std=c++17 algorithms/framed_strip_sweep.cpp -o /tmp/framed-strip
/tmp/framed-strip > /tmp/framed-strip.tsv
~~~

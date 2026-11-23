# 正方形装箱进展

[项目进展](../PROGRESS.md) · [赛题 README](../competitions/squares-in-squares/README.md) · [早期策略笔记](competition-strategies/01-square-packing.md)

正方形装箱目前的自研最好总分是 **22.849664303**。相对最初的整数网格 **28.937669917**，下降 **6.088005614**（约 **21.04%**）。最终 CSV 包含 500,500 行，模拟器重算了全部 1,000 题，官方 v20 评分器也在原始十进制和 pandas 数值读写两条本地路径上接受了全部布局。[最新版提交 CSV](../competitions/squares-in-squares/submissions/rectangular_core-score-22.849664303.csv) · [逐题认证报告](../competitions/squares-in-squares/submissions/rectangular_core-score-22.849664303-certification.json)

## 方案与历次总分

总分是把 1–1000 块的每道题分别计算 `L / √n − 1` 后求和，其中 `L` 是外包正方形的边长。分数越低越好。

「模拟器重跑」使用仓库中浏览器模拟器共用的 JavaScript 引擎 `packing-core.js`，对每个布局重新检查重叠、计算边长并合计。「官方 v20 本地」是未修改的赛题评分器在本地对完整 CSV 的验证结果。下表按九位小数展示，两种方法只在末尾的浮点舍入上有差别。11-20 版已在 Kaggle 得到 **22.9943078507**，提交时用户报告排名 **1825**。

| 阶段 | 方案 | 模拟器重跑 ↓ | 官方 v20 本地 ↓ |
| --- | --- | ---: | ---: |
| 11-09 · 模拟器 v0.1 | 首个交互画布，整列排放的轴对齐网格，支持拖动和旋转。表中为默认网格的回放总分。 | 28.937669917 | 同一网格于 11-12 认证 |
| 11-10 · 模拟器 v0.2 | 中文离线单文件、完整 CSV 导出及更严格的本地几何校验。默认布局沿用网格。 | 28.937669917 | 28.937669917 |
| 11-12 · 模拟器 v0.3 与旋转构造 | 枚举 45° 方形核心与四角方阵/阶梯，删去外围方块以复用布局。可在模拟器里直接运行，改善 162 题。 | 26.993155239 | 26.993155239 |
| 11-19 · 偏置对角带 + L 形外扩 | 枚举 45° 斜排带、偏置和两角阶梯，用右边与上边的方块把有效布局迁移到更大的题。较上版改善 352 题。 | 23.634514815 | 23.634514815 |
| 11-19 · 变角度斜带 + L 形外扩 | 扫描不同倾角，允许各行沿斜带方向平移，并逐题保留更紧的布局。较上版改善 74 题。 | 23.592926108 | 23.592926108 |
| 11-19 · 再加偏心方形核心 | 把旋转方阵移到内矩形，四角填阶梯，补一列形成方形容器。与变角度斜带取优，较 23.634515 版累计改善 144 题。 | 23.445523069 | 23.445523069 |
| 11-19 · 矩形核心 + 独立四角阶梯 | 将核心推广为旋转的长方形，四角阶梯深度分别枚举。消去中心坐标求出固定构造的最小边长，再尝试删块和外扩。较上版改善 231 题。 | 23.040802440 | 23.040802440 |
| 11-20 · 变长 45° 斜排 | 四角保留阶梯，每行斜排按剩余宽度独立取长并居中。较上版改善 54 题，其中 271 块首次小于边长 17。 | 22.994307851 | 22.994307851 |
| 11-23 · 多起点接触优化 | 用接触约束的线性化压紧已有布局，17 题直接改善，删块和 L 形外扩再改善 4 题。 | 22.979222174 | 22.979222174 |
| 11-23 · 双倾斜边带 | 底边和左边分别排入倾斜方块，两端可保留轴对齐方块，右上角补整齐网格。逐题取优后缩短 46 题。 | 22.953899197 | 22.953899197 |
| 11-23 · 旋转裁切与接触优化 | 从已有布局裁出更紧的子布局，再压紧接触与试加网格边框。逐题取优后缩短 14 题。 | 22.940511772 | 22.940511772 |
| 11-23 · 行偏移与接缝匹配 | 枚举行容量变化的偏移点，允许两条边带交叠，并移除最少的冲突方块。较上版改善 67 题。 | 22.923849921 | 22.923849921 |
| 11-23 · 双边带联合搜索 | 联合比较两侧边带的倾角、行偏移与交叠宽度，用二分图匹配处理接缝。较上版改善 59 题。 | 22.906698393 | 22.906698393 |
| 11-23 · 接触约束压紧与扰动重启 | 固定角度修复几何接触，小题增加不同布局起点。两路自研输出逐题择优并外扩，改善 102 题。 | **22.849664303** | **22.849664303** |

模拟器默认打开最新版认证 CSV，离线单文件内嵌同一文件。网页与 Node 共用双边带坐标生成、外扩和择优参数。已有 Python 接触优化的结果通过认证 CSV 载入。

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
| 矩形核心 | `algorithms/core_search.py --mode rectangular` |
| 四角阶梯与变长斜排 | `algorithms/core_search.py`，默认 `--mode clipped`。用 `clipped_sweep.cpp` 重新搜索各行的相位和四角深度。 |
| 多起点接触优化 | `experiments/contact_polish.py`，使用赛题 README 中的目标列表。 |

各生成器的输入、输出与参数见 `--help`。也可查看[早期网格与旋转构造认证](competition-strategies/2026-11-12-results.json)和[斜带与外扩认证](competition-strategies/strip-search-results.json)。

在仓库根目录执行下列命令可用模拟器核心重算当前 CSV 的总分。对照时可更换 CSV 路径。

```bash
node - competitions/squares-in-squares/submissions/rectangular_core-score-22.849664303.csv <<'JS'
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

[历史实验脚本](https://github.com/Leonardo-F/kaggle-lab/blob/9f975fecb9481afef8fa0976c76232b22bb22a9b/competitions/squares-in-squares/algorithms/refine_small.py)可用种子 29、3029、4129、81129 各重跑 128 次。

### 矩形内的 45° 斜带与整数边框

固定外边长后，枚举一侧整数宽的网格边框、斜带行数和两个角的余量，在长方形内部按行计算容量。令整数网格边长为 k，扫描 k = 2…31。394 个方块数有容量超过 k² 的候选。按既有中心外扩系数 1.00000004 和 10⁻⁶ 的改进门槛逐题比较，新增改进 **0 题**，继续使用上版 CSV，总分 **23.040802440**。[历史枚举器](https://github.com/Leonardo-F/kaggle-lab/blob/9f975fecb9481afef8fa0976c76232b22bb22a9b/competitions/squares-in-squares/algorithms/framed_strip_sweep.cpp)保留了这次扫描的复现入口。

### 用逐题榜单选择优化目标

从 inversion 的逐题榜单 Notebook 已渲染的输出提取 498 条边长。以 11-20 版为基线，490 题可再缩短至少 `10⁻⁶`，这些差距按 `ΔL/√n` 加权合计约 0.8421 分。22.1061247393 的 Hopper Notebook 报告主要收益来自合并公开布局，最新一轮 hopper 对其公开基线追加约 0.0000445 分。我们的优化从自有 CSV 出发，用逐题记录定位目标和比较边长。[逐题榜单](https://www.kaggle.com/code/inversion/squares-in-squares-per-puzzle-leaderboard)

对邻近方块取当前分离最大的轴，同时线性化方块中心、角度和容器边界。压紧一步后重新计算几何分离，再尝试缩小步长。小规模题加入轻微随机扰动和重启。88 块从 9.914214 降到 9.894228，外扩后 107 块也少约 0.019986。双边带构造随后将 378、418、754、810 块的边长分别降至 19.979694、20.982990、27.958465、28.958465。

### 旋转裁切与接触优化

从较大布局中按四条边裁出包含目标块数的窗口，测试若干小角度，再用凸包的支撑方向把子布局转到最小外包正方形。对入选布局放宽接触线性化步长。69 块通过裁切和接触优化将边长从 8.904069 降至 8.856212。154 块从另一个 181 块构造中裁出有效种子，经压紧后从 12.985282 降至 12.977127。换用不同起点后，418 块从 20.982990 降至 20.966801。

### 行偏移与接缝匹配

固定一个长方形和倾角。每行沿法向移动时，只有碰到边界、角落方块或能容纳下一块时，行容量才会改变。把这些位置对 1 取余，枚举对应的整组排布偏移。以 304 块为例，边长取 17.978、倾角取 51.9° 和 75.9°，等距采样 16 个偏移只能排下 302 块，枚举偏移断点可以排下 304 块。

底边与左边的倾斜排布也可以在接缝处交叠。冲突图的两侧分别对应两条边带的方块。计算最大匹配，再求最小点覆盖，移除该覆盖中的方块，即可在给定两组排布中保留最多的方块。551 块由边长 24 缩至 23.990000，650 块由 26 缩至 25.982000。整份 CSV 的 67 道新布局均由这两类构造生成，其余 933 道沿用上一版自研布局。[单题生成命令](../competitions/squares-in-squares/README.md#重建和验证最佳解)


### 双边带联合搜索

在 22.923849921 的自研基线上，为两侧边带保留多组倾角和行偏移，在不同交叠宽度下联合比较配对容量，再通过二分图匹配去除接缝冲突。新生成的构造改善 59 题，总分下降 0.017151528；其余题保留自研基线。生成器、参数和完整复现命令见[赛题 README](../competitions/squares-in-squares/README.md#重建和验证最佳解)。公开方案只用于比较和启发，不直接替换布局。

### 公开布局诊断与独立搜索

以 [GeiserX 公开的 22.1124018632 布局快照](https://github.com/GeiserX/squares-in-squares/tree/f822b34) 为参考，对比原自研基线 22.906698393。统计的是参考方案逐题可缩短的边长除以 `sqrt(n)` 后的合计。这个快照是公开对照，并非理论最优。

| 方块数 | 我们与公开参考的正向分差 |
| --- | ---: |
| 1–100 | 0.09805 |
| 101–324 | 0.16417 |
| 325–576 | 0.19369 |
| 577–1000 | 0.33838 |

325 块及以上占约 67% 的可见差距。379 和 419 块的公开布局在靠近容器两条边的位置使用了倾斜排列，余下主要是轴对齐方块。参考 [Sergio Fernández Rubio（GeiserX）的双臂分析](https://github.com/GeiserX/squares-in-squares/blob/main/avenues/family.md)，我们从自己的基线检验了几个不同假设：

- 分别给四条边带分配宽度与小数余量，在中间保留整数网格。用 `experiments/pinwheel_sweep.cpp` 比较不同分区的容量。
- 把轴对齐方块和斜方块视为两套候选网格，再用二分图最大匹配得到可共存的子集。用 `experiments/lattice_matching.cpp` 枚举角度、相位和网格错位。
- 用 `experiments/contact_repair.py` 先线性化中心和角度的变化，再固定角度，用精确的面分离约束修复中心位置。用 `experiments/pressure_search.py` 对小题扰动自研布局，允许一簇方块共同旋转，在更小的边长内最小化重叠，再恢复间隙并检查实际边长。

求解器只读取仓库已有的自研 CSV。公开快照用于计算差距、挑选题号和观察结构。四边带扫描覆盖整数边长 2–31，双网格匹配覆盖 3–22，两者在本轮枚举范围内均未改善自研基线。接触约束压紧与扰动重启合并后改善 102 题，总分下降 0.057034090，其中 577–1,000 块的 73 道题贡献 0.025629069。11 块边长从 3.914213679 降至 3.886746085，69 块从 8.856211585 降至 8.827194845，503 块从 22.955000263 降至 22.930437841。

在赛题目录运行以下命令。搜索额外需要 NumPy、SciPy 和支持 C++20 的编译器，本轮使用 NumPy 2.3.5 和 SciPy 1.17.0。输入只需要仓库自研基线，慢速压紧可用 `--min-n` 与 `--max-n` 分段运行。

```bash
base=submissions/rectangular_core-score-22.906698393.csv
g++ -std=c++20 -O3 -fPIC -shared experiments/pressure_loss.cpp -o /tmp/packing-pressure.so
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python experiments/contact_repair.py \
  "$base" /tmp/packing-repair.csv --workers 5 --steps 3
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python experiments/pressure_search.py \
  "$base" /tmp/packing-pressure.csv --lib /tmp/packing-pressure.so --workers 4 --attempts 120 \
  --targets 11 17 19 29 37 41 50 54 55 68 69 71 105 107 108 126 129 131 154 155
OPENBLAS_NUM_THREADS=1 python experiments/choose_search_results.py \
  "$base" /tmp/packing-combined.csv /tmp/packing-repair.csv /tmp/packing-pressure.csv
python algorithms/certify.py --input /tmp/packing-combined.csv --complete --workers 8 \
  --report /tmp/packing-combined-certification.json
```

大题剩余的改进需要让多个倾斜区域协同工作。[cdeotte 的公开构造](https://www.kaggle.com/code/cdeotte/squares-in-squares-multi-gadget-fault-dp-22-48)提供了一个可测试的方向：沿阶梯形分界组合多个小模块。独立生成模块后，可以用拼接前后的容量与容器边长决定哪些接缝值得交给压紧程序。

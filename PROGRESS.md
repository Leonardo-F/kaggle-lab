# Kaggle Lab 项目进展

更新日期 2026-11-20

正方形装箱目前的最好总分是 **23.040802440**。相对最初的整数网格 **28.937669917**，下降 **5.896867477**（约 **20.38%**）。最终 CSV 包含 500,500 行，模拟器与官方 v20 本地评分均接受了全部 1,000 题。[最新版提交 CSV](competitions/squares-in-squares/submissions/rectangular_core.csv) · [逐题认证报告](competitions/squares-in-squares/submissions/rectangular_core-certification.json)

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

在最新一轮，18 块的边长从 4.884210 降到 4.828427，41 块从 7 降到 6.949748。29 块对目标边长 5.9899 做了 512 次局部重启，尚未找到可行布局，提交文件保留边长 6 的网格。

## 复现与历史记录

- [11-12 的实验记录](docs/competition-strategies/implementation-status.md)和[网格、旋转构造的认证摘要](docs/competition-strategies/2026-11-12-results.json)记录了最初的两组完整结果。
- [偏置对角带与外扩实验](docs/competition-strategies/strip-search.md)提供推导、三种构造开关和复现命令，[认证摘要](docs/competition-strategies/strip-search-results.json)保存各组的 CSV 指纹。
- [最新构造与 29 块实验](competitions/squares-in-squares/submissions/rectangular_core.md)提供生成命令和逐题验证入口。`core_search.py --mode baseline` 可以重建 23.445523069 版，`tilt_search.py` 的清单字段 `score_strip_with_border` 记录变角度斜带单独合并后的值。

在仓库根目录执行下列命令可用模拟器核心重算当前 CSV 的总分。对照时可更换 CSV 路径。

```bash
node - competitions/squares-in-squares/submissions/rectangular_core.csv <<'JS'
const fs = require('node:fs');
const core = require('./competitions/squares-in-squares/simulator/packing-core.js');
const layouts = core.parseCsv(fs.readFileSync(process.argv[2], 'utf8'));
if (layouts.size !== core.MAX_N) throw Error('CSV 必须覆盖全部 1,000 题');
let total = 0;
for (let n = 1; n <= core.MAX_N; n++) total += core.evaluate(layouts.get(n)).score;
console.log(total.toFixed(9));
JS
```

### 矩形内的 45° 斜带与整数边框

固定外边长后，枚举一侧整数宽的网格边框、斜带行数和两个角的余量，在长方形内部按行计算容量。令整数网格边长为 k，扫描 k = 2…31。394 个方块数有容量超过 k² 的候选。按既有中心外扩系数 1.00000004 和 10⁻⁶ 的改进门槛逐题比较，新增改进 **0 题**，继续使用上版 CSV，总分 **23.040802440**。在装箱目录运行以下命令可重新生成候选表，各列依次为题号、理想边长、容量、边框宽、斜带行数、下侧余量。[枚举器](competitions/squares-in-squares/algorithms/framed_strip_sweep.cpp)

~~~bash
c++ -O3 -std=c++17 algorithms/framed_strip_sweep.cpp -o /tmp/framed-strip
/tmp/framed-strip > /tmp/framed-strip.tsv
~~~

## 量子电路编译

已生成首个完整的 `invsqrt.kmb` 子题电路。用每段中点修正割线误差，查表项数从 4,096 降到 2,048。进一步一次读取相邻两项，选中一项后提前清理另一项。三个阶段按相同口径估算的单题成本如下。

| 阶段 | 逻辑比特 | Toffoli 类门 | 全输入模型超限数 | 单题成本估算 ↓ |
| --- | ---: | ---: | ---: | ---: |
| 4,096 项普通割线 | 127 | 6,551 | 0 | 872,599 |
| 2,048 项中点校正，单项查表 | 119 | 4,448 | 0 | 559,595 |
| 2,048 项中点校正，成对查表 | **123** | **3,555** | **0** | **468,566** |

最后一步多用 4 个逻辑比特，节省 893 个 Toffoli 类门，估算成本再降 **16.27%**，较本仓库第一版降低 **46.30%**。对最终电路的全部 3,133,452 个输入各做一次 Kickmix 回放，输出相位、输入恢复和辅助位清零均通过。另对 4,342 个输入各回放四次，共 17,368 次，也全部通过。最高相对误差约为 5.18052 × 10⁻⁸，容限约为 5.96046 × 10⁻⁸。官方每输入 64 次的完整验证和 Kaggle 线上总分仍待取得。[七个版本的参数、成本与复现命令](competitions/google-quantum-circuit-compilation/README.md#已编译的逆平方根相位电路) · [逐版本实测记录](competitions/google-quantum-circuit-compilation/experiments/linear-phase-audit.json)

# Santa 2026 · 解法与实验进展

独立求解 V4 本地全量 **219,462 步**，1,000 题通过独立回放。历代算法、分数、消融及复现命令见[算法演进](algorithm-evolution.md)。

以下保留早期实验及复现记录。

## 问题建模

每题的状态由当前寄存器值和已覆盖目标组成。每条指令读取两个寄存器，再写入一个寄存器，写入位置可以与输入相同。加减乘除每次均计一步，除法要求整除。每题最多 4,096 步，提交 CSV 的每个程序单元格最多 128 KiB。1,000 题的步数直接求和，任何一题非法会导致整份提交被拒绝。

例如初值为 3、目标为 9、27、81 时，先算 3×3 得到 9，再用 9×3 得到 27，最后用 9×9 得到 81。三个目标都未出现在初值中，每步最多引入一个新目标，因此这三步已达该题下界。

## 求解方法

1. 先用当前寄存器中的值直接生成目标。搜索停滞时，枚举一步可达的中间值，优先选择能让多个未覆盖目标下一步变得可达的中间值。
2. 对剩余目标用多进制拆解。宽进制方案尝试 31、48、64、81、128、256 和 512，按需构造余数。需要时用 `bq − r` 代替 `bq + r`，前提是乘积不超过该题的上限。构造相邻目标时可复用商、余数和中间积。
3. 保留首次覆盖目标的指令及其依赖，然后根据后续使用重新分配寄存器，复用原本需要重新生成的数值。逐条回放，逐题保留最短的合法候选。

4. 对不足 25 个合法数值的小题，用 A* 搜索最少指令。对较大题，根据寄存器内已有的商和余数在多个进制间切换。最后回看生成的算术链，用已有数值替换只为某个结果服务的中间计算，回放后逐题选优。

对应实现和命令见[项目入口](../README.md)。

## 1,000 道正式题结果

| 方案 | 总指令数 |
| --- | ---: |
| 官方示例提交 | 1,490,379 |
| 第一版多进制基线 | 425,694 |
| 第一版加中间值搜索、带符号余数及寄存器复用 | 391,003 |
| 第一版加宽进制方案 | 285,527 |
| 上一版逐题选优 | 285,288 |
| 混合进制、算术链重写与小题精确搜索 | 272,748 |
| 官方示例起点压缩（自产结果连续三轮 `--refine`） | 270,450 |
| 值图改写器（锚点 ± 偏移 + 双指令重推，迭代三轮） | 269,706 |
| 值图改写器多轮 + 逐题取最短合并 | 269,611 |
| 锚点变体搜索（跨度/方向/倍增）+ 两轮合并 | 269,474 |
| 追加变体 6/7 与倍增变体 5 后再合并 | 269,413 |
| 有理链改写 `t = (a·p + c)/q` + 合并 | 269,385 |
| 有理链 p,q 上限放宽到 256 后再合并 | 269,369 |
| 历史参考程序加入两步中间值，做共享值图搜索 | 266,406 |
| GitHub 269,369 版单独做同样搜索 | 264,773 |
| 两个共享值图搜索结果与 GitHub 基线逐题合并 | **263,575** |

早期从本地 285,288 步提交文件继续优化，少 12,540 步（4.40%）。有 951 道题变短。求解器和独立回放器均验证了全部 1,000 道题，最长程序 526 步。该分数为本地计数，待上传 Kaggle 核对。

随后改为从官方 `sample_submission`（1,490,379 步）出发：先按上面的运行命令生成一版，再把自产结果作为 `--reference` 并加 `--refine` 连续压缩三轮，逐题保留更短程序，得到 **270,450**。`--check` 对 1,000 题全量回放通过。该版提交保存为 [elf-calculator-score-270450.csv](../submissions/elf-calculator-score-270450.csv)，与官方示例逐题比较，1,000 题均为更短程序、无一逐字节相同。官方 `data/` 仍不入库，按 README 下载后即可重跑。

## 共享值图大邻域搜索（2026-11-24）

搜索从自研的 270,771 步和 269,369 步提交分别出发。对每个值枚举之前出现的操作数，再从按位宽优先选取的 72 个候选值中构造额外的两步中间值，每个节点最多尝试 24 个此类替代项。每题运行 1,000 轮，随机扰动一小组活跃依赖并以全部目标共用的节点数择优。搜索后的图尝试三种求值顺序，每个程序回放后再与参考比较。两路输出分别为 266,406 和 264,773 步，逐题保留最短合法程序后为 **263,575** 步。正式 1,000 题通过仓库回放和独立回放，453 题较原 GitHub 基线更短，547 题持平，最长 525 步。

```bash
python dag_lns.py data/puzzles.csv --reference submissions/elf-calculator-score-270771.csv \
    --rounds 1000 --seed 20261124 --jobs 8 --output lns-history.csv
python dag_lns.py data/puzzles.csv --reference submissions/elf-calculator-score-269369.csv \
    --rounds 1000 --seed 20261124 --jobs 8 --output lns-main.csv
python legacy/graph_polisher.py data/puzzles.csv --merge \
    submissions/elf-calculator-score-269369.csv lns-history.csv lns-main.csv \
    --output elf-calculator-score-263575.csv
python solve.py data/puzzles.csv --check elf-calculator-score-263575.csv
```

这是本地验证的指令总数。批量共享值图搜索使用上述 Python 入口。浏览器模拟器的交互求解仍由 JavaScript 实现。[提交 CSV](../submissions/elf-calculator-score-263575.csv)

## 公开前沿方案对比（2026-11-23）

对公开前沿提交（128,513，见 [对比分析](frontier-analysis.md)）做了逐格阅读与差距测量：该 notebook 只校验并复制一份公开的"逐题最短程序"数据集，不含求解算法。按目标位宽分档对比，我们的每题目标平均指令数在各档都约为其 1.8 倍；对 1,000 题的随机性与共享结构检验显示目标基本是随机大整数，差距来自联合搜索而非某种解析结构。

新增 `legacy/graph_polisher.py`（值图改写器），把程序产出的所有值当作操作数做单/双指令重推、锚点 ± 偏移重推（偏移递归构造），每步回放校验、只保留更短结果；多轮结果再逐题取最短合并。修正"锚点改写只按整题长度择优"后，对正式集迭代打磨、再做锚点变体搜索（跨度 4–16、单向/双向、`anchor*k ± gap` 倍增锚点）并逐题取最短合并，得到 **270,450 → 269,369**（少 1,081 步，−0.40%；281 题变短、719 题持平、0 题变长，最长程序 525 步），`solve.py --check` 独立回放 1,000 题通过。归档 [elf-calculator-score-269369.csv](../submissions/elf-calculator-score-269369.csv)（中间版本 269,706、269,611、269,474、269,413、269,385 一并保留）。

```bash
# 逐轮打磨：单指令 → 双指令 → 双向锚点 → 交替收敛
python legacy/graph_polisher.py data/puzzles.csv --reference submissions/elf-calculator-score-270450.csv \
    --one-sided --no-two-step --output a.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --reference a.csv --one-sided --output b.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --reference b.csv --output c.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --reference c.csv --one-sided --output d.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --reference d.csv --output e.csv --jobs 8
# 逐题取最短并复核
python legacy/graph_polisher.py data/puzzles.csv --merge \
    submissions/elf-calculator-score-270450.csv a.csv b.csv c.csv d.csv e.csv --output merged.csv
python legacy/graph_polisher.py data/puzzles.csv --check merged.csv
```

各轮总步数：a=269,911 · b=269,804 · c=269,741 · d=e=269,739 · 合并=269,611。

```bash
# 变体搜索（从 269,611 出发），再与前面的结果逐题取最短
for v in 1 2 3 4 5; do
    python legacy/graph_polisher.py data/puzzles.csv --reference submissions/elf-calculator-score-269611.csv \
        --variant $v --output v$v.csv --jobs 8
done
for v in 1 2 3; do
    python legacy/graph_polisher.py data/puzzles.csv --reference submissions/elf-calculator-score-269611.csv \
        --scaled --variant $v --output sc$v.csv --jobs 8
done
python legacy/graph_polisher.py data/puzzles.csv --reference merged.csv --scaled --variant 3 --output wsc.csv --jobs 8
python legacy/graph_polisher.py data/puzzles.csv --merge submissions/elf-calculator-score-270450.csv \
    submissions/elf-calculator-score-269611.csv v*.csv sc*.csv merged.csv w*.csv --output best.csv
python legacy/graph_polisher.py data/puzzles.csv --check best.csv
```

变体表：跨度/最近邻/方向/是否双指令，见 `legacy/graph_polisher.py` 的 `VARIANTS`；`--scaled` 额外尝试 `t = anchor*k ± gap`（k ≤ 16），`--rational` 尝试 `t = (anchor*p + c)/q`（p,q ≤ 64，需要 `t*q ≤ value_limit`，因此只在有裕量的题上生效）。各变体单独结果 269,422–269,609，合并后 269,474；追加变体 6/7、倍增变体 5、有理链改写后到 **269,385**。

仍与公开前沿（128,513）差约 2.1 倍：该分数是社区逐题最优程序的并集，单算法难以匹配；剩余差距需要"全局共享中间值搜索"而非继续加局部改写规则。

官方输入及完整答案需从本地运行生成。仓库收录求解器、复现命令和汇总结果。

[官方题面与评分](https://www.kaggle.com/competitions/santa-2026/overview) · [数据与规则](https://www.kaggle.com/competitions/santa-2026/data)

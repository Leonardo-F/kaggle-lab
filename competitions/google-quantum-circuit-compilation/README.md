# Google Quantum AI — Verifiable Quantum Circuit Compilation

> Google 量子计算电路编译优化赛（Kaggle，2026–2027）
>
> **项目状态：成本计算器 + 可复现整数近似实验 + 官方验证入口。尚无通过官方验证的参赛电路；官方数据接入需要 Kaggle 登录和赛规确认。**

- 官方比赛：[Google Quantum AI — Verifiable Quantum Circuit Compilation](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation)
- 组织方：Google Quantum AI
- 总奖金：US$150,000
- 启动：2026-10-22；报名 / 组队截止：**2027-01-13 23:59 UTC**；最终提交：**2027-01-20 23:59 UTC**
- 中途里程碑奖截止：2026-11-20；持续榜首奖计分期结束：2027-01-04。具体奖金资格、公开 Notebook、数据使用和代码开源要求，以 Kaggle 当前规则为准。

## 这项竞赛在解决什么问题？

在容错量子计算中，量子比特（Q）和 Toffoli/T 等非 Clifford 门通常是昂贵资源。比赛希望通过**可逆计算、编译优化、误差容忍与资源权衡**，减少真实量子应用所需的计算资源。

竞赛采用可验证的 **kickmix** 电路：由可逆经典逻辑、对角相位操作和基于测量的反计算构成，可在经典计算机上高效抽样验证；相关技术来自 Google 开源的 [Qualtran](https://github.com/quantumlib/Qualtran)。允许使用 AI coding agents，但**正确性验证和可复现性**仍然是必要步骤。

这里的目标不是在真实量子硬件上运行 VQE，而是降低三个特定子程序的容错资源成本。

## 三个赛题 / Three benchmarks

| 赛题 | 科学背景 | 要实现/优化的内容 | 单题成本（越小越好） |
|---|---|---|---|
| `invsqrt` | 核聚变 / 温稠密等离子体 | 计算与 `1/√x` 对应的精确相位操作；优化可逆定点算术、近似及清理工作量 | `Q × (Toffoli + T/4)` |
| `dqi` | 组合优化 / Decoded Quantum Interferometry | 对 Reed–Solomon 综合征进行**可逆解码与相位校正**；在门数、辅助量子比特和少量允许失败之间权衡 | `R(ε₊) × Q² × T` |
| `dfthcsos` | 量子化学 / FeMoCo 氮固定催化 | 协同优化经典张量分解、Givens 旋转树与量子查表 QROM/ANGLE 电路 | `λ_eff × T × Q` |

符号：`Q` 为逻辑量子比特数，`T` 在后两个成本式中指 **Toffoli 数量**（**不是** T 门数量）；`ε₊` 是解码失败率的置信上界。`dfthcsos` 中的 `Q/T` 对应**整个块编码**，不只是单个 ANGLE 文件。

### 1. `invsqrt` — 核聚变逆平方根相位

电子的库仑相互作用涉及 `1/r = 1/√x`。给定固定点表示的 `x`，设计一个既准确又资源节约的 kickmix 相位电路。可以尝试更好的初值、分段逼近、Newton 迭代次数/位宽分配、可逆乘法及 measurement-based uncomputation。**必须**满足官方近似误差和清理辅助位等要求。

### 2. `dqi` — 可逆 Reed–Solomon 解码

DQI 将多项式组合优化中的一部分工作转换为纠错码解码。需要把综合征变换为正确的相位修正，并恢复辅助工作位。优化方向包括有限域算术、可逆综合征解码器结构、临时存储复用，以及允许小幅失败率换取资源压缩。评分会用 `ε₊` 对失败率付出重复运行成本；因此不应只关注 Toffoli 门数。

### 3. `dfthcsos` — FeMoCo 哈密顿量块编码

任务不仅要求量子电路优化，还需要**经典数值表示与量子 QROM** 联合设计：输出 Hamiltonian 张量分解、Givens 树，以及每个 `angle_k_i` 的查表/相位电路。ANGLE 电路宽度不得超过 **128 qubits**。要同时评估分解误差、谱参数、完整块编码的门数/量子比特数。

## 官方计分（越大越好）

最终成绩是三个 benchmark 相对于参考实现成本下降倍数的**几何平均**：

```text
score = ((cost_ref[invsqrt] / cost[invsqrt])
       * (cost_ref[dqi]     / cost[dqi])
       * (cost_ref[dfthcsos]/ cost[dfthcsos])) ** (1/3)

invsqrt_cost = Q * (n_toffoli + n_T_gates / 4)
dqi_cost     = R(epsilon_upper) * Q**2 * n_toffoli
R(epsilon)   = ln(2) / -ln(0.5 + 2*sqrt(epsilon))
dfthcsos_cost = sqrt(E_gap * (2*Lambda - E_gap)) * n_toffoli * Q
```

上述是官方评分公式的说明性重写。**真正得分应以 Kaggle 评测器为准**；`algorithms/cost_model.py` 只是独立实现的数值计算小工具，并不等于官方网关或验证器。

## 必需提交结构 / Submission ZIP

**ZIP 根目录**须包含以下内容（`.kmb` 或 `.kmx` 二选一）：

```text
submission.zip
├── invsqrt.kmb                  # 或 invsqrt.kmx
├── dqi.kmb                      # 或 dqi.kmx
└── dfthcsos/
    ├── angle_k_0.kmb             # 或 .kmx
    ├── angle_k_1.kmb
    ├── ...                       # 编号从 0 连续，不得缺号
    └── submission.npz           # U, W, H2_I, H1_I, Hsym_lower, tree_edges
```

提交后官方评分预计约 45 分钟，实际以官方平台显示为准。没有完整、验证通过的 `.kmb`/`.kmx` 与数值数组时，**不要把此仓库当前目录压缩后当成有效参赛提交**。

## 仓库已有内容

```text
algorithms/cost_model.py      # Python 标准库实现的评分公式计算（原创）
experiments/test_cost_model.py # 数值单元测试
submissions/README.md         # 本地生成的完整 ZIP 应放何处（输出已 gitignore）
```

运行目前已有的公式测试：

```bash
python -m unittest discover -s competitions/google-quantum-circuit-compilation/experiments -v
```

### 新增：全输入整数实验与验证入口

在独立虚拟环境安装 `requirements.txt`（Python 3.11+），然后从仓库根目录运行：

```bash
python -m pip install -r competitions/google-quantum-circuit-compilation/requirements.txt
python competitions/google-quantum-circuit-compilation/algorithms/invsqrt_model.py --output competitions/google-quantum-circuit-compilation/experiments/results/invsqrt-scan.json
```

该命令遍历所有 3,133,452 个整数输入，比较 32/64/128 段与 26/28/30 位小数，保存全部整数系数、精确整数不等式的失败数及代码哈希。每次乘法采用 nearest-even 舍入，尺度指数单独保留。它尚未计入可逆清理和旋转合成成本。

官方数据解压到 `official/` 后，可调用原始任务验证器（入口接口依据官方 metric v10；因当前数据权限不足，三题集成运行仍待完成）：

```bash
python competitions/google-quantum-circuit-compilation/algorithms/verify_official.py --data-root competitions/google-quantum-circuit-compilation/official --submission competitions/google-quantum-circuit-compilation/official/sample_submission --report competitions/google-quantum-circuit-compilation/experiments/results/reference-verification.json
```

入口提供 `--task invsqrt` / `dqi` / `dfthcsos`，默认验证三题，保留官方完整抽样预算。缺少数据或失败时写入失败回执并返回非零状态；不会沿用旧的成功报告。任务本地验证仍不等于 Kaggle 完整提交检查或私有 salt 评分。参见 [当前实测结果和接入限制](../../docs/competition-strategies/implementation-status.md)。

## 推荐实现路线 / Engineering roadmap

1. **官方基准复现：** 研究 Qualtran/kickmix 的文件格式、验证器和基础电路生成方法；先生成三项都能通过校验的官方等价 baseline。
2. **分任务独立优化：** 从 `invsqrt` 的可逆定点近似或 `dqi` 的有限域模块入手；保留 baseline 与每次修改的统计结果。
3. **量子资源分析：** 每次保存 Q、Toffoli、T、失败率上界、验证日志和相对改善倍数；`dfthcsos` 必须计算整个 block encoding 的成本。
4. **自动验证闭环：** 对所有候选运行官方 fuzz/verifier，严格检查功能、相位和 ancilla 清理。
5. **再打包提交：** 只有三项输出都满足官方文件格式和约束，才产生可提交的 ZIP。

建议把每个 benchmark 进一步拆为 `invsqrt/`、`dqi/`、`dfthcsos/` 子模块，但**待真实实现出现时再创建**，避免空目录增加复杂度。

## 参考 / References and provenance

1. [Kaggle 官方比赛说明与提交格式](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation)
2. T. Khattar et al., *Leveraging verifiable structure in quantum circuits to find more efficient compilations with agentic AI*, [arXiv:2610.23832](https://arxiv.org/abs/2610.23832)
3. [Google Qualtran 开源仓库](https://github.com/quantumlib/Qualtran) — **引用与未来依赖候选，并非此仓库已拷贝的代码**。

本仓库的 `cost_model.py` 是根据公开评分公式独立编写的；目前**没有复用第三方量子编译器实现**。未来如引用外部库、论文算法、Notebook 或适配他人代码，应注明作者、链接、许可证、变更说明与具体使用位置。

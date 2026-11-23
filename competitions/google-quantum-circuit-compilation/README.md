# Google Quantum AI — Verifiable Quantum Circuit Compilation

比赛要求用可逆计算和相位操作压低三个子程序的容错资源成本。电路用 Kickmix 表示，可在普通计算机上抽样验证。[Kaggle 赛题](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation) · [论文与验证设计](https://arxiv.org/html/2610.23832v2)

| 子题 | 任务 | 单题成本 |
| --- | --- | --- |
| `invsqrt` | 对固定点输入施加逆平方根相位，恢复输入并清理辅助位。 | `Q × (Toffoli + T 门 / 4)` |
| `dqi` | 可逆 Reed–Solomon 解码并施加相位修正。 | `R(ε₊) × Q² × Toffoli` |
| `dfthcsos` | 为 FeMoCo 哈密顿量构建块编码，联合选择张量分解和 ANGLE 查表。 | `√(E_gap × (2Λ − E_gap)) × Toffoli × Q` |

`Q` 为逻辑比特数，`ε₊` 为 DQI 失败率的置信上界。DFTHCSOS 的成本用完整块编码的资源计算，单个 ANGLE 电路宽度至多 128 比特。榜单分数取三项参考成本与提交成本比值的几何平均，越高越好。[成本公式实现](algorithms/cost_model.py)

## 生成和回放逆平方根电路

在本赛题目录用 Python 3.11+ 运行。以下命令生成 26 位联合拟合候选，对 3,133,452 个合法输入各回放一次。[各版本成本、量子比特和其他两题的实验](docs/progress.md)

```bash
python -m pip install -r requirements.txt
python algorithms/invsqrt_circuit.py --integer-fit --fraction-bits 26 --output submissions/invsqrt.kmb
python experiments/audit_invsqrt.py submissions/invsqrt.kmb --integer-fit --fraction-bits 26 --all-inputs --repetitions 1 --output /tmp/invsqrt-26.json
python -m unittest discover -s experiments -v
```

## 官方验证和提交格式

将从 Kaggle 下载的官方数据解压到本赛题目录的 `official/`，其中包含 `verifiers/` 与 `sample_submission/`。从本目录运行。

```bash
python algorithms/verify_official.py --data-root official --submission official/sample_submission --report experiments/results/reference-verification.json
```

默认调用三项原始验证器，可用 `--task invsqrt`、`--task dqi` 或 `--task dfthcsos` 指定单题。验证失败时命令返回非零状态。完整官方数据的集成运行和榜单成绩仍待取得。

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

提交产物放在 `submissions/`。生成的电路、NPZ 和 ZIP 由 Git 忽略。仓库中的电路生成器使用开源 [Kickmix 1.0.0](https://github.com/quantumlib/Qualtran/tree/main/kickmix)。

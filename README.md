# Kaggle Lab 🧪

A single home for **independent Kaggle competition solutions, algorithms, visualizations, experiments, and reproducible submissions**.

> Status: initial scaffold / baseline implementations. The packing studio is an **original implementation** written for this repository, not a derivative of an existing packing simulator. No competitive leaderboard claims are made.

## Competitions

| Project | Problem | What works now | Official page |
| --- | --- | --- | --- |
| [`squares-in-squares`](competitions/squares-in-squares/) | Pack 1–1,000 unit squares into the smallest enclosing square | Offline HTML, rotated constructions, per-puzzle selection, CSV, pinned official interval certification | [Kaggle](https://www.kaggle.com/competitions/squares-in-squares) |
| [`google-quantum-circuit-compilation`](competitions/google-quantum-circuit-compilation/) | Reduce resources for three verifiable quantum-circuit tasks | Cost model, exhaustive integer invsqrt experiments, official-verifier entry pending data access | [Kaggle](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation) |

## 竞赛项目概览（中文）

- **Squares in Squares（正方形装箱）：** 为 `n = 1…1000` 的每个实例排列 n 个单位正方形，允许旋转、不得重叠，目标是尽量减小外包正方形边长；可运行原创的 2D 网页模拟器并导出 `id,n,square_id,x,y,angle` 六列 CSV。
- **Google Quantum AI（容错量子电路优化）：** 独立研究 `invsqrt`（逆平方根相位）、`dqi`（可逆 Reed–Solomon 解码）、`dfthcsos`（FeMoCo Hamiltonian / QROM）三个 benchmark。当前提供官方规则详解及成本公式测试，**尚无有效量子电路提交文件**。详情见 [量子比赛 README](competitions/google-quantum-circuit-compilation/README.md)。

## Quick start / 快速开始

**中文解题笔记（2026-11-11）：** 从 [阅读指南](docs/competition-strategies/README.md) 开始，依次阅读 [正方形装箱的构造、搜索与验证](docs/competition-strategies/01-square-packing.md) 和 [量子编译三个子题的思路与实验路线](docs/competition-strategies/02-quantum-compilation.md)。文档区分已有功能、公开方法与拟开展实验；尚未实现的优化不会被当作已有成绩。

**实现进度（2026-11-12）：** [运行命令、已验证结果与下一步](docs/competition-strategies/implementation-status.md)。装箱构造组合的完整 CSV 在未修改的官方 v20 本地检查中通过全部 1000 个实例，总分 **26.9931552390**（网格为 28.9376699166）；这是本地验证结果。量子第一题已完成明确舍入规则的全输入整数实验，尚无通过官方验证的量子电路。

**Square Packing Studio (no build tools or dependencies):** download and open the standalone HTML below. The Chinese UI defaults to n=1000 and its main download button generates a complete `submission.csv` (n=1–1000, 500,500 rows). The default algorithm is the organizer-described unrotated grid baseline; a single-puzzle export is available for debugging.

A portable all-in-one HTML version is also included at `competitions/squares-in-squares/simulator/SquarePackingStudio-standalone.html` (and supplied as a separate downloadable HTML).

For a local HTTP server instead:

```bash
cd competitions/squares-in-squares/simulator
python -m http.server 8000
# Open http://localhost:8000
```

**Generate a full, *valid but unoptimized* Kaggle submission**:

```bash
python competitions/squares-in-squares/algorithms/packing.py generate --output submission.csv
python competitions/squares-in-squares/algorithms/packing.py validate --input submission.csv --complete
```

**Run all local tests**:

```bash
python -m pip install -r competitions/squares-in-squares/requirements.txt numpy==2.3.5
python -m unittest discover -s competitions/squares-in-squares/experiments -v
python -m unittest discover -s competitions/google-quantum-circuit-compilation/experiments -v
```

## Directory policy / 目录规范

```text
kaggle-lab/
├── README.md                     Project index
├── LICENSE                       MIT
├── .github/workflows/test.yml    Lightweight Python + JS checks
├── competitions/
│   ├── squares-in-squares/
│   │   ├── README.md             Competition, algorithm, export & references
│   │   ├── simulator/            Independent HTML/CSS/JS visual workspace
│   │   ├── algorithms/           Python generator & geometry validator
│   │   ├── experiments/          Reproducibility tests
│   │   └── submissions/          Local CSV outputs (gitignored)
│   └── google-quantum-circuit-compilation/
│       ├── README.md             Scoring, three tasks & constraints
│       ├── algorithms/           Cost-model helper
│       ├── experiments/          Unit tests
│       └── submissions/          Kaggle ZIP outputs (gitignored)
└── shared/                      Common code when actually needed
```

New competitions should get their own folder under `competitions/`; do not combine dependencies or submissions across competitions without a concrete reuse case.

## Attribution, independent implementation & competition ethics

- The **packing web simulator and Python generator/verifier were independently written for this repository** using the mathematical geometry and file specifications in the official competition statement. No source was copied from third-party visualizers or optimization repositories.
- The packing `vendor/` directory now contains the **unmodified official v20 metric**, under its separate Apache 2.0 license and attribution notice. Its digest is pinned; original simulators and constructors remain independently implemented. References to other optimizers remain study links.
- If a future algorithm or codebase is adapted from external work, document the exact source URL, original authors, license, modifications, and affected paths in that competition's README before committing it.
- The local collision check is based on standard floating-point separating-axis geometry. **It does not replace** the organizers' interval-arithmetic validation and is not a guarantee of accepted Kaggle scoring.
- Keep Kaggle API secrets, private datasets, large generated CSV/ZIPs and experimental checkpoints out of git. Verify active competition rules before making competition-specific solutions public.

## Publish to GitHub

Repository: https://github.com/Leonardo-F/kaggle-lab

```bash
git clone https://github.com/Leonardo-F/kaggle-lab.git
cd kaggle-lab
# ... edit, then ...
git add .
git commit -m "Improve Kaggle solution"
git push origin main
```

Run the local checks listed above before pushing; CI (`.github/workflows/test.yml`) runs the Python and JavaScript tests on every push and pull request.

**Optional GitHub Pages / 网页部署:** the packing simulator in `competitions/squares-in-squares/simulator/` can be published as a static site, but Pages deployment is **not** enabled automatically by this repository. The portable `SquarePackingStudio-standalone.html` opens locally without a build step.

This repository is public. Competition outputs, credentials, large datasets and experimental logs stay local (`.gitignore`). Before publishing optimized solutions, review Kaggle's rules on shared code and prize eligibility; cite third-party components and respect their licenses.

## License

Original repository code: [MIT](LICENSE). External competition problem statements, APIs, datasets and reference materials retain their respective licenses.

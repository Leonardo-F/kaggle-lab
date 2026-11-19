# Kaggle Lab 🧪

A single home for **independent Kaggle competition solutions, algorithms, visualizations, experiments, and reproducible submissions**.

> Scores and verification results in this repository come from local runs.

## Competitions

| Project | Problem | What works now | Official page |
| --- | --- | --- | --- |
| [`squares-in-squares`](competitions/squares-in-squares/) | Pack 1–1,000 unit squares into the smallest enclosing square | Offline HTML, rotated constructions, per-puzzle selection, CSV, pinned official interval certification | [Kaggle](https://www.kaggle.com/competitions/squares-in-squares) |
| [`google-quantum-circuit-compilation`](competitions/google-quantum-circuit-compilation/) | Reduce resources for three verifiable quantum-circuit tasks | Compiled inverse-square-root phase circuit, full-domain Kickmix replay, cost comparisons | [Kaggle](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation) |

## 竞赛项目概览（中文）

- **Squares in Squares（正方形装箱）：** 为 `n = 1…1000` 的每个实例排列 n 个单位正方形，允许旋转、不得重叠，目标是尽量减小外包正方形边长；可运行原创的 2D 网页模拟器并导出 `id,n,square_id,x,y,angle` 六列 CSV。
- **Google Quantum AI（容错量子电路优化）：** 独立研究 `invsqrt`（逆平方根相位）、`dqi`（可逆 Reed–Solomon 解码）、`dfthcsos`（FeMoCo Hamiltonian / QROM）三个 benchmark。已有可生成的逆平方根相位电路，全域本地回放通过，官方三题总分待取得。详情见 [量子比赛 README](competitions/google-quantum-circuit-compilation/README.md)。

## Quick start / 快速开始

- **正方形装箱**目前最佳本地官方 v20 总分为 **23.040802440**。离线模拟器、最新 CSV 和复现命令见[装箱 README](competitions/squares-in-squares/README.md)。
- **两项竞赛的版本与实测记录**见 [PROGRESS.md](PROGRESS.md)。量子赛题的解题思路见[量子编译策略](docs/competition-strategies/02-quantum-compilation.md)。

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
│   │   └── submissions/          Best CSV and certificate
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
- Keep Kaggle API secrets, private datasets, and intermediate competition outputs out of git. Verify active competition rules before making competition-specific solutions public.

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

This repository is public. Intermediate outputs, credentials, and large datasets stay local (`.gitignore`). Before publishing optimized solutions, review Kaggle's rules on shared code and prize eligibility; cite third-party components and respect their licenses.

## License

Original repository code: [MIT](LICENSE). External competition problem statements, APIs, datasets and reference materials retain their respective licenses.

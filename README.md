# Kaggle Lab 🧪

A single home for **independent Kaggle competition solutions, algorithms, visualizations, experiments, and reproducible submissions**.

> Status: initial scaffold / baseline implementations. The packing studio is an **original implementation** written for this repository, not a derivative of an existing packing simulator. No competitive leaderboard claims are made.

## Competitions

| Project | Problem | What works now | Official page |
| --- | --- | --- | --- |
| [`squares-in-squares`](competitions/squares-in-squares/) | Pack 1–1,000 unit squares into the smallest enclosing square | Offline interactive 2D studio, local overlap checks, deterministic baseline, import/export of CSV, experimental compaction | [Kaggle](https://www.kaggle.com/competitions/squares-in-squares) |
| [`google-quantum-circuit-compilation`](competitions/google-quantum-circuit-compilation/) | Reduce resources for three verifiable quantum-circuit tasks | Challenge brief, experiment scaffold, stand-alone cost-model helper | [Kaggle](https://www.kaggle.com/competitions/google-verifiable-quantum-circuit-compilation) |

## 竞赛项目概览（中文）

- **Squares in Squares（正方形装箱）：** 为 `n = 1…1000` 的每个实例排列 n 个单位正方形，允许旋转、不得重叠，目标是尽量减小外包正方形边长；可运行原创的 2D 网页模拟器并导出 `id,n,square_id,x,y,angle` 六列 CSV。
- **Google Quantum AI（容错量子电路优化）：** 独立研究 `invsqrt`（逆平方根相位）、`dqi`（可逆 Reed–Solomon 解码）、`dfthcsos`（FeMoCo Hamiltonian / QROM）三个 benchmark。当前提供官方规则详解及成本公式测试，**尚无有效量子电路提交文件**。详情见 [量子比赛 README](competitions/google-quantum-circuit-compilation/README.md)。

## Quick start / 快速开始

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
- **Official documentation references** appear in each competition's README. They are specifications and citation links, **not borrowed implementations**.
- If a future algorithm or codebase is adapted from external work, document the exact source URL, original authors, license, modifications, and affected paths in that competition's README before committing it.
- The local collision check is based on standard floating-point separating-axis geometry. **It does not replace** the organizers' interval-arithmetic validation and is not a guarantee of accepted Kaggle scoring.
- Keep Kaggle API secrets, private datasets, large generated CSV/ZIPs and experimental checkpoints out of git. Verify active competition rules before making competition-specific solutions public.

## Publish to GitHub

Repository: https://github.com/Leonardo-F/kaggle-lab . See [`GITHUB_SETUP.md`](GITHUB_SETUP.md) for local cloning and future contribution instructions.

## License

Original repository code: [MIT](LICENSE). External competition problem statements, APIs, datasets and reference materials retain their respective licenses.

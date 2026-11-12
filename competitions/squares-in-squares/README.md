# Squares in Squares

**Competition:** https://www.kaggle.com/competitions/squares-in-squares

A geometric packing challenge: place **n=1…1000** unit squares, optionally rotated, with no overlap. For each n, minimize the axis-aligned enclosing square side `L`. Translations do not change `L`.

## Score & submission

- Per-puzzle objective: `L / sqrt(n) - 1`; total score is the sum across all puzzles. **Lower is better.**
- Feasible tilings of perfect-square counts (n=1,4,9,…) achieve the area bound and score zero.
- Missing/invalid puzzles receive their trivial-grid penalty from the official scorer.
- One CSV with columns **`id,n,square_id,x,y,angle`**; center coordinates and angles in **radians**. Complete n=1…1000 produces **500,500 data rows**.

## Interactive simulator (v0.3)

**Easiest:** download [`SquarePackingStudio-standalone.html`](simulator/SquarePackingStudio-standalone.html) and open it in a modern desktop browser. All JavaScript and CSS are embedded; no install, server, account, or network assets are needed. The Chinese interface also adapts to narrow screens.

- The default preview is **n=1000**: a 32×32 unrotated unit grid, with 24 empty cells.
- The primary button downloads **`submission.csv` with all 1,000 puzzles and 500,500 data rows**, independent of the currently previewed n. IDs run from 0 to 500499.
- Algorithm: m=ceil(sqrt(n)); center i is `(i % m + 0.5, floor(i / m) + 0.5)`, angle=0. This independently implements the **trivial grid baseline described by the organizer**, not an optimal packing and not a byte-for-byte copy of sample_submission.csv. Its total score from the published formula is approximately **28.93766991655**.
- Edits take precedence for their puzzle; other puzzles use the baseline. A secondary button exports a single puzzle for debugging only.
- Drag/select, rotate, nudge, zoom and pan. Camera scale stays fixed while dragging. Reset restores the current puzzle's baseline.
- Optional compact-and-relax search for n≤80 never starts by itself and may find no improvement.
- Optional **旋转构造** buttons compare a rotated core with four corner blocks or staircases, plus deletion transfer. Apply to the current puzzle or all 1,000; existing better valid edits are retained. The default remains the organizer grid.
- Import merges complete, locally acceptable puzzles atomically. The original decimal strings are preserved for unchanged imported coordinates. Empty values, non-decimal literals, incorrect IDs, missing squares, overlaps and uncertain contacts are rejected.
- Work remains in memory. **Download CSV before closing the page.** No automatic Kaggle submission occurs.

### What the checker does

Zero-angle near contacts use exact decimal differences; positive overlaps are not forgiven by a tolerance. For rotated squares, separating-axis tests and spatial hashing identify clear separation/overlap. Borderline rotated contacts are labeled uncertain and blocked, even when an official high-precision verifier could prove them feasible. Invalid layouts show no attractive negative score.

The local numerical editor accepts |x|,|y|≤10⁶ and |angle|≤1000 radians, decimal fields up to 2048 characters with exponent magnitude≤2048, and files up to 100 MB. These are **local resource/precision limits**, not a restatement of competition rules. Arbitrary rotated layouts still require the official interval verifier; no official certification is claimed by this app.

### Development and checks

The editable version is `simulator/index.html` beside `styles.css`, `packing-core.js` and `app.js`. Rebuild the one-file edition with:

```bash
python simulator/build_standalone.py
node --test experiments/test_core.cjs
```

## Reproducible Python baseline

No third-party package needed (Python 3.10+):

```bash
python algorithms/packing.py generate --output submissions/submission.csv
python algorithms/packing.py validate --input submissions/submission.csv --complete
python -m unittest discover -s experiments -v
```

The generated CSV is a **valid but weak baseline**: a `ceil(sqrt(n))`-column grid for each puzzle. Its chief purpose is to establish correct formatting, local feasibility, and a safe fallback before implementing stronger research algorithms.

Geometry checks implement SAT (separating-axis theorem) with a 2-unit spatial hash. Zero-angle critical contacts use exact decimal comparisons; borderline rotated contacts are conservatively rejected locally. **Always rerun the original official metric before submitting.**

## Provenance / attribution

### Constructive portfolio and official certification

Install the separate numerical dependencies in a virtual environment, then run from the repository root:

```bash
python -m pip install -r competitions/squares-in-squares/requirements.txt
python competitions/squares-in-squares/algorithms/constructions.py --output competitions/squares-in-squares/submissions/constructed.csv --manifest competitions/squares-in-squares/experiments/results/constructions.json
python competitions/squares-in-squares/algorithms/certify.py --input competitions/squares-in-squares/submissions/constructed.csv --complete --workers 4 --report competitions/squares-in-squares/experiments/results/certification.json
```

The certifier checks final decimal strings and a pandas numeric read/write round trip with the **unmodified official v20 metric**. It reports rejected puzzles separately from their fallback score, and exits unsuccessfully if either route rejects any puzzle. It does not submit to Kaggle. Reports retain the CSV and verifier SHA-256 hashes. Full verification can take several minutes.

On 2026-11-12, all 1,000 generated puzzles passed both routes. The portfolio improved 162 puzzles, lowering the local official score from 28.93766991655 to **26.99315523903**. See [results and limitations](../../docs/competition-strategies/implementation-status.md).

**Original code in this project:**
- `simulator/index.html`, `simulator/styles.css`, `simulator/packing-core.js`, `simulator/app.js`, `simulator/build_standalone.py`: designed and implemented from scratch for Kaggle Lab, with no third-party script, CSS, artwork, source material or layout algorithm copied.
- `algorithms/packing.py`: independently implemented deterministic grid layout, geometric projections, separating-axis collision checks, CSV writer, CSV reader and score calculation.
- `algorithms/constructions.py` and the matching browser function: independent implementation of classical rotated-core/corner families and per-puzzle deletion transfer. Mathematical inspiration is documented in the strategy notes; no external coordinates or optimizer code were imported.
- `algorithms/certify.py`: original strict CSV wrapper around the third-party metric in `vendor/`.
- `experiments/test_packing.py`: independent sanity checks.

**External reference specifications only (not code reuse):**
- Kaggle official competition: https://www.kaggle.com/competitions/squares-in-squares
- Kaggle official data/CSV specification: https://www.kaggle.com/competitions/squares-in-squares/data
- Kaggle official metric and high-precision verifier: https://www.kaggle.com/code/metric/squares-in-squares

The official verifier is the sole vendored implementation: see [vendor/NOTICE.md](vendor/NOTICE.md) and its Apache 2.0 license. Third-party simulators, packing tables, submissions and optimization routines have not been copied. Further reuse must retain authorship, license, version, modifications and affected paths.

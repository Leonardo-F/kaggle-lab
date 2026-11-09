# Squares in Squares

**Competition:** https://www.kaggle.com/competitions/squares-in-squares

A geometric packing challenge: place **n=1…1000** unit squares, optionally rotated, with no overlap. For each n, minimize the axis-aligned enclosing square side `L`. Translations do not change `L`.

## Score & submission

- Per-puzzle objective: `L / sqrt(n) - 1`; total score is the sum across all puzzles. **Lower is better.**
- Feasible tilings of perfect-square counts (n=1,4,9,…) achieve the area bound and score zero.
- Missing/invalid puzzles receive their trivial-grid penalty from the official scorer.
- One CSV with columns **`id,n,square_id,x,y,angle`**; center coordinates and angles in **radians**. Complete n=1…1000 produces **500,500 data rows**.

## Interactive simulator

Open [`simulator/index.html`](simulator/index.html) with its neighboring CSS/JS files, or the completely self-contained [`SquarePackingStudio-standalone.html`](simulator/SquarePackingStudio-standalone.html). No npm, frameworks or network assets are required. Features:

1. Browse n=1 to 1000; every puzzle starts with a deterministic non-overlapping grid.
2. Select a square, drag it, rotate it 5° at a time, nudge with arrows, zoom or pan.
3. View bounding side `L`, per-puzzle score, density, and local overlap check.
4. Experimental **compact & relax** search for n≤80 (may find *no* improvement; a failed candidate leaves the prior feasible layout intact).
5. Export just the selected puzzle CSV or a complete 1–1000 `submission.csv`. Edited layouts take precedence; remaining puzzles use safe grids.
6. Import CSV from a previous session. Complete puzzles are validated locally before being accepted. Work is held in memory, so **export to save** before closing the tab.

**Limitations:** canvas-based **2D** preview is the scientifically correct view for a two-dimensional packing task. This is an independent visualization tool, **not** a claim to implement a state-of-the-art packing optimizer. CSV imports expect standard unquoted numeric fields and six columns in official order. The app does not autosave. The full CSV may take a moment to generate.

## Reproducible Python baseline

No third-party package needed (Python 3.10+):

```bash
python algorithms/packing.py generate --output submissions/submission.csv
python algorithms/packing.py validate --input submissions/submission.csv --complete
python -m unittest discover -s experiments -v
```

The generated CSV is a **valid but weak baseline**: a `ceil(sqrt(n))`-column grid for each puzzle. Its chief purpose is to establish correct formatting, local feasibility, and a safe fallback before implementing stronger research algorithms.

Geometry checks implement SAT (separating-axis theorem) with a 2-unit spatial hash. The local threshold uses floating-point tolerance; close-to-touching rotated squares can still fail the competition's certified interval arithmetic. **Always rerun the original official metric before submitting.**

## Provenance / attribution

**Original code in this project:**
- `simulator/index.html`, `simulator/styles.css`, `simulator/app.js`: designed and implemented from scratch for Kaggle Lab, with no third-party script, CSS, artwork, source material or layout algorithm copied.
- `algorithms/packing.py`: independently implemented deterministic grid layout, geometric projections, separating-axis collision checks, CSV writer, CSV reader and score calculation.
- `experiments/test_packing.py`: independent sanity checks.

**External reference specifications only (not code reuse):**
- Kaggle official competition: https://www.kaggle.com/competitions/squares-in-squares
- Kaggle official data/CSV specification: https://www.kaggle.com/competitions/squares-in-squares/data
- Kaggle official metric and high-precision verifier: https://www.kaggle.com/code/metric/squares-in-squares

Potential third-party simulator designs, open-source Kaggle submissions, external packing tables and copied optimization routines were **not used**. If added in the future, they must be credited here with authorship, license, URLs, modifications and affected files.

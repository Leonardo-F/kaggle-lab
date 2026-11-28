# Santa V11 — frozen R16 candidate (R17 full-test runner)

This is the source and runtime-only package for the 15,936-instruction Dev100 candidate. It contains no puzzle CSV, submission, previous solution program, score baseline or checkpoint database. All native candidates are freshly constructed from the specified puzzle row. R8 portfolio and R12 free-basis+synthesis portfolio run independently; the smallest valid program is selected. R16 experimental multi-basis selector is deliberately excluded.

## Setup
Use Linux x86-64 (bundled binaries) or rebuild with GCC supporting C++17 and `__int128`. Tested Python 3.13.5 / NumPy 2.3.5 / SciPy 1.17.0. Install dependencies with `python -m pip install -r requirements.txt`. If needed run `./build.sh`. Place your original official `puzzles.csv` outside the extracted folder; the runner verifies the SHA-256 against `splits.json`. Never change the algorithm or binaries during one checkpoint experiment; a different environment or source fingerprint requires a new DB. MILP includes a wall-clock time limit, so exact per-puzzle scores may differ by machine and load.

## First complete holdout
From the extracted folder:
```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python variants/frozen17/run.py ../puzzles.csv --split holdout --db runs/holdout.sqlite --jobs 4 --limit 24
```
Repeat the same command until 100/100 complete. `--limit` is the number of unfinished group tasks per invocation, not number of puzzles. Both groups must finish to count one completed ID. New groups are generated from raw puzzle data, and verified before committing to SQLite. The existing DB is a checkpoint of this exact run only. Do not pass prior submission CSVs as solver inputs.

## Full independent test
```
mkdir -p runs
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python variants/frozen17/run.py ../puzzles.csv --split all --db runs/full.sqlite --jobs 4 --limit 64
```
Repeat until 1,000/1,000. To export a finished complete run:
```
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python variants/frozen17/run.py ../puzzles.csv --split all --db runs/full.sqlite --jobs 4 --limit 0 --export runs/submission.csv
python repo_verify.py ../puzzles.csv runs/submission.csv --report runs/validation.json
```
The full DB must start empty and independently reconstruct all 1,000 rows. Neither the development nor the holdout checkpoint is used by the full run. The exporter refuses an incomplete result; the independent verifier checks exactly matching IDs, register indices, defined operands, exact division, positive bounded arithmetic, instruction count and target coverage. The R8 group can log failed optional routes; inspect stored `errors` fields before interpreting the result as an exact full-portfolio reproduction. If a group fails completely it remains unfinished and can be retried. Only actual committed results count. No GitHub changes or network access are required.

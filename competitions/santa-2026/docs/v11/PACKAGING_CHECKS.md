# Packaging checks

- All 18 input archives (17 research rounds and final full-test archive) passed ZIP CRC checks.
- 476 Python source instances (including repeated historical snapshots) passed AST syntax parsing.
- Production build.sh and resume_full.sh passed Bash syntax validation. All eight production C++ binaries were successfully built using build.sh.
- Fresh official runner smoke test (two group tasks, new SQLite database, two workers): external execution time limit interrupted the invocation after one group was committed. SQLite integrity_check returned ok; scored_0001 basis group returned a valid 258-step program. The R8 group and full smoke test were not completed.
- The source-only rebuilt binary set differs from the archived frozen binaries in: order, factor. A fresh checkpoint database is required; do not reuse the original database with rebuilt binaries.
- Production verifier replayed the existing V11 submission and historic merged submission against the original official puzzles, independently confirming 1000/1000 valid each and scores 158955 and 158585, respectively. This is validation of existing submissions, not a fresh thousand-puzzle rerun.
- No GitHub actions, repository integration tests, or full new solve were performed for this packaging task. Historical research snapshots are retained as source archives, not independently built or certified.

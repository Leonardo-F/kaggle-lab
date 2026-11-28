# Santa V11 — final full independent test (checkpoint 10)

Frozen R16 portfolio, 1,000 official puzzles, original input SHA-256 `b0c70d849eca078a0e1cf9a4f7b47fd40b7435663f6f84de6725f84724500428`. The full run started from an empty database in checkpoint01 and resumed only its own checkpoints. The runner accepted the frozen configuration fingerprint throughout. No historical programs were used as solver input. V10 per-puzzle score metrics were read only during post-run audits. No GitHub modifications.

## Final results
- Complete: 1,000/1,000 (310 new in checkpoint10), 2,000/2,000 groups, no partial IDs.
- Score: **158,955**; V10 164,306; reduction 5,351 (3.2567283%).
- 848 better, 70 equal, 82 worse; gross improvements 5,660 and regressions 309 instructions.
- Independent audit: 12,556 candidate program instances validated, zero invalid, zero recorded optional route errors.
- Final submission independently validated: 1,000/1,000, score 158,955, maximum 348 steps.
- Submission SHA-256 `02d3cc0a1de5c5178ee212dbf674a01630c95375696a071e5f19c53b66aa57bb`.
- R8 group alone: 161,446; basis group alone: 161,711. R8 strictly wins 508 puzzles, basis strictly wins 399, ties 93. Full portfolio wins by complementary fresh construction.
- Group elapsed sum 10,464.631 seconds (not wall time).

## Execution and limitations
Eight bounded invocations (batch34–41), four workers, original solver parameters; tool calls were interrupted but the bounded processes continued within their 110-second limits and committed individual groups. Last batch completed normally. No further processes are required. Full export and independent verification completed. The optional R16 multi-basis experiment was not included in the frozen candidate. SciPy MILP has a wall-clock limit, so exact rerun scores can vary with machine and load. Score is locally validated, not a Kaggle leaderboard submission.

## Files
- `v11_frozen_fulltest/runs/submission.csv`: final submission
- `v11_frozen_fulltest/runs/validation.json`: final verifier output
- `v11_frozen_fulltest/runs/audit.json`: complete independent audit
- `v11_frozen_fulltest/runs/partial_scores.csv`: complete V10/V11 comparison (legacy filename)
- `v11_frozen_fulltest/runs/full.sqlite`: complete independent run checkpoint

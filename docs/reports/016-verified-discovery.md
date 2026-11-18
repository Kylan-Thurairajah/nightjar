# 016: Verified discovery

## Completed

Nightjar now distinguishes a likely contact from a confirmed objective. A sufficiently strong public belief marks a candidate; a manual drone can move to that cell and press `F` to check it. A correct check confirms the mission, while an incorrect one removes the false candidate and returns the mission to searching.

Verification is an explicit, one-tick action. It does not consume sensor randomness, and the result is included in replay archives. Existing histories without verification keep their version-1 format.

The terminal shows the current discovery phase, candidate location, verification prompt, and confirmed objective. The README, demo guide, manual test guide, architecture, design, roadmap, and milestone specification describe the updated flow.

## Validation

- Focused mission, discovery, presentation, replay, and UI tests: 71 passed.
- `mypy`: passed.
- Ruff lint: passed.
- Ruff formatting check for changed files: passed.
- Full test suite: 354 passed; `test_single_drone_and_random_archives_preserve_pre_coordination_baseline` retains a known pre-existing archive-hash mismatch (`cde04fd6...` expected, `0b073c3a...` actual).

## Remaining milestone work

This completes the manual verification slice. Persistent task assignments and autonomous verifier routing remain future work; automatic drones do not yet receive a dedicated verification assignment.

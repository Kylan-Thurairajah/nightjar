# Changelog

## Unreleased — local 0.1.0 preparation

- Deterministic synthetic GridWorld missions, validated configuration and preflight.
- Manual/AUTO/IDLE drone modes, collision checks, shared Bayesian inference and
  RANDOM, FRONTIER and INFORMATION GAIN policies.
- Hybrid fleet TUI control: one MANUAL drone, background AUTO drones, atomic
  selection handoff, preserved IDLE parking, off-loop serialized commands and replay-safe
  control restoration. Core serial fleet/global-budget rules remain unchanged.
- Fleet-wide visited knowledge and soft round-local target preferences for FRONTIER
  and INFORMATION GAIN; no fixed sectors or disjoint-route guarantee.
- Immutable public mission history, validated JSON viewing archives and read-only
  replay controls, including compact-terminal replay visibility.
- Offline reproducible policy benchmarking with raw metrics, descriptive means,
  software/source provenance and a documented measured example; publication is pending.
- Repository-native Codex specialists, scoped skills and incremental quality gates.

Release decisions and limitations: [checklist](docs/RELEASE.md).

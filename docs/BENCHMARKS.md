# Offline search-policy comparisons

Nightjar benchmarks its synthetic core, independently of the Textual event loop.
Run from an installed checkout with the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m nightjar.benchmark --help
.\.venv\Scripts\python.exe -m nightjar.benchmark --seeds 0 1 2 --ticks 50 --drones 1 --map compact --scenario open_field --sensor standard
```

The default command uses those same settings. JSON goes to stdout. To retain a new
local report, append `--output benchmark-repeat.json`. Output creation is exclusive:
choose a new filename if it exists. The command does not publish, contact services,
or overwrite an existing report.

## Protocol and reproducibility

Each seed runs RANDOM, FRONTIER and INFORMATION GAIN in fixed order with identical
environment, map, sensor, drone count and total simulation-tick ceiling. Drones are
set AUTO in roster order; the existing core fleet scheduler runs until budget or
mission-wide planner exhaustion. The default one-drone protocol isolates policy
behavior. `--drones 3` explicitly benchmarks the core's all-AUTO fleet protocol; it
does not represent user-driven hybrid TUI sessions: all benchmark drones are AUTO and there are no manual inputs.
Fleet runs use shared visited coverage and FRONTIER/INFORMATION GAIN soft round-local
target preferences. JSON labels this `shared_coverage_soft_round_targets`; RANDOM
ignores target claims. Claims do not imply nonoverlapping routes or sensing areas.

Equal budgets are equal ceilings, not a requirement to force an exhausted planner
to spend ticks. A STOP from one drone ends the whole mission, and a final partial
round stops as soon as the shared budget is exhausted. An ACTIVE round that makes no
progress is an error, not a reason to loop indefinitely.

Seed pairing provides the same geometry and hidden synthetic objective for the
compared policies. It does not provide identical readings: different routes and scan
orders consume sensor randomness differently. The planner's private random stream
is separate from sensing and obstacle/objective generation. No hidden objective
coordinates are supplied to the benchmark's planner or used for reported scoring.

Reports include versioned configuration/protocol, Python/NumPy/application versions
and a deterministic source fingerprint. No timestamps, machine-specific paths or
wall-clock measurements enter the deterministic output. Repeating the same arguments,
source bytes and software environment reproduces the report; different software
versions or changed source can change numerical results. A package version alone
does not identify an uncommitted checkout, hence the source fingerprint.

## Metrics

| Metric | Meaning |
| --- | --- |
| Budget / ticks consumed | Shared allowed ceiling versus actual accepted movement attempts plus scans |
| Rounds | Calls to the fleet scheduler, including a zero-tick terminal STOP round |
| Scans | Number of recorded observations |
| Movement attempts | Sum of drone-local movement ticks, including blocked attempts |
| Successful / blocked moves | Sum of path lengths minus initial positions; attempts minus successes |
| Unique visited / traversable cells | Union across drones, versus every non-obstacle map cell |
| Coverage | Unique visited divided by traversable; includes initial spawn cells and unreachable cells in the denominator |
| Initial / final entropy | Shared belief uncertainty in bits |
| Entropy reduction | Initial minus final entropy; may be negative after noisy evidence |
| Terminal reason | Actual budget or global planner exhaustion |

The UI's entropy change is final minus initial, so its sign is opposite the benchmark's
explicitly named reduction. Lower entropy means a more concentrated belief, not
necessarily a correct belief or a discovered objective. Coverage is physical visitation,
not sensor-radius coverage, probability mass searched or reachable-space completion.

Raw per-seed rows are the evidence. Descriptive strategy means and sample counts
summarize that exact matrix; they are not confidence intervals or significance tests.
There are no detection-accuracy, discovery, optimality or hardware-performance scores.

## Workload and limitations

The runner accepts 1–32 unique nonnegative seeds, 1–1000 ticks, 1–10 drones, and the
existing scenario/map/sensor presets. It runs sequentially and retains replay within
each mission; it does not alter simulation semantics to make benchmarks faster.
Completed simulations are released rather than retained as a matrix of timelines.
Larger maps, budgets and seed sets can still be expensive; run them explicitly outside
PR CI. Routine tests use small deterministic fixtures.

There is no sector allocation or independent per-drone STOP policy. Fixed starting
locations, roster priority, finite candidate models, sensing assumptions and stopping
rules all influence the results. Inspect methods and raw data before interpreting
differences. No claim generalizes automatically to other maps, seed sets or real systems.

## Measured example

The [raw example](benchmarks/compact-open-3seeds.json) contains nine measured runs:
three policies x seeds 0, 1 and 2; Compact/Open field, Standard sensor, one drone and
50 ticks. All nine reached budget exhaustion. It was generated with:

```powershell
.\.venv\Scripts\python.exe -m nightjar.benchmark --seeds 0 1 2 --ticks 50 --drones 1 --map compact --scenario open_field --sensor standard --output docs/benchmarks/compact-open-3seeds.json
```

That artifact is already present in the checkout. To repeat, use stdout or a new
`--output benchmark-repeat.json` path, then compare parsed reports. Environment:
Python 3.13.1, NumPy 2.5.4, Nightjar distribution version 0.1.0; the raw file records
the exact source fingerprint. Source-byte/line-ending changes can alter the hash.

| Policy | Seeds | Mean ticks | Mean scans | Mean visited coverage | Mean final entropy (bits) | Mean entropy reduction (bits) |
| --- | --- | --- | --- | --- | --- | --- |
| RANDOM | 3 | 50 | 7 | 6.60% | 7.3050 | 0.2496 |
| FRONTIER | 3 | 50 | 25 | 13.54% | 4.2363 | 3.3183 |
| INFORMATION GAIN | 3 | 50 | 8 | 20.31% | 4.5107 | 3.0439 |

These are descriptive results for this small matrix. FRONTIER reduced entropy more
than INFORMATION GAIN here, while INFORMATION GAIN visited more distinct cells.
Different routing, scan counts and stopping rules affect the tradeoff; the data do
not establish a universally best policy. In an independent short-budget fixture
(seed 3, two drones, seven ticks), INFORMATION GAIN spent all seven ticks moving
and took no scans, leaving entropy unchanged. This illustrates why actual scans and
metrics are reported rather than assuming intended information gathering succeeded.

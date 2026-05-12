# ADR-0001: Point-Adjust Evaluation Metrics

## Status
Proposed

## Context

M0 evaluation returns only 3 metrics: `precision`, `recall`, `f1`. These are standard point-wise metrics that treat each time point independently. In anomaly detection for time series, this is problematic: a continuous anomaly segment of 100 points where the algorithm detects just 1 point gets recall = 0.01, even though the algorithm successfully identified the anomaly event.

- Background: M1 introduces batch experiment comparison (排行榜). A single F1 metric is insufficient for meaningful algorithm ranking. PA-F1 is the de facto standard in time series anomaly detection benchmarks (TSB-UAD, NAB).
- Constraints: Must maintain backward compatibility (existing smoke tests pass); must not change `RunResult.metrics` data structure (`dict[str, float]`).
- Alternatives:
  1. Keep M0's 3 metrics only — insufficient for M1 ranking
  2. Add PA metrics alongside standard metrics — chosen: preserves M0 compatibility while enabling M1 ranking
  3. Replace standard metrics with PA metrics — breaks M0 contract

## Decision

Expand `evaluate()` return dict from 3 keys to 6 keys:

| Key | Description |
| --- | --- |
| `precision` | Standard TP/(TP+FP), point-wise |
| `recall` | Standard TP/(TP+FN), point-wise |
| `f1` | Standard 2PR/(P+R), point-wise |
| `pa_precision` | Point-Adjust Precision |
| `pa_recall` | Point-Adjust Recall |
| `pa_f1` | Point-Adjust F1 (ranking default sort key) |

**Point-Adjust logic**: For each contiguous anomaly segment in ground truth (y_true=1 run), if prediction hits any point in that segment, all points in the segment are counted as TP. Unhit segments are fully FN. FP remains point-wise.

**Behavior change**: `evaluate()` now fails fast on missing inputs:
- No LABEL column → `SchemaValidationError` (M0 returned silent zeros)
- No `predicted_label` column → `SchemaValidationError` (M0 raised KeyError)

**Chosen approach**: Option 2 — add PA metrics alongside standard metrics.
**Rationale**: Backward compatible (existing 3 keys still present), enables M1 ranking with PA-F1 as default sort, aligns with TSB-UAD benchmark convention.

## Consequences

### Positive
- M1 batch ranking can use PA-F1 as primary sort metric
- Detecting missing labels early prevents silent wrong results
- `RunResult.metrics: dict[str, float]` unchanged — no core/ structural change

### Negative
- 6 keys instead of 3 — downstream consumers must handle new keys
- PA metrics inflate TP count, which can mask point-wise precision issues
- Behavior change: callers expecting zeros on missing labels will now get exceptions

### Neutral
- SQLite `metrics` table stores each key as a row — 6 rows per run instead of 3

## Boundary Behavior

| Scenario | Standard P/R/F1 | PA-P/R/F1 |
| --- | --- | --- |
| All predictions 0 | P=0, R=0, F1=0 | P=0, R=0, F1=0 |
| All predictions 1 | P=TP/(TP+FP), R=1.0, F1=2PR/(P+R) | PA-R=1.0 (all segments hit), PA-P computed point-wise adjusted |
| No ground truth labels | `SchemaValidationError` | `SchemaValidationError` |
| No predicted_label | `SchemaValidationError` | `SchemaValidationError` |
| Empty input | `SchemaValidationError` | `SchemaValidationError` |
| Single-point anomaly segment hit | Standard R low, PA-R = 1.0 for that segment | PA-F1 > standard F1 |

## Compliance
- **Red line**: R1 — modifying metrics semantics in `pipeline/evaluate.py` (not `core/`, but `evaluate()` output contract affects `RunResult.metrics` content)
- **Scope**: pipeline (evaluate), core (RunResult.metrics content confirmation), tests

## References
- Related proposals: M1 PR-1 in docs/PLAN.md
- Related ADRs: None
- External: TSB-UAD benchmark methodology, NAB scoring
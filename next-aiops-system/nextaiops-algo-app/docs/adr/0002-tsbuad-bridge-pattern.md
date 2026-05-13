# ADR-0002: TSB-UAD Bridge Pattern (Adapter + Optional Dependency)

## Status
Accepted

## Context

M1 needs to expand the algorithm library beyond `three_sigma` and `iqr` to 5+ algorithms for meaningful batch comparison. TSB-UAD provides 5+ production-quality anomaly detection algorithms (IForest, LOF, OCSVM, PCA, HBOS), but it carries heavy dependencies (tensorflow, tslearn, stumpy, tsfresh) that would pollute the base installation and break CI.

- Background: M1 batch experiment ranking requires multiple algorithms to demonstrate comparison value. TSB-UAD algorithms are well-tested but the package has incompatible dependencies with our lightweight base.
- Constraints: Default install must remain lightweight; CI must not fail due to TSB-UAD dependencies; existing algorithms must continue working without extras.
- Alternatives considered:
  1. Vendor TSB-UAD source code — high maintenance cost, diverges from upstream
  2. Make TSB-UAD a hard dependency — breaks lightweight install and CI
  3. Adapter + optional dependency (chosen) — clean separation, graceful degradation

## Decision

Use the **Adapter pattern** with `TSB-UAD` as an **optional dependency** (`[tsbuad]` extras group).

- **Chosen approach**: `TSBUADAdapter` wraps TSB-UAD algorithm classes into the `AnomalyDetector` protocol. Conditional registration via import guard — algorithms only appear in REGISTRY when extras are installed.
- **Rationale**:
  - Adapter pattern preserves stable/variable separation (core/ untouched)
  - Optional dependency keeps base install clean and CI green
  - Import guard ensures graceful degradation without ImportError
  - M1 excludes deep learning algorithms (LSTM-AE, CNN) to control CI risk
  - KNN is not included because TSB-UAD documentation does not list it as a supported algorithm

## Consequences

### Positive
- Base install stays lightweight (numpy + pandas + sklearn + plotly)
- TSB-UAD algorithms integrate via REGISTRY without code changes
- CI runs fast without tensorflow dependency
- Users who install extras get instant access to 5 more algorithms

### Negative
- Two installation paths require dual testing (`make smoke` vs `make smoke-tsbuad`)
- Adapter must handle univariate-to-multivariate conversion (M1 uses per-column + max/OR strategy)
- TSB-UAD API inconsistencies (e.g., OCSVM) require per-class hooks in adapter

### Neutral
- TSB-UAD version pinned at 0.0.3 — future upstream changes may break adapter

## Compliance
- **Red line**: R6 (heavy dependency must be optional), R2 (algorithm must implement AnomalyDetector + register)
- **Scope**: algorithms (adapter), pipeline (conditional), pyproject.toml, Makefile

## References
- Related ADR: ADR-0001 (PA evaluation metrics needed for TSB-UAD batch ranking)
- TSB-UAD GitHub: https://github.com/TheDatumOrg/TSB-UAD
- TSB-UAD PyPI: https://pypi.org/project/TSB-UAD/
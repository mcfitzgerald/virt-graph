# Validation & Chaos Engineering

The generator includes a robust validation suite to ensure synthetic data mirrors real-world supply chain patterns.

## RealismMonitor

The `RealismMonitor` runs online during generation, inspecting batches of data as they are created. It uses O(1) space algorithms to validate:

### 1. Structural Integrity
*   **Pareto Principle:** Validates that the top 20% of SKUs generate ~80% of volume.
*   **Hub Concentration:** Ensures key accounts (e.g., MegaMart) hold realistic market share (20-30%).

### 2. Kinetic Dynamics
*   **Bullwhip Effect:** Verifies that order variance is higher than POS sales variance.
*   **Friction:** Tracks transport delays by mode (Truck, Ocean, Air) to ensure realistic lead time variability.

### 3. Strategic & Financial (New)
*   **Forecast Bias:** Tracks `(Forecast - Actual) / Actual` to detect systematic over/under-planning.
*   **Return Rate:** Monitors the ratio of `returns` to `sales` volume (Target: 2-5%).
*   **Margin Integrity:** Checks for excessive discounting (>50%) that would destroy gross margin.

## Chaos Injection

To support "Beast Mode" testing, the generator injects deterministic anomalies defined in `benchmark_manifest.json`.

### Risk Events
Deterministic scenarios that trigger specific data patterns:
*   **RSK-BIO-001 (Contamination):** Forces a specific batch of Sorbitol to be `REJECTED`, enabling recall trace testing.
*   **RSK-LOG-002 (Port Strike):** Switches delay distribution from Poisson (normal) to Gamma (fat-tail), creating massive delays at USLAX.
*   **RSK-CYB-004 (Cyber Outage):** Freezes pick waves at Chicago DC (Status: `ON_HOLD`).

### Quirks
Behavioral pathologies that occur probabilistically:
*   **Optimism Bias:** Planners systematically over-forecast new product launches by 15%.
*   **Phantom Inventory:** Random 2% shrinkage injected into inventory records.
*   **Bullwhip Crack:** Retailers batch orders during promotions, amplifying demand signals.

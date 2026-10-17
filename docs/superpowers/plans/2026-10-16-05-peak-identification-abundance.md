# Peak Identification and Abundance Table Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox syntax for tracking. Implementation requires a separate user instruction; this plan is a proposed design.

**Goal:** Suggest atomic ion identities and compare observed isotope signals with reference abundances.

**Architecture:** Use a versioned offline isotope catalog and an explicit mass/charge matcher, then compute observed areas with the shared signal reader. Separate candidate suggestions, file labels and measured/reference abundance columns.

**Tech Stack:** Python, versioned local isotope data, NumPy, AnyWidget, Plotly, unittest, Playwright

**Spec:** [Roadmap design brief, section 5](../specs/2026-10-16-roadmap-design.md).

## Global Constraints

- Keep Marimo + AnyWidget + Plotly; do not introduce Panel.
- Treat frame limits as zero-based and inclusive.
- Do not change source HDF5 files except through explicit write-back.
- Preserve existing shared ROI, All depths, maximize/restore, and offline operation.
- Scientific transforms must not silently change analysis intensities.

## Dependencies and file boundaries

Requires the `SignalRecipe`/`read_signal` interfaces from the disjoint-window plan. Depth calibration is optional; frame bounds remain the integration domain. Create `isotopes.py` for matching/reference parsing and `abundance.py` for observation aggregation; store attributed reference data under `data/reference/`.

## Review Focus

- Isobaric candidates and exact ties must remain visible rather than auto-labeling a peak (Task 1).
- Ppm tolerance is mass-dependent; charge/polarity and ionic-mass convention cannot be inferred from a nominal label (Task 1).
- Abundance intervals, missing abundances and enriched samples must not become precise expected fractions (Tasks 1, 2).
- Overlapping isotope windows and zero-total/partial coverage must not yield misleading independent fractions (Task 2).
- Changing candidates must not overwrite original file labels or reconstruct many channels without an explicit request (Task 3).

### Task 1: Establish an attributed isotope catalog and matcher

**Files:** Create `isotopes.py`, `data/reference/isotopes.json`, `data/reference/README.md`, `scripts/update_isotope_reference.py`, `tests/test_isotopes.py`.

**Interfaces:** `IsotopeRecord(symbol, mass_number, neutral_mass_u, abundance_low, abundance_high, source_id)`; `load_catalog(path=None) -> tuple[IsotopeRecord,...]`; `ion_mz(record, charge: int) -> float`; `find_candidates(mz: float, tolerance: float, tolerance_unit: str, charges: tuple[int,...], catalog) -> list[IonCandidate]`. Candidate fields include signed charge, predicted m/z, signed Th/ppm error and reference provenance.

- [ ] Write synthetic-catalog tests at neutral masses 10 and 12 for both Th and ppm tolerance, inclusive boundaries, tied masses, zero m/z, invalid tolerance, and forbidden charge zero/outside ±1..3. Check positive and negative electron corrections against separately sourced reference fixtures, not rounded atomic weights.
- [ ] Test abundance ranges and absent values survive parsing/serialization. Each catalog has a recorded source revision/retrieval date, license/redistribution review and checksum; invalid reference records fail validation rather than being dropped silently.
- [ ] Run `uv run python -m unittest discover -s tests -p 'test_isotopes.py' -v`; verify failure, then implement exact-mass matching, deterministic error ordering and explicit polarity. The convention starts from neutral isotope mass, accounts for signed electron count, and documents omitted binding-energy corrections.
- [ ] Build the offline catalog from NIST isotope masses and CIAAW abundance values/ranges. The update script runs manually; app startup never downloads data. Pin the chosen reference releases and verify one mono-isotopic and one multi-isotopic element against their source tables.
- [ ] Run matcher/catalog tests. Commit: `Add offline isotope mass candidate matching.`

### Task 2: Compute explicit observed isotope areas

**Files:** Create `abundance.py`, `tests/test_abundance.py`; modify `signals.py` only through its documented public reader interface.

**Interfaces:** `measure_isotopes(path, recipes: Sequence[SignalRecipe], roi: tuple[int,int,int,int], frames: tuple[int,int]) -> list[IsotopeMeasurement]`. A row records recipe/reference ID, requested and actual coverage, summed original intensity, observed selected-set fraction or null, reference interval, and ambiguity/status. Measured ratios are not inferred atomic concentration.

- [ ] Write tests for two non-overlapping synthetic isotope signals of 30 and 70 normalized counts: measured selected-set fractions 0.3/0.7. Zero totals yield null fractions; missing coverage stays missing. ROI and frame changes must produce independently verified sums of original values.
- [ ] Test same/overlapping mass-window recipes: mark those rows ambiguous and suppress an independent observed-fraction estimate until overlap is resolved. If recipes have different frame coverage, require their common covered interval for a ratio, display it explicitly, and return unavailable when it is empty.
- [ ] Run `uv run python -m unittest discover -s tests -p 'test_abundance.py' -v`; verify failure, then implement through `read_signal`. Do not sum rounded CSV or logarithmic display arrays. Preserve reference abundance ranges; avoid deriving sample composition or confidence probabilities.
- [ ] Add regression fixtures for a mono-isotopic reference, an isotope without a natural abundance, and an enriched-sample observation far from the natural expectation; report the observation without forcing a fit to natural abundance.
- [ ] Run all numerical tests. Commit: `Measure isotope areas with explicit coverage and ambiguity.`

### Task 3: Ship identification assistance and the abundance table

**Files:** Create `web/peak_helper.js`, `scripts/check_peak_helper.py`; modify `workspace.py`, `web/workspace.js`, `web/workspace.css`, `README.md`.

**Interfaces:** `peak_candidates {mz,tolerance,unit,charges}` returns candidate records only; `abundance_measure {recipes,frames,roi}` explicitly starts integration with progress. `peak_assignment {recipe_id,candidate_id}` records a user annotation while preserving the original file label. Reference metadata travels with assignments and exports.

- [ ] Write a failing browser scenario opening the helper from a selected spectrum peak, changing tolerance/polarity, inspecting two candidates, selecting an annotation, and explicitly measuring a requested isotope set. Verify source label and primary signal are unchanged until the user chooses an analysis action.
- [ ] Test empty matches, nominal bins spanning several identities, isobars, measured/reference columns, abundance ranges, enriched observations, and missing/overlap statuses. Verify sorting and CSV headers remain stable for similar isotope names/charges.
- [ ] Implement a compact helper dialog and abundance tab/table with element/isotope, charge, predicted m/z, mass error, reference abundance, measured area and observed fraction. Offer Add as comparison and Apply window as explicit actions. Molecular/adduct search remains excluded and is stated in help.
- [ ] Run `uv run python scripts/check_peak_helper.py` with the app and all isotope/abundance tests. Verify the feature works offline and no candidate-list request triggers full raw reconstruction.
- [ ] Update README and commit: `Add peak identification and isotope abundance inspection.`

## Acceptance

Users can see plausible atomic-ion identities, explicitly choose one, and compare measured isotope signals with attributed reference expectations without silently turning an ambiguous spectrum into a chemical assignment.

## References

- [NIST isotope masses](https://www.nist.gov/pml/atomic-weights-and-isotopic-compositions-relative-atomic-masses).
- [CIAAW isotope abundances](https://ciaaw.org/isotopic-abundances.htm).

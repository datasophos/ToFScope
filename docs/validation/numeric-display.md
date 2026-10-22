# Compact numeric display audit

Manual review on 2026-10-21 found long floating-point tails in identification
window bounds and requested a review of the whole application. The audit covers
floating-point inputs, summaries, candidate/measurement tables, stored-channel
picker labels, plot cursor positions and renderer tooltips.

`PreciseNumberInput` now provides a common pattern: compact values while reading,
full exact strings on focus, select-on-focus for editing, and an exact-value
hover title. Formatting never updates the stored string. Identification mass,
tolerance and window bounds plus calibration depth/anchor fields use up to four
decimal places; the existing custom signal editor keeps its two-place compact
presentation through the same component. Tolerance spinners advance by 0.1,
while smaller manually entered tolerances remain valid.

`formatNumber` suppresses insignificant trailing zeros and floating-point noise
in normal values, with scientific notation for small nonzero and large values.
The audit applies it to calibration summaries, measured intensity sums/fractions,
candidate masses/uncertainties, stored signal masses and plot readouts/tooltips.
Existing bounded axis tick, file-size and percentage formatters remain suitable;
frame/ROI indices remain integers. Exact metadata is retained for editing,
annotations, scientific calculations, API commands and exported data. Signal
search accepts both the displayed rounded mass and the full raw mass.

Verification includes formatter tests for floating-point tails, signed/zero,
missing/nonfinite, tiny and large values; stored-signal search tests for rounded
and exact values; and a browser workflow submitting exact mass intervals
`[1.387507820129395, 1.587507820129394]` after compact display and an exact
`13.387507820129395` nm depth anchor after showing `13.3875`. Existing calibration,
interval, panning and signal-editing browser workflows also passed.

The rebuilt packaged UI is served by the existing local port-8765 process;
no backend restart or duplicate app tab is needed. The confirmed local dataset
directory remains recorded in private agent memory, outside git.

Final verification: 30 frontend tests and all 71 browser workflows passed;
TypeScript and packaged asset build passed. Independent review found no
remaining scientific-precision or focus-handling issues. Its rounded-mass search
finding was reproduced and fixed with dedicated exact/rounded-search tests.

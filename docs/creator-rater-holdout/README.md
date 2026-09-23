# Creator-versus-rater holdout

This untouched holdout uses `survey/sources/cat-on-keyboard.jpg`, whose verified public-domain
credit is copied into `report.json`. It was run after the first outdoor-cat experiment with the
same local models, 512×512 output, seed 42, three rating trials, and one proposed refinement.

The first attempt failed closed before producing evidence because the detailed Ollama response was
truncated into invalid JSON under its 4,096-token runner context. The encoder request was raised to
8,192 tokens and the complete run then succeeded. This failed attempt is recorded in the living
implementation log, not counted as a result.

The finished holdout rejected the challenger: the pixels-only judge preferred whichever candidate
appeared second, so the order-reversed logical verdicts disagreed. No deterministic guard regressed.
The deterministic proxy was effectively unchanged (0.669898 baseline, 0.669543 challenger), while
the experimental semantic median fell from 75 to 70. Visual inspection also found that both
generated images remain materially different from the source in crop, keyboard geometry,
markings, sharpness, and exact identity.

`report.json` is authoritative for settings, byte sizes, times, source credit, raw trials, reasons,
and the rejection. This is one uncalibrated holdout, not evidence that the automatic rater agrees
with human perception.

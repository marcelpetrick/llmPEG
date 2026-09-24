# Closed-loop and regrade tone evidence, v2 (colourfulness)

The [`../tone-feedback/`](../tone-feedback/README.md) run repeated after two fixes (2026-09-24):
colour is judged by Hasler–Süsstrunk colourfulness instead of mean HSV saturation, and the regrade
scales chroma with a capped gain instead of HSV saturation.

- `artifacts/`: the 13 review and held-out artifacts with their tone re-measured from the verified
  source by `scripts/upgrade_tone.py` (format 1.2, written by llmpeg 0.8.0). Every model-written
  field is unchanged, and all 13 render byte-identical prompts to the originals.
- `measurements.json`: `scripts/tone_feedback.py --artifacts-dir …/artifacts` over seeds 42, 7, and
  1234 — tone (with colourfulness) of `control`, `loop`, and `matched`, plus proxy scores.
- `contact-sheet.jpg`: all 13 sources at seed 42, downscaled for viewing only.

Because prompts are identical and renders are deterministic, the `control` renders were copied from
the earlier runs, and 19 `loop` renders whose negatives did not change were copied from v1; the
other 20 were rendered fresh. Only the seven seed-42 `loop` PNGs shown on `survey/qwen.html` are
checked in; the rest (about 60 MB) regenerate bit-for-bit. Write-up:
[`docs/tone.md`](../../../docs/tone.md), attempt 7.

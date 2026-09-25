# Colourfulness wording in the prompt: rejected

A test run (2026-09-25) of one prompt change: for format 1.2 artifacts, describe colour in the
`Tone:` line with Hasler and Süsstrunk's category words and the colourfulness figure ("moderately
colourful … (colourfulness 32)") instead of the mean HSV saturation figure. The 13 upgraded
artifacts in [`../tone-feedback-v2/artifacts/`](../tone-feedback-v2/README.md) were rendered with
the changed prompt by `scripts/tone_feedback.py` at seeds 42 and 7 (`control` and `loop`).

`measurements.json` holds those 78 rows. Compared with the same artifacts, seeds, and variants in
`../tone-feedback-v2/measurements.json`, which used the unchanged prompt, the mean absolute
colourfulness error of the `control` render went from 7.9 to 8.2: better for 6 of 26 source-seed
pairs, worse for 12. Luminance was unchanged (27.8 → 28.1). The change was **not adopted**; the
renders are not checked in, and the code that produced them was reverted before any commit.

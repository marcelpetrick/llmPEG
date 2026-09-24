# Closed-loop and regrade tone evidence

Output of `scripts/tone_feedback.py` (2026-09-24): all 13 survey sources (the three cats from
[`../review/`](../review/) and the ten held-out sources from [`../tone-holdout/`](../tone-holdout/)),
each at seeds 42, 7, and 1234, local ComfyUI/Qwen-Image-2.1 at 512×512 and CFG 3.5:

- `control`: the current pipeline's render. The seed-42 controls were copied from the review and
  held-out runs, whose renders are deterministic;
- `loop`: a second render at the same seed with negative-prompt terms chosen from the sign of each
  measured error of the `control` render against the artifact's recorded tone
  (`llmpeg.grading.feedback_negative`);
- `matched`: the `control` render regraded toward the recorded tone (`llmpeg.grading.match_tone`),
  a post-process that reads the artifact, never the source.

`measurements.json` holds every row: tone, the negatives used, and the deterministic
`visual_proxy_score` and `histogram_similarity` against the source. `contact-sheet.jpg` shows the
seed-42 renders of all 13 sources, downscaled for viewing only.

Only the 14 seed-42 `loop` and `matched` PNGs that `survey/qwen-tone.html` shows are checked in; the
other 103 renders (48 MB) are reproducible bit-for-bit with the script. The write-up is in
[`docs/tone.md`](../../../docs/tone.md).

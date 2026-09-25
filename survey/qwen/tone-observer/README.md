# Observer prompt with the closed loop

Output of `scripts/tone_feedback.py --prompt observer --artifacts-dir ../tone-feedback-v2/artifacts
--seeds 42 7` (2026-09-25): the 13 format 1.2 artifacts rendered with the `observer` prompt from
`scripts/tone_prompt_sweep.py` — one observing paragraph in the register of Qwen's own prompt
rewriter, with no labels, hex codes, canvas size, or instructions — as `control`, `loop`, and
`matched`.

- `measurements.json`: 78 rows with tone, colourfulness, and proxy scores.
- `contact-sheet.jpg`: seed 42, source beside pipeline prompt + loop, observer, and observer + loop,
  downscaled for viewing only.

The observer prompt leaves out the artifact's critical-text list, so it is not yet a drop-in
replacement for the pipeline prompt. Renders are not checked in; the script regenerates them
bit-for-bit. Write-up: [`docs/tone.md`](../../../docs/tone.md), attempt 9.

# Observer prompt that keeps critical text

`scripts/tone_feedback.py --prompt observer-text` over the 13 format 1.2 artifacts in
[`../tone-feedback-v2/artifacts/`](../tone-feedback-v2/README.md) at seeds 42 and 7 (2026-09-25):
the `observer` paragraph plus one sentence quoting the artifact's critical text, the way Qwen's
prompt rewriter copies visible text.

- `measurements.json`: tone, colourfulness, and proxy scores for `control`, `loop`, and `matched`.
- `text-recall.json`: `scripts/text_recall.py` over the `control` renders of three prompts —
  pipeline, observer, and observer-text — with every transcript kept.

Text survival is read by the local `qwen3.5:4b` model, not an OCR engine, so a misread counts as
lost; the three prompts are read the same way. Of 78 expected strings (8 sources × 2 seeds), the
reader found 27 in pipeline renders, 13 in observer renders, and 25 in observer-text renders.
Renders are not checked in; the scripts regenerate them. Write-up:
[`docs/tone.md`](../../../docs/tone.md), attempt 10.

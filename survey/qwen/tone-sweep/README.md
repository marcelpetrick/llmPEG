# Tone sweep evidence

Output of `scripts/tone_sweep.py` (2026-09-23): the three prompts in [`../review/`](../review/)
re-rendered by local ComfyUI/Qwen-Image-2.1 with one generator setting changed at a time. The
`default` renders are a control and are pixel-identical to the review run's.

`measurements.json` holds each render's settings, extra negative terms, and source vs.
reconstruction tone. The write-up and its caveats are in [`docs/tone.md`](../../../docs/tone.md).

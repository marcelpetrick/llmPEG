# Prompt-isolation tone evidence

Output of `scripts/tone_prompt_sweep.py` (2026-09-24): the three review artifacts in
[`../review/`](../review/) turned into seven prompt variants by rule, each rendered by local
ComfyUI/Qwen-Image-2.1 at 512×512, seed 42, under two settings: the bundled workflow (CFG 3.5,
30 steps) and ComfyUI's official Qwen-Image-2.1 template (CFG 1, 25 steps).

- `measurements.json`: every render's setting, prompt variant, and source vs. reconstruction tone;
- `<case>-<setting>-<variant>.prompt.txt`: the exact text the generator received;
- `contact-sheet.jpg`: all 42 renders beside their sources, downscaled for viewing only.

The 42 full-size PNGs (25 MB) are not checked in. At a fixed seed the generator is deterministic:
the `workflow`/`control` renders are pixel-identical to the review run's, as the earlier
`tone-sweep/` control was. `uv run python scripts/tone_prompt_sweep.py` regenerates them.

The write-up is in [`docs/tone.md`](../../../docs/tone.md).

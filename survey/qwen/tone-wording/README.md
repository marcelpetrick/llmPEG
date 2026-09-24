# Encoder colour-wording evidence

Output of `scripts/tone_wording.py` (2026-09-24). All 13 survey sources were re-encoded by local
Ollama `qwen3.5:4b` (`detailed`, format 1.1) with one extra line in the vision instruction, then
rendered with the plain pipeline prompt at seed 42:

> Name each colour as it looks in this photograph, with a modifier such as pale, faded, greyish,
> muted, or deep; never intensify it with bright, vivid, lush, or rich unless that is unmistakable.

The line was **not adopted** and is not in `src/llmpeg/providers.py`; see
[`docs/tone.md`](../../../docs/tone.md), attempt 6. `measurements.json` compares each render's tone
with the earlier artifact's seed-42 render and counts intensifying colour words in both artifacts.
The 13 renders are not checked in; `llmpeg generate <artifact> --resolution 512 --seed 42`
reproduces each one from its checked-in artifact.

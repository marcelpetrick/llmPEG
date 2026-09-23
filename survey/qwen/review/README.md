# Single-page review run: one reconstruction per source

The first live run of `scripts/review_cycle.py` (2026-09-23), made after one human reviewer rated
the earlier Qwen reconstructions as too saturated. It is the first run with format 1.1 artifacts:
each carries a pixel-measured `tone` object, and the rendered prompt carries a `Tone:` line plus a
"do not brighten, add contrast, boost saturation, or apply HDR" instruction.

The three sources are the public-domain cat photographs credited in `survey/manifest.json`.

## Settings

- Encoder: local Ollama `qwen3.5:4b`, `detailed` profile, temperature 0, seed 42, `/no_think`.
- Generator: local ComfyUI/Qwen-Image-2.1, prompt text only, 512×512, seed 42, 30 steps, CFG 3.5,
  Euler, simple scheduler, the bundled workflow's negative prompt.
- llmPEG 0.5.1.

## Results

Taken from `report.json`. Ratios are source bytes over the artifact as stored, 228-byte header
included; the gzip ratio is against the `.llmpeg.json.gz` file, gzip framing included.

| Case | Plain bytes | Plain ratio | Gzip bytes | Gzip ratio | Status |
| --- | ---: | ---: | ---: | ---: | --- |
| `cat-monochrome` | 2,529 | 136.7:1 | 1,374 | 251.7:1 | pass |
| `cat-on-keyboard` | 2,300 | 266.3:1 | 1,273 | 481.1:1 | incomplete |
| `cat-on-grass` | 2,875 | 278.3:1 | 1,531 | 522.5:1 | fail |

Tone, source → reconstruction (luminance, contrast, saturation on 0–255; warmth is mean red minus
mean blue):

| Case | Luminance | Contrast | Saturation | Warmth |
| --- | --- | --- | --- | --- |
| `cat-monochrome` | 125 → 67 | 61 → 62 | 0 → 11 | 0 → −1 |
| `cat-on-keyboard` | 148 → 111 | 55 → 46 | 48 → 88 | −5 → 40 |
| `cat-on-grass` | 158 → 124 | 24 → 33 | 89 → 126 | 51 → 47 |

**The tone instruction did not fix saturation.** The keyboard cat is as saturated as before the
change (78.5–88.4 in the creator/rater holdout run, `docs/tone-review-plan.md`), the grass cat
overshoots by 37, and all three renders are darker than their sources. See [`docs/tone.md`](../../../docs/tone.md) for the follow-up sweep
and what did move the numbers.

The composition-region fix did hold: the 11 regions across the three artifacts are distinct
percentage boxes, and none repeats the instruction's former example box.

## Files

- `<case>.llmpeg.json.gz`: the artifact, as written by the encoder;
- `<case>.prompt.txt`: the text the generator received, and nothing else;
- `<case>.png`: the reconstruction;
- `<case>-result.json`: deterministic proxy metrics (see `docs/metrics.md` for why they are not a
  perception score);
- `report.json`: settings, sizes, timings, and source vs. reconstruction tone.

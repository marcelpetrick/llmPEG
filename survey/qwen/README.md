# Local Qwen-Image-2.1 comparison evidence

`survey/qwen.html` now shows the single-reconstruction review in [`review/`](review/README.md),
with tone experiments in [`tone-sweep/`](tone-sweep/README.md) and
[`docs/tone.md`](../../docs/tone.md). The two creator/rater runs below are **superseded** as the
published page and kept as evidence.

This directory contains the two creator/rater runs that `survey/qwen.html` used to show. Both
source photographs are existing public-domain survey sources; their credits are copied into each
authoritative `report.json` and into `survey/qwen-manifest.json`.

## Measured pipeline

1. Local Ollama `qwen3.5:4b` receives the original image and writes a `detailed` llmPEG artifact.
2. llmPEG renders the artifact into a generator-neutral text prompt.
3. Ollama releases its model allocation before generation so both local stages can share the
   available GPU memory.
4. Local ComfyUI loads Qwen-Image-2.1 and receives the text prompt only. The source image is never
   included in the ComfyUI workflow.
5. The measured workflow generates 512×512 pixels with seed 42, 30 steps, CFG 3.5, Euler sampling,
   and the simple scheduler.
6. Local Qwen-VL rates source versus reconstruction in repeated trials. A creator/rater round
   proposes a challenger, then makes two pixels-only pairwise judgments with A/B order reversed.

This is reconstruction, not decompression: Qwen-Image-2.1 invents a new image from text and cannot
recover the original pixels.

## Results

| Evidence | Baseline proxy | Challenger proxy | Semantic median | Outcome |
| --- | ---: | ---: | ---: | --- |
| `creator-rater/` | 0.632194 | 0.700023 | 85 → 80 | challenger rejected |
| `creator-rater-holdout/` | 0.669898 | 0.669543 | 75 → 70 | challenger rejected |

In both runs the pairwise judge preferred whichever candidate appeared second. Reversing image
order therefore reversed the logical preference, so neither challenger was accepted. These two
runs demonstrate the local pipeline and a rater failure mode; they do not demonstrate improved
human-perceived similarity.

Each evidence directory contains baseline and challenger artifacts, rendered prompts, generated
PNGs, a provenance README, and the authoritative `report.json`. The `*-result.json` files are
small derived records used only by the generic HTML renderer; tests require their deterministic
metric objects to equal the corresponding objects in `report.json` exactly.

Regenerate the public comparison with:

```bash
uv run llmpeg survey survey/qwen-manifest.json --output survey/qwen.html --overwrite
```

The Qwen-Image-2.1 weights are not included in this repository and use the non-commercial Qwen
Research licence.

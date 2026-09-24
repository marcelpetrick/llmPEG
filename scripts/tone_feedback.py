"""Compare two tone corrections that do not guess which way Qwen-Image-2.1 will miss.

A fixed tone rule helped some held-out sources and hurt others, because Qwen pulls each image
toward its own look in either direction (`docs/tone.md`, attempt 4). Both corrections here look at
the render first:

- ``loop``: render, measure the render's tone, add negative-prompt terms chosen from the *sign* of
  each error against the artifact's recorded tone, and render once more with the same seed.
- ``matched``: deterministically regrade the ``control`` render toward the artifact's recorded
  tone. It is a post-process that reads the artifact, never the source.

Every case is rendered at several seeds so no effect rests on one. Artifacts come from
`survey/qwen/review/` (the cats) and `survey/qwen/tone-holdout/` (everything else).
"""

from __future__ import annotations

import argparse
import io
import json
import os
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image

from llmpeg import __version__
from llmpeg.artifact import Artifact, Tone
from llmpeg.encoder import MONOCHROME_SATURATION, measure_tone, render_generation_prompt
from llmpeg.evaluation import evaluate_with_artifact
from llmpeg.generators import DEFAULT_COMFYUI_HOST, generate_comfyui

REPO = Path(__file__).resolve().parent.parent
CATS = ("cat-monochrome", "cat-on-keyboard", "cat-on-grass")
HOLDOUT = (
    "amsterdam-market",
    "astronaut-crew",
    "dogs-beach",
    "food-table",
    "kitchen-table",
    "living-room",
    "mountain-hikers",
    "street-bicycles",
    "train-platform",
    "workspace-books",
)
SEEDS = (42, 7, 1234)
RESOLUTION = 512
# An error inside these margins (0-255 scale) is left alone.
MARGIN = {"luminance": 12, "contrast": 8, "saturation": 12, "warmth": 12}
# Negative terms for a render that is too high (first) or too low (second) on each measure.
FEEDBACK = {
    "luminance": ("overexposed, too bright", "dark, underexposed, dim"),
    "contrast": ("harsh contrast, deep black shadows", "flat, hazy, low contrast"),
    "saturation": ("vivid colors, saturated colors", "dull colors, desaturated, grey, washed out"),
    "warmth": ("warm color cast, orange tint, yellow tint", "cool color cast, blue tint"),
}
MATCH_ROUNDS = 6


def feedback_negative(target: Tone, rendered: Tone) -> str:
    """Negative terms that push each measure of the render back toward the recorded tone."""
    terms: list[str] = []
    if target.saturation < MONOCHROME_SATURATION and rendered.saturation >= MONOCHROME_SATURATION:
        terms.append("color, colour, tint, sepia")
    for name, (too_high, too_low) in FEEDBACK.items():
        error = getattr(rendered, name) - getattr(target, name)
        if name in {"saturation", "warmth"} and target.saturation < MONOCHROME_SATURATION:
            continue
        if error > MARGIN[name]:
            terms.append(too_high)
        elif error < -MARGIN[name]:
            terms.append(too_low)
    return ", ".join(terms)


def match_tone(image: Image.Image, target: Tone) -> Image.Image:
    """Regrade an image toward a recorded tone with global, deterministic adjustments.

    Each round measures the image, then applies one affine map to all three channels (which moves
    mean luminance and its spread exactly, before clipping), scales HSV saturation, and shifts red
    against blue for warmth. Clipping makes one round inexact, so it repeats a few times.
    """
    graded = image.convert("RGB")
    for _ in range(MATCH_ROUNDS):
        now = measure_tone(graded)
        gain = target.contrast / max(now.contrast, 1)
        offset = target.luminance - now.luminance * gain
        graded = graded.point(lambda value, g=gain, o=offset: round(value * g + o))
        if target.saturation < MONOCHROME_SATURATION:
            graded = graded.convert("L").convert("RGB")
        else:
            now = measure_tone(graded)
            scale = target.saturation / max(now.saturation, 1)
            hue, sat, val = graded.convert("HSV").split()
            sat = sat.point(lambda value, k=scale: round(value * k))
            graded = Image.merge("HSV", (hue, sat, val)).convert("RGB")
            shift = (target.warmth - measure_tone(graded).warmth) / 2
            red, green, blue = graded.split()
            red = red.point(lambda value, d=shift: round(value + d))
            blue = blue.point(lambda value, d=shift: round(value - d))
            graded = Image.merge("RGB", (red, green, blue))
    return graded


def _artifact(case: str) -> Artifact:
    folder = "review" if case in CATS else "tone-holdout"
    return Artifact.from_file_bytes(
        (REPO / "survey/qwen" / folder / f"{case}.llmpeg.json.gz").read_bytes()
    )


def _row(
    case: str, seed: int, variant: str, path: Path, artifact: Artifact, extra: str
) -> dict[str, Any]:
    with Image.open(path) as image:
        tone = measure_tone(image)
    evaluation = evaluate_with_artifact(REPO / "survey/sources" / f"{case}.jpg", path, artifact)
    return {
        "case": case,
        "seed": seed,
        "variant": variant,
        "extra_negative": extra,
        "image": path.name,
        "source_tone": asdict(artifact.tone) if artifact.tone else None,
        "reconstruction_tone": asdict(tone),
        "visual_proxy_score": evaluation.metrics.visual_proxy_score,
        "histogram_similarity": evaluation.metrics.histogram_similarity,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for seed in args.seeds:
        for case in args.cases:
            artifact = _artifact(case)
            if artifact.tone is None:
                raise SystemExit(f"{case}: artifact has no tone")
            prompt = render_generation_prompt(artifact)
            control = output_dir / f"{case}-s{seed}-control.png"
            if not control.exists():
                control.write_bytes(generate_comfyui(prompt, RESOLUTION, seed, args.comfyui_host))
            rows.append(_row(case, seed, "control", control, artifact, ""))

            with Image.open(control) as image:
                extra = feedback_negative(artifact.tone, measure_tone(image))
                matched = output_dir / f"{case}-s{seed}-matched.png"
                match_tone(image, artifact.tone).save(matched)
            rows.append(_row(case, seed, "matched", matched, artifact, ""))

            loop = output_dir / f"{case}-s{seed}-loop.png"
            if not loop.exists():
                image_bytes = (
                    generate_comfyui(
                        prompt, RESOLUTION, seed, args.comfyui_host, extra_negative=extra
                    )
                    if extra
                    else control.read_bytes()
                )
                loop.write_bytes(image_bytes)
            rows.append(_row(case, seed, "loop", loop, artifact, extra))
            with Image.open(io.BytesIO(loop.read_bytes())) as image:
                print(f"{case} s{seed}: {artifact.tone} -> loop {measure_tone(image)}", flush=True)

    result = {
        "llmpeg_version": __version__,
        "generator": "local ComfyUI/Qwen-Image-2.1",
        "resolution": RESOLUTION,
        "margins": MARGIN,
        "feedback_terms": FEEDBACK,
        "rows": rows,
    }
    (output_dir / "measurements.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO / "survey/qwen/tone-feedback")
    parser.add_argument("--cases", nargs="+", default=[*CATS, *HOLDOUT], choices=[*CATS, *HOLDOUT])
    parser.add_argument("--seeds", nargs="+", type=int, default=list(SEEDS))
    parser.add_argument(
        "--comfyui-host", default=os.environ.get("LLMPEG_COMFYUI_HOST", DEFAULT_COMFYUI_HOST)
    )
    run(parser.parse_args())


if __name__ == "__main__":
    main()

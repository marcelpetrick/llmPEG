"""Measure which Qwen-Image-2.1 settings move reconstruction tone toward the source.

The review cycle's prompts carry a pixel-measured ``Tone:`` line, yet reconstructions still came
back darker, more saturated, and warmer than their sources. This sweep holds each prompt fixed and
changes one generator setting at a time (guidance scale, or extra negative-prompt terms), then
measures the render's tone with the same function the encoder uses on sources. The ``default``
variant repeats the review cycle's settings as a determinism control.
"""

from __future__ import annotations

import argparse
import io
import json
import os
from dataclasses import asdict
from importlib import resources
from pathlib import Path
from typing import Any

from PIL import Image

from llmpeg import __version__
from llmpeg.encoder import measure_tone
from llmpeg.generators import (
    DEFAULT_COMFYUI_HOST,
    DEFAULT_QWEN_SEED,
    WORKFLOW_RESOURCE,
    generate_comfyui,
)

REPO = Path(__file__).resolve().parent.parent
CASES = ("cat-monochrome", "cat-on-keyboard", "cat-on-grass")
RESOLUTION = 512
COMMON_NEGATIVE = "dark, underexposed, studio lighting, professional color grading, vivid colors"
# Chosen by hand after looking at the default renders, so they are per-case and not yet a rule
# the renderer could derive from an artifact. A derived version needs its own measured run.
TONE_NEGATIVES = {
    "cat-monochrome": "color, colour, tint, sepia, " + COMMON_NEGATIVE,
    "cat-on-keyboard": "saturated colors, warm color cast, orange tint, " + COMMON_NEGATIVE,
    "cat-on-grass": "saturated colors, warm color cast, neon green, " + COMMON_NEGATIVE,
}
VARIANTS: dict[str, dict[str, Any]] = {
    "default": {"cfg": None, "negatives": False},
    "cfg-2.5": {"cfg": 2.5, "negatives": False},
    "cfg-1.5": {"cfg": 1.5, "negatives": False},
    "tone-negatives": {"cfg": None, "negatives": True},
}


def run(args: argparse.Namespace) -> dict[str, Any]:
    review_dir = args.review_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report = json.loads((review_dir / "report.json").read_text(encoding="utf-8"))
    source_tones = {case["case"]: case["source_tone"] for case in report["cases"]}
    workflow = json.loads(resources.files("llmpeg").joinpath(WORKFLOW_RESOURCE).read_text())
    workflow_cfg = workflow["6"]["inputs"]["cfg"]

    rows: list[dict[str, Any]] = []
    for variant in args.variants:
        settings = VARIANTS[variant]
        for case in CASES:
            prompt = (review_dir / f"{case}.prompt.txt").read_text(encoding="utf-8")
            extra = TONE_NEGATIVES[case] if settings["negatives"] else ""
            image = generate_comfyui(
                prompt,
                RESOLUTION,
                args.seed,
                args.comfyui_host,
                cfg=settings["cfg"],
                extra_negative=extra,
            )
            image_path = output_dir / f"{case}-{variant}.png"
            with image_path.open("wb" if args.overwrite else "xb") as stream:
                stream.write(image)
            with Image.open(io.BytesIO(image)) as rendered:
                tone = asdict(measure_tone(rendered))
            rows.append(
                {
                    "case": case,
                    "variant": variant,
                    "cfg": settings["cfg"] if settings["cfg"] is not None else workflow_cfg,
                    "extra_negative": extra,
                    "image": image_path.name,
                    "source_tone": source_tones[case],
                    "reconstruction_tone": tone,
                }
            )
            print(f"{case} {variant}: {source_tones[case]} -> {tone}", flush=True)

    result = {
        "llmpeg_version": __version__,
        "generator": "local ComfyUI/Qwen-Image-2.1",
        "prompts": str(review_dir.relative_to(REPO)),
        "resolution": RESOLUTION,
        "seed": args.seed,
        "rows": rows,
    }
    path = output_dir / "measurements.json"
    with path.open("w" if args.overwrite else "x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, default=REPO / "survey/qwen/review")
    parser.add_argument("--output-dir", type=Path, default=REPO / "survey/qwen/tone-sweep")
    parser.add_argument("--variants", nargs="+", default=list(VARIANTS), choices=list(VARIANTS))
    parser.add_argument(
        "--comfyui-host", default=os.environ.get("LLMPEG_COMFYUI_HOST", DEFAULT_COMFYUI_HOST)
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_QWEN_SEED)
    parser.add_argument("--overwrite", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()

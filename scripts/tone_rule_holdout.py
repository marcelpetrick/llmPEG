"""Test a tone-derived negative-prompt rule on sources it was not tuned on.

The per-case negatives in `tone_sweep.py` were chosen by looking at the three cat renders. This
script turns them into a rule that reads only the artifact's measured tone, and renders each
held-out source three ways: the current pipeline, the rule's negatives, and the rule's negatives
plus the uniform snapshot phrase from `tone_prompt_sweep.py`. Encoding uses the local Ollama
vision model; the endpoint host is never recorded.
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
from tone_cases import HOLDOUT, RESOLUTION, SNAPSHOT_PHRASE

from llmpeg import __version__
from llmpeg.artifact import Artifact, FidelityProfile, Tone
from llmpeg.encoder import (
    MONOCHROME_SATURATION,
    encode_image,
    measure_tone,
    render_generation_prompt,
)
from llmpeg.generators import DEFAULT_COMFYUI_HOST, DEFAULT_QWEN_SEED, generate_comfyui
from llmpeg.providers import DEFAULT_OLLAMA_VISION_HOST, DEFAULT_VISION_MODEL, OllamaVisionProvider

REPO = Path(__file__).resolve().parent.parent
PREAMBLE = "Create a new image from this semantic description.\n\n"
SNAPSHOT = SNAPSHOT_PHRASE + "."
DARK_LUMINANCE = 90
VIVID_SATURATION = 140
WARM = 15


def tone_negative(tone: Tone) -> str:
    """Negative terms chosen from measured tone alone, generalised from the cat sweep."""
    terms = ["professional color grading", "studio lighting"]
    if tone.saturation < VIVID_SATURATION:
        terms += ["vivid colors", "saturated colors"]
    if tone.luminance >= DARK_LUMINANCE:
        terms += ["dark", "underexposed"]
    if tone.saturation < MONOCHROME_SATURATION:
        terms += ["color", "colour", "tint", "sepia"]
    elif tone.warmth <= WARM:
        terms += ["warm color cast", "orange tint"]
    return ", ".join(terms)


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    provider = OllamaVisionProvider(args.host, args.model, args.timeout)
    rows: list[dict[str, Any]] = []
    for case in args.cases:
        artifact_path = output_dir / f"{case}.llmpeg.json.gz"
        if artifact_path.exists() and not args.overwrite:
            artifact = Artifact.from_file_bytes(artifact_path.read_bytes())
        else:
            artifact = encode_image(
                REPO / "survey/sources" / f"{case}.jpg", provider, FidelityProfile.DETAILED
            )
            artifact.write(artifact_path, overwrite=args.overwrite, compress=True)
        if artifact.tone is None:
            raise SystemExit(f"{case}: artifact has no tone")
        prompt = render_generation_prompt(artifact)
        negative = tone_negative(artifact.tone)
        variants = {
            "control": (prompt, ""),
            "rule-negatives": (prompt, negative),
            "rule-negatives-snapshot": (
                f"{PREAMBLE}{SNAPSHOT}\n{prompt.removeprefix(PREAMBLE)}",
                negative,
            ),
        }
        for variant, (text, extra) in variants.items():
            stem = f"{case}-{variant}"
            image = generate_comfyui(
                text, RESOLUTION, args.seed, args.comfyui_host, extra_negative=extra
            )
            with (output_dir / f"{stem}.png").open("wb" if args.overwrite else "xb") as stream:
                stream.write(image)
            with Image.open(io.BytesIO(image)) as rendered:
                tone = asdict(measure_tone(rendered))
            rows.append(
                {
                    "case": case,
                    "variant": variant,
                    "extra_negative": extra,
                    "image": f"{stem}.png",
                    "source_tone": asdict(artifact.tone),
                    "reconstruction_tone": tone,
                }
            )
            print(f"{stem}: {asdict(artifact.tone)} -> {tone}", flush=True)

    result = {
        "llmpeg_version": __version__,
        # Model name only: the endpoint host is never recorded.
        "encoder": f"ollama/{args.model}",
        "generator": "local ComfyUI/Qwen-Image-2.1",
        "profile": FidelityProfile.DETAILED.value,
        "resolution": RESOLUTION,
        "seed": args.seed,
        "snapshot_phrase": SNAPSHOT,
        "rows": rows,
    }
    path = output_dir / "measurements.json"
    with path.open("w" if args.overwrite else "x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO / "survey/qwen/tone-holdout")
    parser.add_argument("--cases", nargs="+", default=list(HOLDOUT), choices=HOLDOUT)
    parser.add_argument(
        "--host", default=os.environ.get("OLLAMA_VISION_HOST", DEFAULT_OLLAMA_VISION_HOST)
    )
    parser.add_argument("--model", default=os.environ.get("LLMPEG_MODEL", DEFAULT_VISION_MODEL))
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument(
        "--comfyui-host", default=os.environ.get("LLMPEG_COMFYUI_HOST", DEFAULT_COMFYUI_HOST)
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_QWEN_SEED)
    parser.add_argument("--overwrite", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()

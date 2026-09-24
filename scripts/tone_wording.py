"""Measure whether the encoder's colour words move Qwen-Image-2.1's tone.

The vision model wrote "bright green grass" for pale, yellowish grass, and content words outweigh
the prompt's `Tone:` line (`docs/tone.md`). This script re-encodes each source with the current
vision instruction, renders the plain pipeline prompt at seed 42, and records the tone next to the
earlier artifact's control render, along with how many intensifying colour words each artifact
uses. Encoding uses the local Ollama vision model; the endpoint host is never recorded.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image
from tone_cases import CATS, HOLDOUT, RESOLUTION

from llmpeg import __version__
from llmpeg.artifact import Artifact, FidelityProfile
from llmpeg.encoder import encode_image, measure_tone, render_generation_prompt
from llmpeg.generators import DEFAULT_COMFYUI_HOST, DEFAULT_QWEN_SEED, generate_comfyui
from llmpeg.providers import DEFAULT_OLLAMA_VISION_HOST, DEFAULT_VISION_MODEL, OllamaVisionProvider

REPO = Path(__file__).resolve().parent.parent
INTENSIFIERS = re.compile(r"\b(bright|brilliant|vivid|vibrant|lush|rich|saturated)\b", re.I)


def _earlier(case: str) -> tuple[Artifact, Path]:
    if case in CATS:
        folder = REPO / "survey/qwen/review"
        return (
            Artifact.from_file_bytes((folder / f"{case}.llmpeg.json.gz").read_bytes()),
            folder / f"{case}.png",
        )
    folder = REPO / "survey/qwen/tone-holdout"
    return (
        Artifact.from_file_bytes((folder / f"{case}.llmpeg.json.gz").read_bytes()),
        folder / f"{case}-control.png",
    )


def _intensifiers(artifact: Artifact) -> int:
    text = " ".join(
        [artifact.generation_prompt, *(region.description for region in artifact.composition)]
    )
    return len(INTENSIFIERS.findall(text))


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    provider = OllamaVisionProvider(args.host, args.model, args.timeout)
    rows: list[dict[str, Any]] = []
    for case in args.cases:
        earlier, earlier_image = _earlier(case)
        artifact = encode_image(
            REPO / "survey/sources" / f"{case}.jpg", provider, FidelityProfile.DETAILED
        )
        artifact.write(
            output_dir / f"{case}.llmpeg.json.gz", overwrite=args.overwrite, compress=True
        )
        image = generate_comfyui(
            render_generation_prompt(artifact), RESOLUTION, args.seed, args.comfyui_host
        )
        with (output_dir / f"{case}.png").open("wb" if args.overwrite else "xb") as stream:
            stream.write(image)
        with Image.open(io.BytesIO(image)) as rendered:
            tone = asdict(measure_tone(rendered))
        with Image.open(earlier_image) as rendered:
            earlier_tone = asdict(measure_tone(rendered))
        rows.append(
            {
                "case": case,
                "source_tone": asdict(artifact.tone) if artifact.tone else None,
                "earlier_reconstruction_tone": earlier_tone,
                "reconstruction_tone": tone,
                "earlier_intensifiers": _intensifiers(earlier),
                "intensifiers": _intensifiers(artifact),
                "image": f"{case}.png",
            }
        )
        print(f"{case}: {earlier_tone} -> {tone}", flush=True)

    result = {
        "llmpeg_version": __version__,
        # Model name only: the endpoint host is never recorded.
        "encoder": f"ollama/{args.model}",
        "generator": "local ComfyUI/Qwen-Image-2.1",
        "resolution": RESOLUTION,
        "seed": args.seed,
        "intensifiers": INTENSIFIERS.pattern,
        "rows": rows,
    }
    path = output_dir / "measurements.json"
    with path.open("w" if args.overwrite else "x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO / "survey/qwen/tone-wording")
    parser.add_argument("--cases", nargs="+", default=[*CATS, *HOLDOUT], choices=[*CATS, *HOLDOUT])
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

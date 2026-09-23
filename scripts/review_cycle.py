"""Produce the single local-Qwen review page's evidence: one reconstruction per source.

Each source is encoded by the local Ollama vision model, rendered into a text prompt, and
reconstructed by Qwen-Image-2.1 through local ComfyUI from that text only. The run records the
deterministic proxy metrics and, because human reviewers reported over-saturated reconstructions,
the measured tone of source and reconstruction side by side.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image

from llmpeg import __version__
from llmpeg.artifact import FidelityProfile
from llmpeg.encoder import encode_image, measure_tone, render_generation_prompt
from llmpeg.evaluation import evaluate_with_artifact
from llmpeg.generators import (
    DEFAULT_COMFYUI_HOST,
    DEFAULT_GENERATION_TIMEOUT,
    DEFAULT_QWEN_SEED,
    generate_comfyui,
)
from llmpeg.providers import DEFAULT_OLLAMA_VISION_HOST, DEFAULT_VISION_MODEL, OllamaVisionProvider

REPO = Path(__file__).resolve().parent.parent
# The three public-domain cat sources credited in survey/manifest.json.
DEFAULT_CASES = ("cat-monochrome", "cat-on-keyboard", "cat-on-grass")
# Matches the earlier creator/rater runs so reconstructions stay comparable with them.
REVIEW_RESOLUTION = 512


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    provider = OllamaVisionProvider(args.host, args.model, args.timeout)
    cases: list[dict[str, Any]] = []
    for name in args.cases:
        source = REPO / "survey/sources" / f"{name}.jpg"
        artifact_path = output_dir / f"{name}.llmpeg.json.gz"
        prompt_path = output_dir / f"{name}.prompt.txt"
        image_path = output_dir / f"{name}.png"
        result_path = output_dir / f"{name}-result.json"

        started = time.monotonic()
        artifact = encode_image(source, provider, FidelityProfile.DETAILED)
        encode_seconds = time.monotonic() - started
        artifact.write(artifact_path, overwrite=args.overwrite, compress=True)
        prompt = render_generation_prompt(artifact)
        _write(prompt_path, prompt.encode("utf-8"), overwrite=args.overwrite)

        started = time.monotonic()
        image = generate_comfyui(
            prompt, REVIEW_RESOLUTION, args.seed, args.comfyui_host, args.generation_timeout
        )
        generate_seconds = time.monotonic() - started
        _write(image_path, image, overwrite=args.overwrite)

        evaluation = evaluate_with_artifact(source, image_path, artifact)
        _write(result_path, evaluation.to_json().encode("utf-8"), overwrite=args.overwrite)
        with Image.open(image_path) as rendered:
            reconstruction_tone = measure_tone(rendered)
        cases.append(
            {
                "case": name,
                "artifact": artifact_path.name,
                "artifact_plain_bytes": len(artifact.to_bytes()),
                "artifact_gzip_bytes": len(artifact.to_gzip_bytes()),
                "source_bytes": artifact.source.byte_size,
                "prompt": prompt_path.name,
                "reconstruction": image_path.name,
                "result": result_path.name,
                "status": evaluation.status,
                "source_tone": asdict(artifact.tone) if artifact.tone else None,
                "reconstruction_tone": asdict(reconstruction_tone),
                "encode_seconds": round(encode_seconds, 1),
                "generate_seconds": round(generate_seconds, 1),
            }
        )
        print(
            f"{name}: {evaluation.status}, tone {cases[-1]['source_tone']} -> "
            f"{cases[-1]['reconstruction_tone']}"
        )

    report = {
        "llmpeg_version": __version__,
        # Model name only: the endpoint host is never recorded.
        "encoder": f"ollama/{args.model}",
        "generator": "local ComfyUI/Qwen-Image-2.1",
        "profile": FidelityProfile.DETAILED.value,
        "resolution": REVIEW_RESOLUTION,
        "seed": args.seed,
        "cases": cases,
    }
    _write(
        output_dir / "report.json",
        (json.dumps(report, indent=2, sort_keys=True) + "\n").encode("utf-8"),
        overwrite=args.overwrite,
    )
    return report


def _write(path: Path, content: bytes, *, overwrite: bool) -> None:
    with path.open("wb" if overwrite else "xb") as stream:
        stream.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO / "survey/qwen/review")
    parser.add_argument("--cases", nargs="+", default=list(DEFAULT_CASES), choices=DEFAULT_CASES)
    parser.add_argument(
        "--host", default=os.environ.get("OLLAMA_VISION_HOST", DEFAULT_OLLAMA_VISION_HOST)
    )
    parser.add_argument("--model", default=os.environ.get("LLMPEG_MODEL", DEFAULT_VISION_MODEL))
    parser.add_argument("--timeout", type=float, default=900.0)
    parser.add_argument(
        "--comfyui-host", default=os.environ.get("LLMPEG_COMFYUI_HOST", DEFAULT_COMFYUI_HOST)
    )
    parser.add_argument("--generation-timeout", type=float, default=DEFAULT_GENERATION_TIMEOUT)
    parser.add_argument("--seed", type=int, default=DEFAULT_QWEN_SEED)
    parser.add_argument("--overwrite", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()

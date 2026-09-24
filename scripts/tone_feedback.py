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
from llmpeg.artifact import Artifact
from llmpeg.encoder import measure_tone, render_generation_prompt
from llmpeg.evaluation import evaluate_with_artifact
from llmpeg.generators import DEFAULT_COMFYUI_HOST, generate_comfyui
from llmpeg.grading import FEEDBACK_MARGIN, FEEDBACK_TERMS, feedback_negative, match_tone

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
        "margins": FEEDBACK_MARGIN,
        "feedback_terms": FEEDBACK_TERMS,
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

"""Run an auditable local creator-versus-rater reconstruction experiment.

The creator is Qwen-Image-2.1 through ComfyUI. The rater is the configured local
vision-capable Ollama model. A challenger is accepted only when two A/B judgments,
with candidate order reversed, both prefer it and no previously passing deterministic
guard crosses into failure.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any

from llmpeg import __version__
from llmpeg.artifact import Artifact, ArtifactError, FidelityProfile
from llmpeg.encoder import encode_image, render_generation_prompt
from llmpeg.generators import (
    DEFAULT_COMFYUI_HOST,
    DEFAULT_GENERATION_TIMEOUT,
    DEFAULT_QWEN_RESOLUTION,
    DEFAULT_QWEN_SEED,
    generate_comfyui,
)
from llmpeg.providers import (
    DEFAULT_OLLAMA_VISION_HOST,
    DEFAULT_VISION_MODEL,
    OllamaVisionProvider,
)
from llmpeg.rating import AutomaticRating, OllamaSimilarityRater

REPO = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO / "survey/sources/cat-monochrome.jpg"
GUARDS = {"visual_proxy_score": 0.55, "layout_score": 0.55, "palette_distance": 0.22}


def _focus(rating: AutomaticRating) -> str:
    improvements = rating.prompt_improvements[:8]
    differences = rating.differences[:8]
    lines = [*(f"- Missing prompt detail: {item}" for item in improvements)]
    lines.extend(f"- Previous visible mismatch to re-check: {item}" for item in differences)
    return (
        "A previous text-only reconstruction was compared with the source. Reinspect the source "
        "yourself and correct these reproduction problems in the structured description. Treat "
        "the feedback as fallible hints, never as evidence for a feature you cannot see.\n"
        + "\n".join(lines)
    )


def _regressions(baseline: AutomaticRating, challenger: AutomaticRating) -> list[str]:
    regressions: list[str] = []
    for name, threshold in GUARDS.items():
        old = float(getattr(baseline.deterministic, name))
        new = float(getattr(challenger.deterministic, name))
        old_passed = old <= threshold if name.endswith("distance") else old >= threshold
        new_passed = new <= threshold if name.endswith("distance") else new >= threshold
        if old_passed and not new_passed:
            regressions.append(f"{name}: {old} -> {new} crossed threshold {threshold}")
    return regressions


def _credit_for(source: Path) -> dict[str, str]:
    resolved = source.resolve()
    for manifest_path in (
        REPO / "survey/manifest.json",
        REPO / "survey/detailed-manifest.json",
        REPO / "survey/expanded-manifest.json",
    ):
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        for case in manifest.get("cases", []):
            candidate = (manifest_path.parent / str(case.get("source", ""))).resolve()
            if candidate == resolved and isinstance(case.get("credit"), dict):
                return {str(key): str(value) for key, value in case["credit"].items()}
    raise ArtifactError(
        "source has no checked-in survey credit; record verified author, licence, and source URL "
        "before adding experiment media"
    )


def _write_round(
    output_dir: Path,
    name: str,
    artifact: Artifact,
    prompt: str,
    image: bytes,
    *,
    overwrite: bool,
) -> dict[str, Any]:
    artifact_path = output_dir / f"{name}.llmpeg.json.gz"
    prompt_path = output_dir / f"{name}.prompt.txt"
    image_path = output_dir / f"{name}.png"
    artifact.write(artifact_path, overwrite=overwrite, compress=True)
    mode = "w" if overwrite else "x"
    with prompt_path.open(mode, encoding="utf-8") as stream:
        stream.write(prompt)
    byte_mode = "wb" if overwrite else "xb"
    with image_path.open(byte_mode) as stream:
        stream.write(image)
    return {
        "artifact": artifact_path.name,
        "artifact_plain_bytes": len(artifact.to_bytes()),
        "artifact_gzip_bytes": len(artifact.to_gzip_bytes()),
        "prompt": prompt_path.name,
        "reconstruction": image_path.name,
        "reconstruction_bytes": len(image),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    source = args.source.resolve()
    source_bytes = source.read_bytes()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / "report.json"
    planned = [report_path]
    for name in ("baseline", *(f"challenger-{index}" for index in range(1, args.rounds + 1))):
        planned.extend(
            output_dir / f"{name}{suffix}" for suffix in (".llmpeg.json.gz", ".prompt.txt", ".png")
        )
    existing = next((path for path in planned if path.exists()), None)
    if existing is not None and not args.overwrite:
        raise ArtifactError(f"refusing to overwrite existing file: {existing}")

    rater = OllamaSimilarityRater(
        args.ollama_host,
        args.model,
        args.timeout,
        args.rating_repeats,
        args.seed,
    )

    def create(focus: str) -> tuple[Artifact, str, bytes, float]:
        provider = OllamaVisionProvider(
            args.ollama_host,
            args.model,
            args.timeout,
            extra_instruction=focus,
        )
        started = time.monotonic()
        artifact = encode_image(source, provider, FidelityProfile.DETAILED)
        prompt = render_generation_prompt(artifact)
        image = generate_comfyui(
            prompt,
            args.resolution,
            args.seed,
            args.comfyui_host,
            args.timeout,
        )
        return artifact, prompt, image, round(time.monotonic() - started, 3)

    print("creating baseline", flush=True)
    baseline_artifact, baseline_prompt, baseline_image, baseline_seconds = create("")
    baseline_rating = rater.rate(
        source_bytes,
        baseline_image,
        baseline_prompt,
        baseline_artifact.critical_text,
    )
    baseline_record = {
        **_write_round(
            output_dir,
            "baseline",
            baseline_artifact,
            baseline_prompt,
            baseline_image,
            overwrite=args.overwrite,
        ),
        "create_seconds": baseline_seconds,
        "rating": baseline_rating.to_dict(),
    }

    rounds: list[dict[str, Any]] = []
    for index in range(1, args.rounds + 1):
        print(f"creating challenger {index}", flush=True)
        focus = _focus(baseline_rating)
        challenger_artifact, challenger_prompt, challenger_image, create_seconds = create(focus)
        challenger_rating = rater.rate(
            source_bytes,
            challenger_image,
            challenger_prompt,
            challenger_artifact.critical_text,
        )
        pairwise = rater.compare_pairwise(
            source_bytes,
            baseline_image,
            challenger_image,
        )
        regressions = _regressions(baseline_rating, challenger_rating)
        accepted = pairwise.accepted and not regressions
        record = {
            "round": index,
            "focus_instruction": focus,
            **_write_round(
                output_dir,
                f"challenger-{index}",
                challenger_artifact,
                challenger_prompt,
                challenger_image,
                overwrite=args.overwrite,
            ),
            "create_seconds": create_seconds,
            "rating": challenger_rating.to_dict(),
            "pairwise": pairwise.to_dict(),
            "deterministic_regressions": regressions,
            "accepted": accepted,
        }
        rounds.append(record)
        if not accepted:
            break
        baseline_artifact = challenger_artifact
        baseline_prompt = challenger_prompt
        baseline_image = challenger_image
        baseline_rating = challenger_rating

    return {
        "date": time.strftime("%Y-%m-%d"),
        "llmpeg_version": __version__,
        "objective": (
            "pixels-only pairwise prompt refinement with order reversal and deterministic "
            "regression guards; not calibrated to human ratings"
        ),
        "source": str(source.relative_to(REPO)),
        "credit": _credit_for(source),
        "encoder": {"provider": "ollama", "model": args.model, "profile": "detailed"},
        "generator": {
            "provider": "comfyui",
            "model": "qwen-image-2.1",
            "resolution": args.resolution,
            "seed": args.seed,
        },
        "rating_repeats": args.rating_repeats,
        "baseline": baseline_record,
        "rounds": rounds,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-dir", type=Path, default=REPO / "survey/qwen/creator-rater")
    parser.add_argument("--rounds", type=int, default=1)
    parser.add_argument(
        "--ollama-host",
        default=os.environ.get("OLLAMA_VISION_HOST", DEFAULT_OLLAMA_VISION_HOST),
    )
    parser.add_argument(
        "--comfyui-host",
        default=os.environ.get("LLMPEG_COMFYUI_HOST", DEFAULT_COMFYUI_HOST),
    )
    parser.add_argument("--model", default=DEFAULT_VISION_MODEL)
    parser.add_argument("--resolution", type=int, default=DEFAULT_QWEN_RESOLUTION)
    parser.add_argument("--seed", type=int, default=DEFAULT_QWEN_SEED)
    parser.add_argument("--rating-repeats", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=DEFAULT_GENERATION_TIMEOUT)
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if args.rounds < 1:
        parser.error("--rounds must be at least 1")
    try:
        report = run(args)
        report_path = args.output_dir.resolve() / "report.json"
        mode = "w" if args.overwrite else "x"
        with report_path.open(mode, encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, sort_keys=True)
            stream.write("\n")
    except (ArtifactError, OSError, UnicodeError) as error:
        parser.exit(2, f"creator-rater: error: {error}\n")
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

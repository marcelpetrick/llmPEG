"""Command-line interface for llmPEG."""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from llmpeg.artifact import Artifact, ArtifactError, FidelityProfile
from llmpeg.encoder import (
    DEFAULT_MAX_IMAGE_BYTES,
    DEFAULT_MAX_IMAGE_PIXELS,
    encode_image,
    render_generation_prompt,
)
from llmpeg.evaluation import evaluate_with_artifact
from llmpeg.providers import OllamaVisionProvider
from llmpeg.survey import write_survey


def build_parser() -> argparse.ArgumentParser:
    """Build the public CLI parser."""
    parser = argparse.ArgumentParser(
        prog="llmpeg",
        description="Lossy semantic image encoding with explicit fidelity limits.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    encode = subparsers.add_parser("encode", help="encode an image with an Ollama vision model")
    encode.add_argument("image", type=Path)
    encode.add_argument("--output", "-o", required=True, type=Path)
    # choices is a sequence of members, not the enum class itself: argparse's
    # "value not in action.choices" is a plain membership test, and StrEnum
    # members compare equal to their string values.
    encode.add_argument(
        "--profile", choices=list(FidelityProfile), default=FidelityProfile.BALANCED
    )
    encode.add_argument(
        "--host",
        default=os.environ.get("OLLAMA_VISION_HOST", "http://127.0.0.1:11434"),
    )
    encode.add_argument("--model", default="qwen3-vl:32b-ctx49k")
    encode.add_argument("--timeout", type=float, default=600.0)
    encode.add_argument("--max-image-bytes", type=int, default=DEFAULT_MAX_IMAGE_BYTES)
    encode.add_argument("--max-image-pixels", type=int, default=DEFAULT_MAX_IMAGE_PIXELS)
    encode.add_argument("--overwrite", action="store_true")

    reconstruct = subparsers.add_parser(
        "reconstruct", help="render an artifact into a generator-ready prompt"
    )
    reconstruct.add_argument("artifact", type=Path)
    reconstruct.add_argument("--output", "-o", type=Path)
    reconstruct.add_argument("--overwrite", action="store_true")

    inspect = subparsers.add_parser("inspect", help="show artifact sizes and provenance")
    inspect.add_argument("artifact", type=Path)

    evaluate = subparsers.add_parser("evaluate", help="compare source and reconstruction")
    evaluate.add_argument("source", type=Path)
    evaluate.add_argument("reconstruction", type=Path)
    evaluate.add_argument("--artifact", required=True, type=Path)
    evaluate.add_argument("--ocr-text", type=Path)
    evaluate.add_argument("--output", "-o", type=Path)
    evaluate.add_argument("--overwrite", action="store_true")

    survey = subparsers.add_parser("survey", help="render an interactive HTML quality survey")
    survey.add_argument("manifest", type=Path)
    survey.add_argument("--output", "-o", required=True, type=Path)
    survey.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "encode":
            provider = OllamaVisionProvider(args.host, args.model, args.timeout)
            artifact = encode_image(
                args.image,
                provider,
                FidelityProfile(args.profile),
                max_image_bytes=args.max_image_bytes,
                max_image_pixels=args.max_image_pixels,
            )
            artifact.write(args.output, overwrite=args.overwrite)
            print(f"wrote {args.output} ({len(artifact.to_bytes())} bytes)")
        elif args.command == "reconstruct":
            artifact = Artifact.read(args.artifact)
            prompt = render_generation_prompt(artifact)
            if args.output:
                _write_text(args.output, prompt, overwrite=args.overwrite)
                print(f"wrote {args.output}")
            else:
                print(prompt, end="")
        elif args.command == "inspect":
            artifact = Artifact.read(args.artifact)
            artifact_size = len(artifact.to_bytes())
            source_size = artifact.source.byte_size
            print(f"profile: {artifact.profile.value}")
            print(f"source: {source_size} bytes ({artifact.source.width}x{artifact.source.height})")
            print(f"artifact: {artifact_size} bytes")
            print(f"size ratio: {source_size / artifact_size:.2f}:1")
            print(f"saved: {(1 - artifact_size / source_size) * 100:.2f}%")
            print(f"encoder: {artifact.provenance.provider}/{artifact.provenance.model}")
        elif args.command == "evaluate":
            artifact = Artifact.read(args.artifact)
            ocr_text = args.ocr_text.read_text(encoding="utf-8") if args.ocr_text else None
            report = evaluate_with_artifact(
                args.source, args.reconstruction, artifact, ocr_text=ocr_text
            )
            output = report.to_json()
            if args.output:
                _write_text(args.output, output, overwrite=args.overwrite)
                print(f"wrote {args.output} ({report.status})")
            else:
                print(output, end="")
            if report.status == "fail":
                return 1
            if report.status == "incomplete":
                return 3
        elif args.command == "survey":
            write_survey(args.manifest, args.output, overwrite=args.overwrite)
            print(f"wrote {args.output}")
        else:  # pragma: no cover - argparse enforces a known command
            raise AssertionError(f"unknown command: {args.command}")
    except (ArtifactError, OSError, UnicodeError) as error:
        print(f"llmpeg: error: {error}", file=sys.stderr)
        return 2
    return 0


def _write_text(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ArtifactError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8") as stream:
        stream.write(content)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

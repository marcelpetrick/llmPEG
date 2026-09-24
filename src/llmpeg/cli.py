"""Command-line interface for llmPEG."""

from __future__ import annotations

import argparse
import io
import os
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from PIL import Image
from PIL.PngImagePlugin import PngInfo

from llmpeg.artifact import Artifact, ArtifactError, FidelityProfile, Tone, envelope_of
from llmpeg.encoder import (
    DEFAULT_MAX_IMAGE_BYTES,
    DEFAULT_MAX_IMAGE_PIXELS,
    encode_image,
    measure_tone,
    render_generation_prompt,
)
from llmpeg.evaluation import evaluate_with_artifact
from llmpeg.generators import (
    DEFAULT_COMFYUI_HOST,
    DEFAULT_GENERATION_TIMEOUT,
    DEFAULT_QWEN_RESOLUTION,
    DEFAULT_QWEN_SEED,
    generate_comfyui,
)
from llmpeg.grading import feedback_negative, match_tone
from llmpeg.providers import (
    DEFAULT_OLLAMA_VISION_HOST,
    DEFAULT_VISION_MODEL,
    OllamaVisionProvider,
)
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
    encode.add_argument(
        "--output",
        "-o",
        type=Path,
        help="default: <image>.llmpeg.json.gz beside the image",
    )
    envelope = encode.add_mutually_exclusive_group()
    envelope.add_argument(
        "--gzip",
        dest="gzip",
        action="store_true",
        default=True,
        help="store in the deterministic gzip envelope (default)",
    )
    envelope.add_argument(
        "--plain",
        dest="gzip",
        action="store_false",
        help="store canonical JSON without the gzip envelope",
    )
    # choices is a sequence of members, not the enum class itself: argparse's
    # "value not in action.choices" is a plain membership test, and StrEnum
    # members compare equal to their string values.
    encode.add_argument(
        "--profile", choices=list(FidelityProfile), default=FidelityProfile.DETAILED
    )
    encode.add_argument(
        "--host",
        default=os.environ.get("OLLAMA_VISION_HOST", DEFAULT_OLLAMA_VISION_HOST),
    )
    encode.add_argument("--model", default=os.environ.get("LLMPEG_MODEL", DEFAULT_VISION_MODEL))
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

    generate = subparsers.add_parser(
        "generate", help="render an artifact locally with Qwen-Image-2.1 via ComfyUI"
    )
    generate.add_argument("artifact", type=Path)
    generate.add_argument(
        "--output", "-o", type=Path, help="default: <source-name>.reconstructed.png"
    )
    generate.add_argument(
        "--comfyui-host",
        default=os.environ.get("LLMPEG_COMFYUI_HOST", DEFAULT_COMFYUI_HOST),
    )
    generate.add_argument("--resolution", type=int, default=DEFAULT_QWEN_RESOLUTION)
    generate.add_argument("--seed", type=int, default=DEFAULT_QWEN_SEED)
    generate.add_argument("--timeout", type=float, default=DEFAULT_GENERATION_TIMEOUT)
    generate.add_argument(
        "--tone-correction",
        choices=("none", "loop", "match"),
        default="none",
        help=(
            "steer the render toward the artifact's recorded tone: 'loop' renders again with "
            "negative terms chosen from the first render's measured error; 'match' regrades the "
            "render as a post-process (never reads the source)"
        ),
    )
    generate.add_argument("--overwrite", action="store_true")

    inspect = subparsers.add_parser("inspect", help="show artifact sizes and provenance")
    inspect.add_argument("artifact", type=Path)

    verify = subparsers.add_parser("verify", help="check a file conforms to the llmPEG format")
    verify.add_argument("artifact", type=Path)

    evaluate = subparsers.add_parser("evaluate", help="compare source and reconstruction")
    evaluate.add_argument("source", type=Path)
    evaluate.add_argument("reconstruction", type=Path)
    evaluate.add_argument(
        "--artifact",
        type=Path,
        help="default: <source>.llmpeg.json beside the source, else <source>.llmpeg.json.gz",
    )
    evaluate.add_argument("--ocr-text", type=Path)
    evaluate.add_argument("--output", "-o", type=Path)
    evaluate.add_argument("--overwrite", action="store_true")

    survey = subparsers.add_parser("survey", help="render an interactive HTML quality survey")
    survey.add_argument("manifest", type=Path)
    survey.add_argument("--output", "-o", required=True, type=Path)
    survey.add_argument("--overwrite", action="store_true")
    return parser


def _regraded_png(image: Image.Image, tone: Tone) -> bytes:
    """Regrade a render and keep its PNG text chunks, adding one that records the regrade."""
    info = PngInfo()
    for key, value in image.info.items():
        if isinstance(key, str) and isinstance(value, str):
            info.add_text(key, value)
    info.add_text("llmpeg-tone-correction", "match: regraded toward the artifact's recorded tone")
    stream = io.BytesIO()
    match_tone(image, tone).save(stream, format="PNG", pnginfo=info)
    return stream.getvalue()


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI and return a process exit code."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "encode":
            output = args.output or artifact_path_for(args.image, compressed=args.gzip)
            print(
                f"encoding with ollama/{args.model} at {args.host}; "
                "the full image is uploaded to that endpoint",
                file=sys.stderr,
            )
            provider = OllamaVisionProvider(args.host, args.model, args.timeout)
            artifact = encode_image(
                args.image,
                provider,
                FidelityProfile(args.profile),
                max_image_bytes=args.max_image_bytes,
                max_image_pixels=args.max_image_pixels,
            )
            artifact.write(output, overwrite=args.overwrite, compress=args.gzip)
            plain = artifact.to_bytes()
            if args.gzip:
                stored = artifact.to_gzip_bytes()
                print(
                    f"wrote {output} (plain {len(plain):,} bytes, "
                    f"{artifact.source.byte_size / len(plain):.0f}:1; gzip {len(stored):,} bytes, "
                    f"{artifact.source.byte_size / len(stored):.0f}:1)"
                )
            else:
                print(
                    f"wrote {output} (plain {len(plain):,} bytes, "
                    f"{artifact.source.byte_size / len(plain):.0f}:1)"
                )
        elif args.command == "reconstruct":
            artifact = Artifact.read(args.artifact)
            prompt = render_generation_prompt(artifact)
            if args.output:
                _write_text(args.output, prompt, overwrite=args.overwrite)
                print(f"wrote {args.output}")
            else:
                print(prompt, end="")
        elif args.command == "generate":
            artifact = Artifact.read(args.artifact)
            output = args.output or generated_path_for(args.artifact)
            _check_overwrite(output, overwrite=args.overwrite)
            if args.tone_correction != "none" and artifact.tone is None:
                raise ArtifactError("tone correction needs a format 1.1 artifact with tone")
            prompt = render_generation_prompt(artifact)
            # One deadline covers every render, so --tone-correction loop keeps --timeout.
            deadline = time.monotonic() + args.timeout
            generated = generate_comfyui(
                prompt,
                args.resolution,
                args.seed,
                args.comfyui_host,
                args.timeout,
            )
            note = ""
            if artifact.tone is not None and args.tone_correction != "none":
                with Image.open(io.BytesIO(generated)) as first:
                    if args.tone_correction == "match":
                        generated = _regraded_png(first, artifact.tone)
                        note = "; tone matched as a post-process"
                    else:
                        first_tone = measure_tone(first)
                if args.tone_correction == "loop":
                    if extra := feedback_negative(artifact.tone, first_tone):
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise ArtifactError(
                                "--timeout ran out before the tone-correction render"
                            )
                        generated = generate_comfyui(
                            prompt,
                            args.resolution,
                            args.seed,
                            args.comfyui_host,
                            remaining,
                            extra_negative=extra,
                        )
                        note = f"; second render with negatives: {extra}"
                    else:
                        note = "; first render already within tone margins"
            _write_bytes(output, generated, overwrite=args.overwrite)
            print(f"wrote {output} (generator: local ComfyUI/Qwen-Image-2.1{note})")
        elif args.command == "inspect":
            artifact, stored = Artifact.read_stored(args.artifact)
            # Ratios are charged on the bytes actually on disk, envelope included, never on a
            # re-serialization that could differ from the file.
            artifact_size = len(stored)
            source_size = artifact.source.byte_size
            print(f"profile: {artifact.profile.value}")
            print(f"source: {source_size} bytes ({artifact.source.width}x{artifact.source.height})")
            print(f"artifact: {artifact_size} bytes")
            print(
                f"envelope: {envelope_of(stored)} (canonical JSON {len(artifact.to_bytes())} bytes)"
            )
            print(f"size ratio: {source_size / artifact_size:.2f}:1")
            print(f"saved: {(1 - artifact_size / source_size) * 100:.2f}%")
            print(f"encoder: {artifact.provenance.provider}/{artifact.provenance.model}")
        elif args.command == "verify":
            artifact, stored = Artifact.read_stored(args.artifact)
            header = artifact.header
            print(f"{header.magic} {header.format_version} ({header.major_brand})")
            print(f"compatible brands: {', '.join(header.compatible_brands)}")
            print(f"written by: {header.encoder}")
            print(f"needs reader: llmpeg >= {header.min_reader_version}")
            print(f"decoder: {header.decoder}")
            print(f"envelope: {envelope_of(stored)} ({len(stored)} bytes on disk)")
            print(f"profile: {artifact.profile.value}")
            print(f"encoder model: {artifact.provenance.provider}/{artifact.provenance.model}")
            print("conforms: yes")
        elif args.command == "evaluate":
            artifact = Artifact.read(args.artifact or existing_artifact_path_for(args.source))
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


PLAIN_SUFFIX = ".llmpeg.json"
GZIP_SUFFIX = ".llmpeg.json.gz"


def artifact_path_for(image: Path, *, compressed: bool = False) -> Path:
    """Return the artifact path beside an image: photo.jpg -> photo.jpg.llmpeg.json.

    The whole original name is kept and `.llmpeg.json` is appended rather than replacing the
    extension, so `photo.jpg` and `photo.png` in one folder cannot collide on a single artifact.
    It also keeps the source obvious from the artifact's name alone. A gzip envelope adds `.gz`,
    the name `gzip photo.jpg.llmpeg.json` would produce.
    """
    return image.parent / f"{image.name}{GZIP_SUFFIX if compressed else PLAIN_SUFFIX}"


def existing_artifact_path_for(image: Path) -> Path:
    """Return the plain artifact beside an image, or its gzip form when only that exists."""
    plain = artifact_path_for(image)
    compressed = artifact_path_for(image, compressed=True)
    return compressed if not plain.exists() and compressed.exists() else plain


def generated_path_for(artifact: Path) -> Path:
    """Return the default generated-image path beside an artifact."""
    source_name = next(
        (
            artifact.name[: -len(suffix)]
            for suffix in (GZIP_SUFFIX, PLAIN_SUFFIX)
            if artifact.name.endswith(suffix)
        ),
        artifact.stem,
    )
    return artifact.parent / f"{source_name}.reconstructed.png"


def _check_overwrite(path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ArtifactError(f"refusing to overwrite existing file: {path}")


def _write_bytes(path: Path, content: bytes, *, overwrite: bool) -> None:
    _check_overwrite(path, overwrite=overwrite)
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if overwrite else "xb"
    with path.open(mode) as stream:
        stream.write(content)


def _write_text(path: Path, content: str, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ArtifactError(f"refusing to overwrite existing file: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "w" if overwrite else "x"
    with path.open(mode, encoding="utf-8") as stream:
        stream.write(content)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

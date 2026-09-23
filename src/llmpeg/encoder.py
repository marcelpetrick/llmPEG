"""Image-to-artifact encoding and generator prompt rendering."""

from __future__ import annotations

import io
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from PIL import Image, ImageStat, UnidentifiedImageError

from llmpeg.artifact import (
    HEADER_KEY,
    Artifact,
    ArtifactError,
    FidelityProfile,
    FormatHeader,
    SourceInfo,
    Tone,
    source_digest,
)
from llmpeg.providers import VisionProvider

MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
DEFAULT_MAX_IMAGE_BYTES = 25 * 1024 * 1024
DEFAULT_MAX_IMAGE_PIXELS = 50_000_000
# Tone statistics are global means, so a 256-pixel thumbnail measures them to within rounding.
TONE_SAMPLE_PIXELS = 256
# Below this mean HSV saturation a source is rendered as black-and-white. Grayscale JPEGs
# measure 0; faint chroma noise from colour-space conversion stays well under it.
MONOCHROME_SATURATION = 6


def encode_image(
    path: Path,
    provider: VisionProvider,
    profile: FidelityProfile = FidelityProfile.BALANCED,
    *,
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
    max_image_pixels: int = DEFAULT_MAX_IMAGE_PIXELS,
) -> Artifact:
    """Encode an image with a vision provider without mutating the input."""
    try:
        content = path.read_bytes()
    except OSError as error:
        raise ArtifactError(f"cannot read image {path}: {error}") from error
    if len(content) > max_image_bytes:
        raise ArtifactError(
            f"image is {len(content)} bytes; configured limit is {max_image_bytes} bytes"
        )
    if not content:
        raise ArtifactError("image is empty")
    try:
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
            if width * height > max_image_pixels:
                raise ArtifactError(
                    f"image has {width * height} pixels; configured limit is "
                    f"{max_image_pixels} pixels"
                )
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
            media_type = MEDIA_TYPES.get(image.format or "")
            tone = measure_tone(image)
    except (Image.DecompressionBombError, UnidentifiedImageError, OSError) as error:
        raise ArtifactError(f"unsupported or corrupt image: {error}") from error
    if media_type is None:
        raise ArtifactError("supported image formats are JPEG, PNG, and WebP")

    description = provider.describe(content, media_type, profile)
    artifact = _artifact_from_description(
        description,
        profile=profile,
        source=SourceInfo(width, height, len(content), media_type, source_digest(content)),
        provider=provider,
        tone=tone,
    )
    artifact.enforce_budget()
    return artifact


def _artifact_from_description(
    data: dict[str, Any],
    *,
    profile: FidelityProfile,
    source: SourceInfo,
    provider: VisionProvider,
    tone: Tone | None = None,
) -> Artifact:
    expected = {
        "summary",
        "generation_prompt",
        "critical_text",
        "composition",
        "palette",
        "style",
        "avoid",
    }
    missing, extra = expected - set(data), set(data) - expected
    if missing or extra:
        raise ArtifactError(
            f"vision response keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )
    return Artifact.from_dict(
        {
            HEADER_KEY: FormatHeader().to_dict(),
            "profile": profile.value,
            "source": asdict(source),
            **data,
            "provenance": asdict(provider.provenance),
            **({} if tone is None else {"tone": asdict(tone)}),
        }
    )


def measure_tone(image: Image.Image) -> Tone:
    """Measure global exposure and colour from pixels instead of asking the vision model.

    A small vision model describes grading poorly, and a generator left to its defaults renders
    brighter, punchier colour; measured numbers give the prompt something concrete to hold to.
    """
    sample = image.convert("RGB")
    sample.thumbnail((TONE_SAMPLE_PIXELS, TONE_SAMPLE_PIXELS))
    luminance = ImageStat.Stat(sample.convert("L"))
    saturation = ImageStat.Stat(sample.convert("HSV").getchannel("S"))
    red, _, blue = ImageStat.Stat(sample).mean
    return Tone(
        luminance=round(luminance.mean[0]),
        contrast=round(luminance.stddev[0]),
        saturation=round(saturation.mean[0]),
        warmth=round(red - blue),
    )


def describe_tone(tone: Tone) -> str:
    """Turn measured tone into words a text-to-image model follows, keeping the numbers."""
    exposure = _band(
        tone.luminance,
        (
            (70, "dark, low-key"),
            (110, "moderately dark"),
            (150, "mid-tone"),
            (190, "bright"),
            (256, "very bright, high-key"),
        ),
    )
    contrast = _band(tone.contrast, ((40, "low, soft"), (65, "moderate"), (256, "high")))
    if tone.saturation < MONOCHROME_SATURATION:
        colour = "strictly black-and-white grayscale with no colour or tint at all"
    else:
        colour = _band(
            tone.saturation,
            (
                (40, "muted, desaturated colour"),
                (90, "natural, moderate colour"),
                (140, "rich colour"),
                (256, "vivid colour"),
            ),
        )
        cast = "warm" if tone.warmth > 15 else "cool" if tone.warmth < -15 else "neutral"
        colour += f" with a {cast} white balance"
    return (
        f"{exposure} exposure (mean luminance {tone.luminance}/255), {contrast} contrast "
        f"(spread {tone.contrast}/255), {colour} (mean saturation {tone.saturation}/255). "
        "Match this grading exactly: do not brighten, add contrast, boost saturation, or apply "
        "HDR, glow, or cinematic colour grading."
    )


def _band(value: int, bands: tuple[tuple[int, str], ...]) -> str:
    return next(label for limit, label in bands if value < limit)


def render_generation_prompt(artifact: Artifact) -> str:
    """Turn the portable artifact into a model-neutral generation prompt."""
    regions = "\n".join(
        f"- {region.region}: {region.description}" for region in artifact.composition
    )
    text = (
        "\n".join(f"- {json.dumps(item, ensure_ascii=False)}" for item in artifact.critical_text)
        or "- none"
    )
    avoid = ", ".join(artifact.avoid) or "none"
    palette = ", ".join(artifact.palette) or "unspecified"
    canvas = (
        f"{artifact.source.width}x{artifact.source.height} "
        f"({artifact.source.width / artifact.source.height:.3f}:1)"
    )
    # Artifacts before format 1.1 carry no tone, and their prompts stay exactly as they were.
    tone = "" if artifact.tone is None else f"Tone: {describe_tone(artifact.tone)}\n"
    fidelity = {
        FidelityProfile.GIST: "Preserve the recognizable scene and broad arrangement.",
        FidelityProfile.BALANCED: (
            "Preserve the subject, action, palette, lighting, and spatial relationships."
        ),
        FidelityProfile.DETAILED: (
            "Maximize resemblance to this specifically described subject. Prioritize distinctive "
            "markings, proportions, pose landmarks, crop, and object geometry over generic beauty "
            "or creative interpretation."
        ),
    }[artifact.profile]
    return f"""Create a new image from this semantic description.

Primary request: {artifact.generation_prompt}
Fidelity goal: {fidelity}
Style/medium: {artifact.style}
Canvas: {canvas}
Composition:
{regions or "- unspecified"}
Palette: {palette}
{tone}Text to render verbatim when possible:
{text}
Constraints: preserve every described landmark, hierarchy, and spatial relationship; add no
unlisted subject, object, marking, or decoration.
This is a semantic reconstruction, not the original.
Avoid: {avoid}; extra logos; watermarks; invented claims.
"""

"""Image-to-artifact encoding and generator prompt rendering."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from promptpress.artifact import (
    SCHEMA_VERSION,
    Artifact,
    ArtifactError,
    FidelityProfile,
    Region,
    SourceInfo,
    source_digest,
)
from promptpress.providers import VisionProvider

MEDIA_TYPES = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}
DEFAULT_MAX_IMAGE_BYTES = 25 * 1024 * 1024


def encode_image(
    path: Path,
    provider: VisionProvider,
    profile: FidelityProfile = FidelityProfile.BALANCED,
    *,
    max_image_bytes: int = DEFAULT_MAX_IMAGE_BYTES,
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
            image.verify()
        with Image.open(io.BytesIO(content)) as image:
            width, height = image.size
            media_type = MEDIA_TYPES.get(image.format or "")
    except (UnidentifiedImageError, OSError) as error:
        raise ArtifactError(f"unsupported or corrupt image: {error}") from error
    if media_type is None:
        raise ArtifactError("supported image formats are JPEG, PNG, and WebP")

    description = provider.describe(content, media_type, profile)
    artifact = _artifact_from_description(
        description,
        profile=profile,
        source=SourceInfo(width, height, len(content), media_type, source_digest(content)),
        provider=provider,
    )
    artifact.enforce_budget()
    return artifact


def _artifact_from_description(
    data: dict[str, Any],
    *,
    profile: FidelityProfile,
    source: SourceInfo,
    provider: VisionProvider,
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
    try:
        artifact = Artifact(
            schema_version=SCHEMA_VERSION,
            profile=profile,
            source=source,
            summary=str(data["summary"]),
            generation_prompt=str(data["generation_prompt"]),
            critical_text=tuple(str(item) for item in data["critical_text"]),
            composition=tuple(Region(**item) for item in data["composition"]),
            palette=tuple(str(item) for item in data["palette"]),
            style=str(data["style"]),
            avoid=tuple(str(item) for item in data["avoid"]),
            provenance=provider.provenance,
        )
    except (TypeError, ValueError) as error:
        raise ArtifactError(f"invalid vision response structure: {error}") from error
    artifact.validate()
    return artifact


def render_generation_prompt(artifact: Artifact) -> str:
    """Turn the portable artifact into a model-neutral generation prompt."""
    regions = "\n".join(
        f"- {region.region}: {region.description}" for region in artifact.composition
    )
    text = "\n".join(f'- "{item}"' for item in artifact.critical_text) or "- none"
    avoid = ", ".join(artifact.avoid) or "none"
    palette = ", ".join(artifact.palette) or "unspecified"
    canvas = (
        f"{artifact.source.width}x{artifact.source.height} "
        f"({artifact.source.width / artifact.source.height:.3f}:1)"
    )
    return f"""Create a new image from this semantic description.

Primary request: {artifact.generation_prompt}
Style/medium: {artifact.style}
Canvas: {canvas}
Composition:
{regions or "- unspecified"}
Palette: {palette}
Text to render verbatim when possible:
{text}
Constraints: preserve the described hierarchy and spatial relationships.
This is a semantic reconstruction, not the original.
Avoid: {avoid}; extra logos; watermarks; invented claims.
"""

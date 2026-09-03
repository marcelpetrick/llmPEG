"""Deterministic visual proxy metrics for reconstruction comparisons."""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Literal

from PIL import Image, ImageFilter

from promptpress.artifact import Artifact, ArtifactError, FidelityProfile


@dataclass(frozen=True)
class Metrics:
    """Bounded similarity and distance metrics."""

    aspect_similarity: float
    dhash_similarity: float
    histogram_similarity: float
    edge_similarity: float
    palette_distance: float
    layout_score: float
    visual_proxy_score: float
    critical_text_recall: float | None


@dataclass(frozen=True)
class Evaluation:
    """Metric values plus a transparent profile decision."""

    profile: FidelityProfile
    status: Literal["pass", "fail", "incomplete"]
    metrics: Metrics
    checks: dict[str, bool | None]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-ready report."""
        result = asdict(self)
        result["profile"] = self.profile.value
        return result

    def to_json(self) -> str:
        """Return stable pretty JSON with a trailing newline."""
        return json.dumps(self.to_dict(), indent=2, sort_keys=True) + "\n"


THRESHOLDS: dict[FidelityProfile, dict[str, float]] = {
    FidelityProfile.GIST: {"visual_proxy_score": 0.45, "palette_distance": 0.30},
    FidelityProfile.BALANCED: {
        "visual_proxy_score": 0.55,
        "layout_score": 0.55,
        "palette_distance": 0.22,
    },
    FidelityProfile.DETAILED: {
        "visual_proxy_score": 0.62,
        "layout_score": 0.65,
        "palette_distance": 0.18,
        "critical_text_recall": 0.90,
    },
}


def evaluate_images(
    source_path: Path,
    reconstruction_path: Path,
    profile: FidelityProfile,
    *,
    critical_text: tuple[str, ...] = (),
    ocr_text: str | None = None,
) -> Evaluation:
    """Compare two images with reproducible, non-semantic proxy metrics."""
    try:
        with Image.open(source_path) as opened:
            source = opened.convert("RGB")
        with Image.open(reconstruction_path) as opened:
            reconstruction = opened.convert("RGB")
    except OSError as error:
        raise ArtifactError(f"cannot evaluate image: {error}") from error

    aspect = _aspect_similarity(source, reconstruction)
    dhash = _dhash_similarity(source, reconstruction)
    histogram = _histogram_similarity(source, reconstruction)
    edge = _edge_similarity(source, reconstruction)
    palette = _palette_distance(source, reconstruction)
    layout = _bounded(0.55 * dhash + 0.30 * edge + 0.15 * aspect)
    visual = _bounded(0.35 * dhash + 0.30 * histogram + 0.20 * edge + 0.15 * aspect)
    recall = _critical_text_recall(critical_text, ocr_text)
    metrics = Metrics(aspect, dhash, histogram, edge, palette, layout, visual, recall)
    checks: dict[str, bool | None] = {}
    for name, threshold in THRESHOLDS[profile].items():
        value = getattr(metrics, name)
        checks[name] = (
            None
            if value is None
            else (value <= threshold if name.endswith("distance") else value >= threshold)
        )
    status: Literal["pass", "fail", "incomplete"]
    if any(value is False for value in checks.values()):
        status = "fail"
    elif any(value is None for value in checks.values()):
        status = "incomplete"
    else:
        status = "pass"
    return Evaluation(profile, status, metrics, checks)


def evaluate_with_artifact(
    source_path: Path,
    reconstruction_path: Path,
    artifact: Artifact,
    *,
    ocr_text: str | None = None,
) -> Evaluation:
    """Evaluate using profile and critical text stored in an artifact."""
    return evaluate_images(
        source_path,
        reconstruction_path,
        artifact.profile,
        critical_text=artifact.critical_text,
        ocr_text=ocr_text,
    )


def _aspect_similarity(left: Image.Image, right: Image.Image) -> float:
    left_ratio = left.width / left.height
    right_ratio = right.width / right.height
    return _bounded(min(left_ratio, right_ratio) / max(left_ratio, right_ratio))


def _dhash(image: Image.Image) -> tuple[bool, ...]:
    gray = image.convert("L").resize((9, 8), Image.Resampling.LANCZOS)
    values = list(gray.getdata())
    return tuple(
        values[row * 9 + column] > values[row * 9 + column + 1]
        for row in range(8)
        for column in range(8)
    )


def _dhash_similarity(left: Image.Image, right: Image.Image) -> float:
    difference = sum(a != b for a, b in zip(_dhash(left), _dhash(right), strict=True))
    return 1.0 - difference / 64.0


def _histogram_similarity(left: Image.Image, right: Image.Image) -> float:
    size = (128, 128)
    left_histogram = left.resize(size).histogram()
    right_histogram = right.resize(size).histogram()
    intersection = sum(min(a, b) for a, b in zip(left_histogram, right_histogram, strict=True))
    return _bounded(intersection / (size[0] * size[1] * 3))


def _edge_density(image: Image.Image) -> float:
    edge = image.convert("L").resize((128, 128)).filter(ImageFilter.FIND_EDGES)
    count = sum(1 for value in edge.getdata() if isinstance(value, int) and value >= 32)
    return count / (128 * 128)


def _edge_similarity(left: Image.Image, right: Image.Image) -> float:
    difference = abs(_edge_density(left) - _edge_density(right))
    return _bounded(1.0 - difference)


def _dominant_colors(image: Image.Image, count: int = 5) -> list[tuple[int, int, int]]:
    quantized = image.resize((128, 128)).quantize(colors=count)
    palette = quantized.getpalette()
    colors = quantized.getcolors() or []
    if palette is None:
        return []
    return [tuple(palette[index * 3 : index * 3 + 3]) for _, index in sorted(colors, reverse=True)]  # type: ignore[misc]


def _palette_distance(left: Image.Image, right: Image.Image) -> float:
    left_colors = _dominant_colors(left)
    right_colors = _dominant_colors(right)
    if not left_colors or not right_colors:
        return 1.0
    maximum = math.sqrt(3 * 255**2)
    distances = []
    for color in left_colors:
        nearest = min(math.dist(color, candidate) for candidate in right_colors)
        distances.append(nearest / maximum)
    return _bounded(sum(distances) / len(distances))


def _critical_text_recall(expected: tuple[str, ...], actual: str | None) -> float | None:
    if actual is None or not expected:
        return None
    folded = actual.casefold()
    return sum(item.casefold() in folded for item in expected) / len(expected)


def _bounded(value: float) -> float:
    return round(max(0.0, min(1.0, value)), 6)

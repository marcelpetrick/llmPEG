from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from llmpeg.artifact import Artifact, ArtifactError, FidelityProfile, Provenance, Tone
from llmpeg.encoder import (
    colourfulness,
    describe_tone,
    encode_image,
    measure_tone,
    render_generation_prompt,
)


class FakeProvider:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = result
        self.seen: tuple[int, str, FidelityProfile] | None = None

    @property
    def provenance(self) -> Provenance:
        return Provenance("fake", "fixture-v1", 42, 0.0)

    def describe(self, image: bytes, media_type: str, profile: FidelityProfile) -> dict[str, Any]:
        self.seen = (len(image), media_type, profile)
        return self.result


def test_encode_and_render(sample_image: Path, description: dict[str, Any]) -> None:
    provider = FakeProvider(description)
    artifact = encode_image(sample_image, provider, FidelityProfile.DETAILED)
    assert artifact.source.width == 160
    assert artifact.source.height == 120
    assert provider.seen == (sample_image.stat().st_size, "image/png", FidelityProfile.DETAILED)
    prompt = render_generation_prompt(artifact)
    assert "160x120" in prompt
    assert '"EXAMPLE"' in prompt
    assert "left: white rectangle" in prompt
    assert "Maximize resemblance" in prompt
    assert "add no" in prompt
    assert artifact.tone == measure_tone(Image.open(sample_image))
    assert "Tone: " in prompt
    assert "do not brighten" in prompt


def test_tone_is_measured_from_pixels() -> None:
    gray = measure_tone(Image.new("L", (64, 64), 128))
    assert gray == Tone(luminance=128, contrast=0, saturation=0, warmth=0, colourfulness=0)
    orange = measure_tone(Image.new("RGB", (64, 64), (255, 128, 0)))
    assert orange.saturation == 255
    assert orange.warmth == 255
    # A flat colour has no spread, so only the mean term counts: 0.3 * hypot(127, 191.5).
    assert orange.colourfulness == round(0.3 * math.hypot(127, 191.5))


def test_colourfulness_ignores_dark_tints_that_hsv_saturation_inflates() -> None:
    dark = Image.new("RGB", (64, 64), (12, 6, 4))
    mid = Image.new("RGB", (64, 64), (120, 110, 100))
    assert measure_tone(dark).saturation > measure_tone(mid).saturation
    assert colourfulness(dark) < colourfulness(mid)


def test_tone_is_described_in_words_and_numbers() -> None:
    monochrome = describe_tone(Tone(luminance=125, contrast=61, saturation=0, warmth=0))
    assert monochrome.startswith("mid-tone exposure (mean luminance 125/255), moderate contrast")
    assert "strictly black-and-white" in monochrome
    assert "white balance" not in monochrome
    warm = describe_tone(Tone(luminance=148, contrast=55, saturation=48, warmth=30))
    assert "natural, moderate colour with a warm white balance" in warm
    assert "cool" in describe_tone(Tone(40, 80, 200, -40))
    assert "dark, low-key" in describe_tone(Tone(40, 80, 200, -40))
    assert "very bright, high-key" in describe_tone(Tone(230, 20, 10, 0))
    assert "low, soft contrast" in describe_tone(Tone(230, 20, 10, 0))
    assert "neutral white balance" in describe_tone(Tone(230, 20, 10, 0))


def test_artifact_without_tone_renders_the_pre_1_1_prompt(artifact: Artifact) -> None:
    assert artifact.tone is None
    prompt = render_generation_prompt(artifact)
    assert "Tone:" not in prompt
    toned = replace(artifact, tone=Tone(100, 50, 20, 0))
    assert "Tone: moderately dark exposure" in render_generation_prompt(toned)


def test_encode_rejects_input_errors(
    tmp_path: Path, sample_image: Path, description: dict[str, Any]
) -> None:
    provider = FakeProvider(description)
    with pytest.raises(ArtifactError, match="cannot read"):
        encode_image(tmp_path / "missing.png", provider)
    empty = tmp_path / "empty.png"
    empty.touch()
    with pytest.raises(ArtifactError, match="empty"):
        encode_image(empty, provider)
    bad = tmp_path / "bad.png"
    bad.write_text("not an image")
    with pytest.raises(ArtifactError, match="corrupt"):
        encode_image(bad, provider)
    with pytest.raises(ArtifactError, match="configured limit"):
        encode_image(sample_image, provider, max_image_bytes=1)
    with pytest.raises(ArtifactError, match="pixel"):
        encode_image(sample_image, provider, max_image_pixels=1)


def test_encode_rejects_provider_shape(sample_image: Path, description: dict[str, Any]) -> None:
    malformed = dict(description)
    malformed.pop("summary")
    with pytest.raises(ArtifactError, match="keys mismatch"):
        encode_image(sample_image, FakeProvider(malformed), FidelityProfile.DETAILED)
    malformed = dict(description, composition=[{"wrong": "shape"}])
    with pytest.raises(ArtifactError, match="keys mismatch"):
        encode_image(sample_image, FakeProvider(malformed), FidelityProfile.DETAILED)
    malformed = dict(description, critical_text="not an array")
    with pytest.raises(ArtifactError, match="must be an array"):
        encode_image(sample_image, FakeProvider(malformed), FidelityProfile.DETAILED)

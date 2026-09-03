from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from promptpress.artifact import ArtifactError, FidelityProfile, Provenance
from promptpress.encoder import encode_image, render_generation_prompt


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

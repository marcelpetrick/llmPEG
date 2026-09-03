from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PIL import Image, ImageDraw

from llmpeg.artifact import (
    SCHEMA_VERSION,
    Artifact,
    FidelityProfile,
    Provenance,
    Region,
    SourceInfo,
)


@pytest.fixture
def sample_image(tmp_path: Path) -> Path:
    path = tmp_path / "sample.png"
    image = Image.new("RGB", (160, 120), "navy")
    draw = ImageDraw.Draw(image)
    draw.rectangle((10, 10, 75, 100), fill="white")
    draw.rectangle((90, 20, 150, 90), fill="red")
    image.save(path)
    return path


@pytest.fixture
def description() -> dict[str, Any]:
    return {
        "summary": "Two rectangles on a navy field.",
        "generation_prompt": "A white and red geometric poster on navy.",
        "critical_text": ["EXAMPLE"],
        "composition": [
            {"region": "left", "description": "white rectangle"},
            {"region": "right", "description": "red rectangle"},
        ],
        "palette": ["#000080", "#FFFFFF", "#FF0000"],
        "style": "flat geometric poster",
        "avoid": ["gradients"],
    }


@pytest.fixture
def artifact() -> Artifact:
    return Artifact(
        SCHEMA_VERSION,
        FidelityProfile.DETAILED,
        SourceInfo(160, 120, 100_000, "image/png", "a" * 64),
        "Two rectangles on a navy field.",
        "A white and red geometric poster on navy.",
        ("EXAMPLE",),
        (Region("left", "white rectangle"), Region("right", "red rectangle")),
        ("#000080", "#FFFFFF", "#FF0000"),
        "flat geometric poster",
        ("gradients",),
        Provenance("fake", "fixture-v1", 42, 0.0),
    )

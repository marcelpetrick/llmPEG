from __future__ import annotations

import json
from pathlib import Path

import pytest

from promptpress.artifact import Artifact, ArtifactError, FidelityProfile, source_digest


def test_profile_budgets_and_invalid_source() -> None:
    assert FidelityProfile.GIST.budget(10_000) == 1024
    assert FidelityProfile.BALANCED.budget(100_000) == 5000
    assert FidelityProfile.DETAILED.budget(200_000) == 30_000
    with pytest.raises(ArtifactError, match="positive"):
        FidelityProfile.GIST.budget(0)


def test_artifact_round_trip_is_canonical(artifact: Artifact, tmp_path: Path) -> None:
    encoded = artifact.to_bytes()
    assert b"\n" not in encoded
    assert encoded == Artifact.from_dict(json.loads(encoded)).to_bytes()
    path = tmp_path / "result.ppress.json"
    artifact.write(path)
    assert Artifact.read(path) == artifact
    with pytest.raises(ArtifactError, match="overwrite"):
        artifact.write(path)
    artifact.write(path, overwrite=True)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"schema_version": 99}, "unsupported schema"),
        ({"source": {"width": 0}}, "must be positive"),
        ({"source": {"sha256": "bad"}}, "sha256"),
        ({"source": {"media_type": "image/gif"}}, "unsupported source"),
        ({"generation_prompt": ""}, "must not be empty"),
        ({"palette": ["blue"]}, "#RRGGBB"),
        ({"critical_text": [""]}, "must not be empty"),
        ({"composition": [{"region": "", "description": "x"}]}, "must not be empty"),
    ],
)
def test_artifact_validation(artifact: Artifact, mutation: dict[str, object], message: str) -> None:
    data = artifact.to_dict()
    for key, value in mutation.items():
        if key == "source" and isinstance(value, dict):
            data["source"].update(value)
        else:
            data[key] = value
    with pytest.raises(ArtifactError, match=message):
        Artifact.from_dict(data)


def test_artifact_rejects_key_mismatch_and_bad_files(artifact: Artifact, tmp_path: Path) -> None:
    data = artifact.to_dict()
    data["surprise"] = True
    with pytest.raises(ArtifactError, match="keys mismatch"):
        Artifact.from_dict(data)
    path = tmp_path / "bad.json"
    path.write_text("[]")
    with pytest.raises(ArtifactError, match="root"):
        Artifact.read(path)
    path.write_text("{")
    with pytest.raises(ArtifactError, match="cannot read"):
        Artifact.read(path)


def test_budget_enforcement_and_digest(artifact: Artifact) -> None:
    data = artifact.to_dict()
    data["profile"] = "gist"
    data["source"]["byte_size"] = 1
    data["generation_prompt"] = "x" * 2000
    oversized = Artifact.from_dict(data)
    with pytest.raises(ArtifactError, match="budget"):
        oversized.enforce_budget()
    assert source_digest(b"hello") == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )

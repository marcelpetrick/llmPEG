from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmpeg.artifact import (
    FORMAT_MAJOR,
    FORMAT_MINOR,
    FORMAT_VERSION,
    Artifact,
    ArtifactError,
    FidelityProfile,
    UnsupportedFormatError,
    source_digest,
)


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
    path = tmp_path / "result.llmpeg.json"
    artifact.write(path)
    assert Artifact.read(path) == artifact
    with pytest.raises(ArtifactError, match="overwrite"):
        artifact.write(path)
    artifact.write(path, overwrite=True)


def test_artifact_normalizes_surrounding_model_whitespace(artifact: Artifact) -> None:
    data = artifact.to_dict()
    data["generation_prompt"] = "  specific cat  "
    data["composition"][0]["description"] = "  white rectangle  "

    normalized = Artifact.from_dict(data)

    assert normalized.generation_prompt == "specific cat"
    assert normalized.composition[0].description == "white rectangle"


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"llmpeg": {"format_version": "9.0"}}, "this build reads"),
        ({"llmpeg": {"magic": "NOTLLMPEG"}}, "not an llmPEG artifact"),
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
        if key in {"source", "llmpeg"} and isinstance(value, dict):
            data[key].update(value)
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


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("llmpeg", "not an object", "must be an object"),
        ("critical_text", "not an array", "array"),
        ("summary", 123, "string"),
        ("provenance", {"provider": "x"}, "keys mismatch"),
    ],
)
def test_artifact_rejects_wrong_json_types(
    artifact: Artifact, field: str, value: object, message: str
) -> None:
    data = artifact.to_dict()
    data[field] = value
    with pytest.raises(ArtifactError, match=message):
        Artifact.from_dict(data)


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


def test_header_is_first_in_the_serialized_bytes(artifact: Artifact) -> None:
    """The magic must sit at the start of the file, like a binary signature."""
    encoded = artifact.to_bytes()
    assert encoded.startswith(b'{"llmpeg":{')
    assert b'"magic":"llmPEG"' in encoded[:120]


def test_legacy_artifact_without_header_is_readable_and_upgraded(artifact: Artifact) -> None:
    """Files written before the header existed still load, and gain one on write."""
    legacy = artifact.to_dict()
    del legacy["llmpeg"]
    legacy["schema_version"] = 1

    parsed = Artifact.from_dict(legacy)

    assert parsed.header.format_version == FORMAT_VERSION
    assert parsed.header.encoder.endswith("/unknown")
    assert json.loads(parsed.to_bytes())["llmpeg"]["format_version"] == FORMAT_VERSION


def test_unknown_header_fields_are_rejected_now_but_allowed_from_a_newer_minor(
    artifact: Artifact,
) -> None:
    """Additive minor versions stay readable; unknown fields at our own version do not."""
    data = artifact.to_dict()
    data["llmpeg"]["experimental"] = "x"
    with pytest.raises(ArtifactError, match="keys mismatch"):
        Artifact.from_dict(data)

    data["llmpeg"]["format_version"] = f"{FORMAT_MAJOR}.{FORMAT_MINOR + 1}"
    assert Artifact.from_dict(data).header.format_version.startswith(f"{FORMAT_MAJOR}.")


def test_a_future_major_version_is_refused_with_an_actionable_message(
    artifact: Artifact,
) -> None:
    data = artifact.to_dict()
    data["llmpeg"]["format_version"] = f"{FORMAT_MAJOR + 1}.0"
    with pytest.raises(UnsupportedFormatError, match="this build reads"):
        Artifact.from_dict(data)


def test_plain_json_is_not_mistaken_for_an_artifact() -> None:
    with pytest.raises(ArtifactError, match="not an llmPEG artifact"):
        Artifact.from_dict({"hello": "world"})


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        ({"format_version": "one.zero"}, "MAJOR.MINOR"),
        ({"major_brand": " "}, "major_brand must not be empty"),
        ({"compatible_brands": ["other"]}, "must include the major_brand"),
        ({"encoder": "  "}, "header encoder must not be empty"),
    ],
)
def test_header_rejects_malformed_fields(
    artifact: Artifact, mutation: dict[str, object], message: str
) -> None:
    data = artifact.to_dict()
    data["llmpeg"].update(mutation)
    with pytest.raises(ArtifactError, match=message):
        Artifact.from_dict(data)


def test_header_rejects_missing_fields(artifact: Artifact) -> None:
    data = artifact.to_dict()
    del data["llmpeg"]["min_reader_version"]
    with pytest.raises(ArtifactError, match="header keys missing"):
        Artifact.from_dict(data)

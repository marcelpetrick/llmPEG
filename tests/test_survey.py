from __future__ import annotations

import json
from pathlib import Path

import pytest

from llmpeg.artifact import Artifact, ArtifactError
from llmpeg.cli import main
from llmpeg.survey import render_survey, write_survey


def _manifest(tmp_path: Path, artifact: Artifact) -> Path:
    artifact_path = tmp_path / "artifact.json"
    artifact.write(artifact_path)
    (tmp_path / "prompt.txt").write_text("A <cat> & a keyboard", encoding="utf-8")
    (tmp_path / "result.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "metrics": {
                    "visual_proxy_score": 0.7,
                    "layout_score": 0.8,
                    "dhash_similarity": 0.6,
                    "palette_distance": 0.1,
                },
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "title": "Cats & compression",
                "date": "2026-09-03",
                "profile": "balanced",
                "cases": [
                    {
                        "id": "cat-one",
                        "name": "Cat <one>",
                        "source": "source.jpg",
                        "reconstruction": "result.png",
                        "artifact": "artifact.json",
                        "prompt": "prompt.txt",
                        "result": "result.json",
                        "credit": {
                            "author": "Example & Author",
                            "license": "Public domain",
                            "license_url": "https://example.test/license",
                            "source_url": "https://example.test/source",
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    return manifest


def test_render_survey_is_interactive_and_escaped(tmp_path: Path, artifact: Artifact) -> None:
    output = render_survey(_manifest(tmp_path, artifact))
    assert "1/1" in output
    assert "0.700" in output
    assert "Cat &lt;one&gt;" in output
    assert "A &lt;cat&gt; &amp; a keyboard" in output
    assert "Export my ratings" in output
    assert "localStorage" in output
    assert "1/1 cases meet" in output
    assert "<code>balanced</code> profile" in output


def test_render_survey_compares_baseline(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    case = data["cases"][0]
    case["baseline_reconstruction"] = "baseline.png"
    case["baseline_result"] = "result.json"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    output = render_survey(manifest)

    assert "Baseline → refined" in output
    assert "Balanced baseline" in output
    assert "(+0.000)" in output


def test_write_survey_and_cli(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    output = tmp_path / "index.html"
    write_survey(manifest, output)
    with pytest.raises(ArtifactError, match="overwrite"):
        write_survey(manifest, output)
    assert main(["survey", str(manifest), "-o", str(output), "--overwrite"]) == 0
    assert output.read_text().startswith("<!doctype html>")


def test_survey_rejects_bad_manifest(tmp_path: Path) -> None:
    manifest = tmp_path / "bad.json"
    manifest.write_text('{"title":"x","date":"x","profile":"x","cases":[]}')
    with pytest.raises(ArtifactError, match="non-empty"):
        render_survey(manifest)

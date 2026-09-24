from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from llmpeg.artifact import Artifact, ArtifactError
from llmpeg.cli import main
from llmpeg.survey import render_survey, write_survey

REPO = Path(__file__).parents[1]


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
                "technology": {
                    "encoding": {
                        "name": "Local <vision> model",
                        "detail": "Source image → text & structure",
                    },
                    "reconstruction": {
                        "name": "Local image generator",
                        "detail": "Rendered text only → new pixels",
                    },
                },
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
    assert "1/1 cases are marked pass" in output
    assert "<code>balanced</code> profile" in output
    assert "Compression · semantic encoding" in output
    assert "Reconstruction · not decompression" in output
    assert "Local &lt;vision&gt; model" in output
    assert "Source image → text &amp; structure" in output
    assert "source image or source pixels" in output


def test_survey_intro_makes_no_claim_the_cases_do_not_support(
    tmp_path: Path, artifact: Artifact
) -> None:
    manifest = _manifest(tmp_path, artifact)
    output = render_survey(manifest)
    assert "cat images" not in output
    assert "public-domain" not in output
    assert "unverified provenance" not in output

    data = _load_manifest(manifest)
    data["cases"][0]["credit"]["license"] = "Provenance not verified — see EXPANDED.md"
    _save(manifest, data)
    assert "1 of 1 sources have unverified provenance." in render_survey(manifest)


def test_each_survey_keeps_its_ratings_under_its_own_storage_key(
    tmp_path: Path, artifact: Artifact
) -> None:
    manifest = _manifest(tmp_path, artifact)
    first = render_survey(manifest)
    data = _load_manifest(manifest)
    data["title"] = "Another survey"
    _save(manifest, data)
    second = render_survey(manifest)

    assert 'key="llmpeg-survey-v2:Cats & compression"' in first
    assert 'key="llmpeg-survey-v2:Another survey"' in second
    assert "if(!ids.includes(id))continue" in first


def test_render_survey_compares_baseline(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    data = json.loads(manifest.read_text(encoding="utf-8"))
    case = data["cases"][0]
    case["baseline_reconstruction"] = "baseline.png"
    case["baseline_result"] = "result.json"
    case["source_label"] = "Original <source>"
    case["baseline_label"] = "Qwen baseline"
    case["reconstruction_label"] = "Qwen challenger"
    case["finding"] = "Rejected: A/B order was <inconsistent>."
    data["comparison_label"] = "Baseline → challenger"
    manifest.write_text(json.dumps(data), encoding="utf-8")

    output = render_survey(manifest)

    assert "Baseline → challenger" in output
    assert "Original &lt;source&gt;" in output
    assert "Qwen baseline" in output
    assert "Qwen challenger" in output
    assert "Rejected: A/B order was &lt;inconsistent&gt;." in output
    assert "(+0.000)" in output


def test_render_survey_reports_plain_and_gzip_sizes(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    compressed = tmp_path / "artifact.llmpeg.json.gz"
    artifact.write(compressed, compress=True)
    data = _load_manifest(manifest)
    data["cases"][0]["artifact"] = compressed.name
    data["cases"][0]["report"] = "full-report.json"
    _save(manifest, data)

    output = render_survey(manifest)

    assert "plain artifact ratio" in output
    assert "gzip stored ratio" in output
    assert f"{compressed.stat().st_size:,} bytes on disk" in output
    assert '<a href="full-report.json">Full experiment report</a>' in output


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
    manifest.write_text(
        '{"title":"x","date":"x","profile":"x","technology":'
        '{"encoding":{"name":"x","detail":"x"},'
        '"reconstruction":{"name":"x","detail":"x"}},"cases":[]}'
    )
    with pytest.raises(ArtifactError, match="non-empty"):
        render_survey(manifest)


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda data: data.__setitem__("technology", "ollama"), "technology must be an object"),
        (
            lambda data: data["technology"].__setitem__("encoding", "ollama"),
            "technology encoding must be an object",
        ),
        (
            lambda data: data["technology"]["reconstruction"].__setitem__("detail", ""),
            "field detail must be a non-empty string",
        ),
    ],
)
def test_survey_rejects_invalid_technology_metadata(
    tmp_path: Path,
    artifact: Artifact,
    mutation: Any,
    message: str,
) -> None:
    manifest = _manifest(tmp_path, artifact)
    data = _load_manifest(manifest)
    mutation(data)
    _save(manifest, data)
    with pytest.raises(ArtifactError, match=message):
        render_survey(manifest)


def test_survey_rejects_non_string_optional_copy(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    data = _load_manifest(manifest)
    data["cases"][0]["finding"] = 42
    _save(manifest, data)
    with pytest.raises(ArtifactError, match="field finding must be a string"):
        render_survey(manifest)


def test_survey_preserves_old_manifests_with_unknown_technology(
    tmp_path: Path, artifact: Artifact
) -> None:
    manifest = _manifest(tmp_path, artifact)
    data = _load_manifest(manifest)
    del data["technology"]
    _save(manifest, data)

    output = render_survey(manifest)

    assert output.count("Not recorded") == 6
    assert output.count("This manifest predates structured technology provenance.") == 2


def _load_manifest(path: Path) -> dict[str, Any]:
    loaded: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _save(path: Path, data: dict[str, Any]) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_survey_rejects_a_case_that_is_not_an_object(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    data = _load_manifest(manifest)
    data["cases"] = ["not an object"]
    _save(manifest, data)
    with pytest.raises(ArtifactError, match="each survey case must be an object"):
        render_survey(manifest)


def test_survey_rejects_a_result_without_metrics(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    _save(tmp_path / "result.json", {"status": "pass"})
    with pytest.raises(ArtifactError, match="metrics missing"):
        render_survey(manifest)


def test_survey_rejects_a_case_without_credit(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    data = _load_manifest(manifest)
    del data["cases"][0]["credit"]
    _save(manifest, data)
    with pytest.raises(ArtifactError, match="credit missing"):
        render_survey(manifest)


def test_survey_rejects_a_non_numeric_metric(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    _save(
        tmp_path / "result.json",
        {
            "status": "pass",
            "metrics": {
                "visual_proxy_score": "high",
                "layout_score": 0.8,
                "dhash_similarity": 0.6,
                "palette_distance": 0.1,
            },
        },
    )
    with pytest.raises(ArtifactError, match="must be a number"):
        render_survey(manifest)


def test_survey_rejects_a_blank_required_field(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    data = _load_manifest(manifest)
    data["title"] = ""
    _save(manifest, data)
    with pytest.raises(ArtifactError, match="must be a non-empty string"):
        render_survey(manifest)


def test_survey_rejects_unreadable_and_non_object_data(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    (tmp_path / "result.json").write_text("{ broken", encoding="utf-8")
    with pytest.raises(ArtifactError, match="cannot read survey data"):
        render_survey(manifest)
    (tmp_path / "result.json").write_text("[]", encoding="utf-8")
    with pytest.raises(ArtifactError, match="root must be an object"):
        render_survey(manifest)


def test_survey_rejects_invalid_baseline_references(tmp_path: Path, artifact: Artifact) -> None:
    manifest = _manifest(tmp_path, artifact)
    data = _load_manifest(manifest)
    data["cases"][0]["baseline_result"] = ""
    _save(manifest, data)
    with pytest.raises(ArtifactError, match="baseline_result invalid"):
        render_survey(manifest)

    data["cases"][0]["baseline_result"] = "baseline.json"
    _save(tmp_path / "baseline.json", {"status": "pass"})
    _save(manifest, data)
    with pytest.raises(ArtifactError, match="baseline metrics missing"):
        render_survey(manifest)


def test_qwen_review_is_local_and_traceable_to_the_review_report() -> None:
    manifest_path = REPO / "survey/qwen-manifest.json"
    manifest = _load_manifest(manifest_path)
    output = render_survey(manifest_path)
    report = _load_manifest(REPO / "survey/qwen/review/report.json")
    by_case = {case["case"]: case for case in report["cases"]}

    assert "Local Ollama / qwen3.5:4b" in output
    assert "Local ComfyUI / Qwen-Image-2.1" in output
    assert "baseline" not in output.lower()
    assert "Codex built-in" not in output
    assert report["encoder"] == "ollama/qwen3.5:4b"
    assert report["resolution"] == 512
    assert report["seed"] == 42
    assert [case["id"] for case in manifest["cases"]] == [f"qwen-review-{name}" for name in by_case]

    for case in manifest["cases"]:
        for field in ("source", "reconstruction", "artifact", "prompt", "result", "report"):
            assert (manifest_path.parent / case[field]).is_file(), (
                f"missing {field} for {case['id']}"
            )
        measured = by_case[case["id"].removeprefix("qwen-review-")]
        result = _load_manifest(manifest_path.parent / case["result"])
        assert result["status"] == measured["status"]
        source, rendered = measured["source_tone"], measured["reconstruction_tone"]
        for key in ("luminance", "contrast", "saturation"):
            assert f"{key} {source[key]} → {rendered[key]}" in case["finding"]


def test_tone_candidates_are_traceable_to_their_measurements() -> None:
    manifest_path = REPO / "survey/qwen-tone-manifest.json"
    manifest = _load_manifest(manifest_path)
    output = render_survey(manifest_path)

    assert "Current pipeline" in output
    assert "Closed loop" in output
    assert "Regraded" in output
    for case in manifest["cases"]:
        for field in (
            "source",
            "baseline_reconstruction",
            "reconstruction",
            "artifact",
            "prompt",
            "result",
            "baseline_result",
            "report",
        ):
            assert (manifest_path.parent / case[field]).is_file(), (
                f"missing {field} for {case['id']}"
            )
        rows = _load_manifest(manifest_path.parent / case["report"])["rows"]
        image = Path(case["reconstruction"]).name
        row = next(row for row in rows if row["image"] == image)
        assert row["extra_negative"] in case["finding"]
        for key in ("luminance", "saturation"):
            assert f"{key} {row['reconstruction_tone'][key]}" in case["finding"]
            assert f"{key} {row['source_tone'][key]}" in case["finding"]


def test_pages_workflow_publishes_only_the_qwen_review_pages() -> None:
    workflow = (REPO / ".github/workflows/pages.yml").read_text(encoding="utf-8")
    assert "cp -R survey/. _site/" in workflow
    assert "rm _site/*.html" in workflow
    assert workflow.index("rm _site/*.html") < workflow.index(
        "cp survey/qwen.html _site/index.html"
    )
    assert workflow.index("rm _site/*.html") < workflow.index(
        "cp survey/qwen-tone.html _site/tone.html"
    )
    assert "balanced.html" not in workflow

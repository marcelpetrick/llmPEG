from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from promptpress.artifact import Artifact, ArtifactError, FidelityProfile, SourceInfo, source_digest
from promptpress.evaluation import evaluate_images, evaluate_with_artifact


def test_identical_images_pass_gist_and_score_above_changed(
    sample_image: Path, tmp_path: Path
) -> None:
    same = evaluate_images(sample_image, sample_image, FidelityProfile.GIST)
    changed_path = tmp_path / "changed.png"
    Image.new("RGB", (80, 200), "lime").save(changed_path)
    changed = evaluate_images(sample_image, changed_path, FidelityProfile.GIST)
    assert same.status == "pass"
    assert same.metrics.visual_proxy_score == 1.0
    assert same.metrics.palette_distance == 0.0
    assert same.metrics.visual_proxy_score > changed.metrics.visual_proxy_score
    assert same.metrics.aspect_similarity > changed.metrics.aspect_similarity


def test_detailed_text_is_incomplete_failed_or_passed(
    sample_image: Path, artifact: Artifact
) -> None:
    content = sample_image.read_bytes()
    artifact = replace(
        artifact,
        source=SourceInfo(160, 120, len(content), "image/png", source_digest(content)),
    )
    report = evaluate_with_artifact(sample_image, sample_image, artifact)
    assert report.status == "incomplete"
    assert report.checks["critical_text_recall"] is None
    failed = evaluate_with_artifact(sample_image, sample_image, artifact, ocr_text="wrong")
    assert failed.status == "fail"
    passed = evaluate_with_artifact(sample_image, sample_image, artifact, ocr_text="EXAMPLE")
    assert passed.status == "pass"
    assert '"status": "pass"' in passed.to_json()


def test_structural_change_affects_metrics(sample_image: Path, tmp_path: Path) -> None:
    altered = tmp_path / "altered.png"
    image = Image.new("RGB", (160, 120), "navy")
    ImageDraw.Draw(image).ellipse((30, 10, 130, 110), fill="white")
    image.save(altered)
    report = evaluate_images(sample_image, altered, FidelityProfile.BALANCED)
    values = report.metrics
    for value in (
        values.aspect_similarity,
        values.dhash_similarity,
        values.histogram_similarity,
        values.edge_similarity,
        values.palette_distance,
        values.layout_score,
        values.visual_proxy_score,
    ):
        assert 0 <= value <= 1


def test_evaluation_rejects_bad_image(sample_image: Path, tmp_path: Path) -> None:
    bad = tmp_path / "bad.png"
    bad.write_text("bad")
    with pytest.raises(ArtifactError, match="cannot evaluate"):
        evaluate_images(sample_image, bad, FidelityProfile.GIST)


def test_evaluation_rejects_source_that_does_not_match_artifact(
    sample_image: Path, artifact: Artifact
) -> None:
    with pytest.raises(ArtifactError, match="does not match"):
        evaluate_with_artifact(sample_image, sample_image, artifact)


def test_detailed_image_without_text_does_not_require_ocr(
    sample_image: Path, artifact: Artifact
) -> None:
    content = sample_image.read_bytes()
    artifact = replace(
        artifact,
        critical_text=(),
        source=SourceInfo(160, 120, len(content), "image/png", source_digest(content)),
    )
    report = evaluate_with_artifact(sample_image, sample_image, artifact)
    assert report.status == "pass"
    assert report.metrics.critical_text_recall == 1.0

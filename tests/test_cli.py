from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from promptpress.artifact import Artifact, SourceInfo, source_digest
from promptpress.cli import main


def test_reconstruct_inspect_and_evaluate_cli(
    artifact: Artifact, sample_image: Path, tmp_path: Path, capsys: object
) -> None:
    content = sample_image.read_bytes()
    artifact = replace(
        artifact,
        source=SourceInfo(160, 120, len(content), "image/png", source_digest(content)),
    )
    artifact_path = tmp_path / "artifact.json"
    artifact.write(artifact_path)
    prompt_path = tmp_path / "prompt.txt"
    assert main(["reconstruct", str(artifact_path), "-o", str(prompt_path)]) == 0
    assert "Primary request" in prompt_path.read_text()
    assert main(["reconstruct", str(artifact_path)]) == 0
    assert "Create a new image" in capsys.readouterr().out  # type: ignore[attr-defined]
    assert main(["inspect", str(artifact_path)]) == 0
    assert "size ratio:" in capsys.readouterr().out  # type: ignore[attr-defined]
    ocr = tmp_path / "ocr.txt"
    ocr.write_text("EXAMPLE")
    report = tmp_path / "report.json"
    assert (
        main(
            [
                "evaluate",
                str(sample_image),
                str(sample_image),
                "--artifact",
                str(artifact_path),
                "--ocr-text",
                str(ocr),
                "-o",
                str(report),
            ]
        )
        == 0
    )
    assert '"status": "pass"' in report.read_text()


def test_cli_refuses_overwrite_and_reports_errors(
    artifact: Artifact, tmp_path: Path, capsys: object
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact.write(artifact_path)
    output = tmp_path / "exists.txt"
    output.write_text("keep")
    assert main(["reconstruct", str(artifact_path), "-o", str(output)]) == 2
    assert "refusing to overwrite" in capsys.readouterr().err  # type: ignore[attr-defined]
    assert output.read_text() == "keep"
    assert main(["inspect", str(tmp_path / "missing.json")]) == 2


def test_encode_cli(artifact: Artifact, sample_image: Path, tmp_path: Path) -> None:
    output = tmp_path / "encoded.json"
    with patch("promptpress.cli.encode_image", return_value=artifact) as encode:
        assert (
            main(
                [
                    "encode",
                    str(sample_image),
                    "-o",
                    str(output),
                    "--profile",
                    "detailed",
                    "--host",
                    "http://example.test",
                ]
            )
            == 0
        )
    assert output.exists()
    assert encode.call_args.args[2].value == "detailed"


def test_evaluate_cli_returns_status_exit_code(
    artifact: Artifact, sample_image: Path, tmp_path: Path
) -> None:
    content = sample_image.read_bytes()
    artifact = replace(
        artifact,
        source=SourceInfo(160, 120, len(content), "image/png", source_digest(content)),
    )
    artifact_path = tmp_path / "artifact.json"
    artifact.write(artifact_path)
    base = [
        "evaluate",
        str(sample_image),
        str(sample_image),
        "--artifact",
        str(artifact_path),
    ]
    assert main(base) == 3
    wrong = tmp_path / "wrong.txt"
    wrong.write_text("wrong")
    assert main([*base, "--ocr-text", str(wrong)]) == 1

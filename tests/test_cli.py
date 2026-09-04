from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from llmpeg.artifact import Artifact, SourceInfo, source_digest
from llmpeg.cli import artifact_path_for, generated_path_for, main
from llmpeg.generators import GeneratedImage


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
    with patch("llmpeg.cli.encode_image", return_value=artifact) as encode:
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


def test_verify_reports_conformance_and_rejects_foreign_json(
    artifact: Artifact, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = tmp_path / "good.llmpeg.json"
    artifact.write(good)
    assert main(["verify", str(good)]) == 0
    out = capsys.readouterr().out
    assert "llmPEG 1.0 (lpg1)" in out
    assert "conforms: yes" in out

    foreign = tmp_path / "foreign.json"
    foreign.write_text('{"hello": "world"}', encoding="utf-8")
    assert main(["verify", str(foreign)]) == 2
    assert "not an llmPEG artifact" in capsys.readouterr().err


def test_encode_defaults_the_output_beside_the_image(
    artifact: Artifact, sample_image: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """`llmpeg encode photo.jpg` needs no flags and writes photo.llmpeg.json."""
    expected = sample_image.parent / f"{sample_image.name}.llmpeg.json"
    with patch("llmpeg.cli.encode_image", return_value=artifact):
        assert main(["encode", str(sample_image)]) == 0
    assert expected.exists()
    out = capsys.readouterr().out
    assert str(expected) in out
    assert ":1" in out  # the ratio is reported without needing `inspect`


def test_evaluate_defaults_the_artifact_beside_the_source(
    artifact: Artifact, sample_image: Path
) -> None:
    """`llmpeg evaluate photo.png regen.png` finds photo.llmpeg.json on its own."""
    raw = sample_image.read_bytes()
    stored = replace(
        artifact,
        source=SourceInfo(160, 120, len(raw), "image/png", source_digest(raw)),
    )
    stored.write(sample_image.parent / f"{sample_image.name}.llmpeg.json")
    assert main(["evaluate", str(sample_image), str(sample_image)]) in {0, 1, 3}


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("photo.jpg", "photo.jpg.llmpeg.json"),
        ("photo.png", "photo.png.llmpeg.json"),
        ("my.photo.jpg", "my.photo.jpg.llmpeg.json"),
        ("noextension", "noextension.llmpeg.json"),
    ],
)
def test_artifact_path_keeps_the_whole_filename(name: str, expected: str) -> None:
    """The suffix is appended, so photo.jpg and photo.png cannot collide."""
    assert artifact_path_for(Path(name)).name == expected


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("photo.jpg.llmpeg.json", "photo.jpg.reconstructed.png"),
        ("artifact.json", "artifact.reconstructed.png"),
    ],
)
def test_generated_path_preserves_the_source_name(name: str, expected: str) -> None:
    assert generated_path_for(Path(name)).name == expected


def test_generate_cli_prefers_comfyui(
    artifact: Artifact, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact_path = tmp_path / "photo.jpg.llmpeg.json"
    artifact.write(artifact_path)
    output = tmp_path / "generated.png"
    result = GeneratedImage(b"generated", "comfyui")

    with patch("llmpeg.cli.generate_prefer_comfyui", return_value=result) as generate:
        assert main(["generate", str(artifact_path), "-o", str(output)]) == 0

    assert output.read_bytes() == b"generated"
    assert "generator: comfyui" in capsys.readouterr().out
    assert "Primary request" in generate.call_args.args[0]
    assert generate.call_args.args[1:3] == (160, 120)


def test_generate_cli_reports_codex_fallback(
    artifact: Artifact, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact_path = tmp_path / "photo.llmpeg.json"
    artifact.write(artifact_path)
    result = GeneratedImage(b"generated", "codex", "service offline")

    with patch("llmpeg.cli.generate_prefer_comfyui", return_value=result):
        assert main(["generate", str(artifact_path)]) == 0

    captured = capsys.readouterr()
    assert "generator: codex" in captured.out
    assert "ComfyUI unavailable (service offline)" in captured.err
    assert (tmp_path / "photo.reconstructed.png").read_bytes() == b"generated"


def test_generate_cli_can_select_codex(
    artifact: Artifact, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact.write(artifact_path)
    output = tmp_path / "generated.png"

    with patch("llmpeg.cli.generate_codex", return_value=b"codex") as generate:
        assert (
            main(
                [
                    "generate",
                    str(artifact_path),
                    "--generator",
                    "codex",
                    "--timeout",
                    "12",
                    "-o",
                    str(output),
                ]
            )
            == 0
        )

    assert output.read_bytes() == b"codex"
    assert generate.call_args.args[1:] == (160, 120, 12.0)
    assert "generator: codex" in capsys.readouterr().out


def test_generate_cli_checks_overwrite_before_generation(
    artifact: Artifact, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    artifact_path = tmp_path / "artifact.json"
    artifact.write(artifact_path)
    output = tmp_path / "generated.png"
    output.write_bytes(b"keep")

    with patch("llmpeg.cli.generate_prefer_comfyui") as generate:
        assert main(["generate", str(artifact_path), "-o", str(output)]) == 2

    generate.assert_not_called()
    assert output.read_bytes() == b"keep"
    assert "refusing to overwrite" in capsys.readouterr().err

from __future__ import annotations

import io
import subprocess
import urllib.error
from pathlib import Path
from unittest.mock import patch

import pytest
from PIL import Image

from llmpeg.artifact import ArtifactError
from llmpeg.generators import (
    GeneratorUnavailable,
    comfyui_reachable,
    default_comfyui_script,
    generate_codex,
    generate_comfyui,
    generate_prefer_comfyui,
)


def png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (8, 6), "navy").save(stream, format="PNG")
    return stream.getvalue()


def test_default_comfyui_script_prefers_an_existing_candidate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    repo = tmp_path / "llmPEG"
    script = tmp_path / "ComfyUI" / "generate_image.sh"
    repo.mkdir()
    script.parent.mkdir()
    script.touch()
    monkeypatch.chdir(repo)

    assert default_comfyui_script() == script


def test_comfyui_health_check(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    calls: list[tuple[str, float]] = []

    def open_ok(url: str, timeout: float) -> Response:
        calls.append((url, timeout))
        return Response()

    monkeypatch.setattr("llmpeg.generators.urllib.request.urlopen", open_ok)
    assert comfyui_reachable("http://comfy.test/", 10) is True
    assert calls == [("http://comfy.test/system_stats", 2.0)]

    def open_fail(_url: str, timeout: float) -> Response:
        del timeout
        raise urllib.error.URLError("offline")

    monkeypatch.setattr("llmpeg.generators.urllib.request.urlopen", open_fail)
    assert comfyui_reachable("http://comfy.test", 1) is False


def test_comfyui_requires_its_adapter_script(tmp_path: Path) -> None:
    with pytest.raises(GeneratorUnavailable, match="script not found"):
        generate_comfyui("cat", tmp_path / "missing.sh", "http://comfy.test", 5)


def test_comfyui_returns_a_valid_image(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    script = tmp_path / "generate_image.sh"
    script.touch()

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        Path(command[2]).write_bytes(png_bytes())
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr("llmpeg.generators.subprocess.run", run)
    assert generate_comfyui("cat", script, "http://comfy.test", 5) == png_bytes()


@pytest.mark.parametrize(
    ("error", "reachable", "exception", "message"),
    [
        (subprocess.TimeoutExpired(["comfy"], 5), False, GeneratorUnavailable, "timed out"),
        (subprocess.TimeoutExpired(["comfy"], 5), True, ArtifactError, "timed out"),
        (
            subprocess.CalledProcessError(1, ["comfy"], stderr="workflow failed"),
            False,
            GeneratorUnavailable,
            "workflow failed",
        ),
        (OSError("cannot execute"), True, ArtifactError, "ComfyUI failed"),
    ],
)
def test_comfyui_classifies_adapter_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error: Exception,
    reachable: bool,
    exception: type[Exception],
    message: str,
) -> None:
    script = tmp_path / "generate_image.sh"
    script.touch()
    monkeypatch.setattr(
        "llmpeg.generators.subprocess.run", lambda *_args, **_kwargs: (_ for _ in ()).throw(error)
    )
    monkeypatch.setattr("llmpeg.generators.comfyui_reachable", lambda *_args: reachable)

    with pytest.raises(exception, match=message):
        generate_comfyui("cat", script, "http://comfy.test", 5)


@pytest.mark.parametrize(("payload", "message"), [(None, "no image"), (b"bad", "invalid image")])
def test_comfyui_rejects_bad_output(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: bytes | None,
    message: str,
) -> None:
    script = tmp_path / "generate_image.sh"
    script.touch()

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        if payload is not None:
            Path(command[2]).write_bytes(payload)
        return subprocess.CompletedProcess(command, 0, "adapter output", "")

    monkeypatch.setattr("llmpeg.generators.subprocess.run", run)
    with pytest.raises(ArtifactError, match=message):
        generate_comfyui("cat", script, "http://comfy.test", 5)


def test_codex_requires_the_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmpeg.generators.shutil.which", lambda _name: None)
    with pytest.raises(GeneratorUnavailable, match="not on PATH"):
        generate_codex("cat", 10, 10, 5)


@pytest.mark.parametrize(
    ("width", "height", "orientation"),
    [(12, 8, "landscape"), (8, 12, "portrait"), (8, 8, "square")],
)
def test_codex_invokes_imagegen_with_the_requested_orientation(
    monkeypatch: pytest.MonkeyPatch,
    width: int,
    height: int,
    orientation: str,
) -> None:
    seen: list[str] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.extend(command)
        work = Path(command[command.index("-C") + 1])
        assert (work / "prompt.txt").read_text(encoding="utf-8") == "a cat"
        (work / "out.png").write_bytes(png_bytes())
        return subprocess.CompletedProcess(command, 0, "DONE", "")

    monkeypatch.setattr("llmpeg.generators.shutil.which", lambda _name: "/usr/bin/codex")
    monkeypatch.setattr("llmpeg.generators.subprocess.run", run)

    assert generate_codex("a cat", width, height, 5) == png_bytes()
    instruction = seen[-1]
    assert "$imagegen" in instruction
    assert f"{width}x{height} ({orientation})" in instruction


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (subprocess.TimeoutExpired(["codex"], 5), "timed out"),
        (subprocess.CalledProcessError(1, ["codex"], stderr="login failed"), "login failed"),
    ],
)
def test_codex_reports_process_failures(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    monkeypatch.setattr("llmpeg.generators.shutil.which", lambda _name: "/usr/bin/codex")
    monkeypatch.setattr(
        "llmpeg.generators.subprocess.run", lambda *_args, **_kwargs: (_ for _ in ()).throw(error)
    )
    with pytest.raises(ArtifactError, match=message):
        generate_codex("cat", 10, 10, 5)


@pytest.mark.parametrize(("payload", "message"), [(None, "no image"), (b"bad", "invalid image")])
def test_codex_rejects_bad_output(
    monkeypatch: pytest.MonkeyPatch, payload: bytes | None, message: str
) -> None:
    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        work = Path(command[command.index("-C") + 1])
        if payload is not None:
            (work / "out.png").write_bytes(payload)
        return subprocess.CompletedProcess(command, 0, "agent output", "")

    monkeypatch.setattr("llmpeg.generators.shutil.which", lambda _name: "/usr/bin/codex")
    monkeypatch.setattr("llmpeg.generators.subprocess.run", run)
    with pytest.raises(ArtifactError, match=message):
        generate_codex("cat", 10, 10, 5)


def test_preferred_generator_uses_comfyui(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmpeg.generators.generate_comfyui", lambda *_args: b"comfy")
    with patch("llmpeg.generators.generate_codex") as codex:
        result = generate_prefer_comfyui("cat", 10, 10, Path("script"), "host", 5)
    assert result.data == b"comfy"
    assert result.provider == "comfyui"
    assert result.fallback_reason is None
    codex.assert_not_called()


def test_preferred_generator_falls_back_only_when_comfyui_is_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: object) -> bytes:
        raise GeneratorUnavailable("service offline")

    monkeypatch.setattr("llmpeg.generators.generate_comfyui", unavailable)
    monkeypatch.setattr("llmpeg.generators.generate_codex", lambda *_args: b"codex")
    result = generate_prefer_comfyui("cat", 10, 10, Path("script"), "host", 5)
    assert result.data == b"codex"
    assert result.provider == "codex"
    assert result.fallback_reason == "service offline"

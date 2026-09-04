from __future__ import annotations

import json
import subprocess
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image

from llmpeg.artifact import ArtifactError
from prototypeWebUI import server as web


@pytest.fixture
def web_server() -> Iterator[str]:
    server = ThreadingHTTPServer(("127.0.0.1", 0), web.Handler)
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_file_page_targets_local_backend_without_unsafe_html() -> None:
    page = web.INDEX.read_text(encoding="utf-8")
    assert 'location.protocol === "file:" ? "http://127.0.0.1:8000"' in page
    assert ".innerHTML" not in page
    assert 'aria-label="Workflow: image to prompt to new image"' in page
    assert "IMAGE <small>your source</small>" in page
    assert "PROMPT <small>editable text</small>" in page
    assert "NEW IMAGE <small>invented pixels</small>" in page
    assert "performance.now()" in page
    assert "Usually about 40 seconds" in page
    assert 'id="theme"' in page
    assert 'data-theme="dark"' in page
    assert 'localStorage.setItem("llmpeg-theme", theme)' in page


def test_config_defaults_to_codex(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLMPEG_GENERATOR", raising=False)
    assert web.Config().generator == "codex"


def test_config_allows_file_origin(web_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.CONFIG, "vision_host", "http://vision.test:11434")
    request = urllib.request.Request(
        f"{web_server}/api/config", headers={"Origin": web.FILE_ORIGIN}
    )
    with urllib.request.urlopen(request) as response:
        payload = json.load(response)
        assert response.headers["Access-Control-Allow-Origin"] == web.FILE_ORIGIN
    assert payload["vision_host"] == "http://vision.test:11434"
    assert payload["vision_configured"] is True


def test_preflight_allows_file_page_posts(web_server: str) -> None:
    request = urllib.request.Request(
        f"{web_server}/api/encode",
        method="OPTIONS",
        headers={
            "Origin": web.FILE_ORIGIN,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
            "Access-Control-Request-Private-Network": "true",
        },
    )
    with urllib.request.urlopen(request) as response:
        assert response.status == 204
        assert response.headers["Access-Control-Allow-Origin"] == web.FILE_ORIGIN
        assert response.headers["Access-Control-Allow-Private-Network"] == "true"


def test_encode_rejects_non_image_upload(web_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.CONFIG, "vision_host", "http://vision.test:11434")
    request = urllib.request.Request(
        f"{web_server}/api/encode",
        data=b"not an image",
        method="POST",
        headers={"Content-Type": "image/jpeg"},
    )
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request)
    assert caught.value.code == 400
    assert json.load(caught.value)["error"] == "uploaded data is not a supported image"


def test_generation_request_accepts_ui_values() -> None:
    assert web.generation_request(
        {"prompt": "a tabby cat", "width": 1024, "height": 1024, "seed": 42}
    ) == ("a tabby cat", 1024, 1024, 42)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"prompt": "cat", "width": "wide"},
        {"prompt": "cat", "width": 128},
        {"prompt": "cat", "height": 2048},
        {"prompt": "x" * (web.MAX_PROMPT_CHARS + 1)},
    ],
)
def test_generation_request_rejects_invalid_values(payload: object) -> None:
    with pytest.raises(ArtifactError):
        web.generation_request(payload)


def test_unknown_generator_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.CONFIG, "generator", "mystery")
    with pytest.raises(ArtifactError, match="unsupported generator"):
        web.generate("cat", 1024, 1024, 42)


def test_codex_generator_explicitly_invokes_imagegen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    command_seen: list[str] = []
    prompt_seen: list[str] = []

    def run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        command_seen.extend(command)
        work = Path(command[command.index("-C") + 1])
        prompt_seen.append((work / "prompt.txt").read_text(encoding="utf-8"))
        Image.new("RGB", (8, 8), "navy").save(work / "out.png")
        return subprocess.CompletedProcess(command, 0, "DONE", "")

    monkeypatch.setattr("prototypeWebUI.server.shutil.which", lambda _name: "/usr/bin/codex")
    monkeypatch.setattr("prototypeWebUI.server.subprocess.run", run)

    generated = web.generate_codex("a tabby cat on grass", 1024, 1024, 42)

    assert generated.startswith(b"\x89PNG\r\n\x1a\n")
    assert prompt_seen == ["a tabby cat on grass"]
    assert "--ephemeral" in command_seen
    assert "image_generation" in command_seen
    assert "$imagegen" in command_seen[-1]
    assert "untrusted data" in command_seen[-1]
    assert "./out.png" in command_seen[-1]


def test_codex_generator_requires_installed_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("prototypeWebUI.server.shutil.which", lambda _name: None)
    with pytest.raises(ArtifactError, match="not on PATH"):
        web.generate_codex("cat", 1024, 1024, 42)


def test_index_exists_in_prototype_directory() -> None:
    assert Path(web.__file__).resolve().parent / "index.html" == web.INDEX

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

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


def test_index_exists_in_prototype_directory() -> None:
    assert Path(web.__file__).resolve().parent / "index.html" == web.INDEX

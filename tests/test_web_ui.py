from __future__ import annotations

import base64
import io
import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest
from PIL import Image

from llmpeg.artifact import Artifact, ArtifactError, FidelityProfile
from llmpeg.providers import DEFAULT_OLLAMA_VISION_HOST, DEFAULT_VISION_MODEL
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


def _png(width: int = 64, height: int = 48, color: str = "navy") -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), color).save(buffer, format="PNG")
    return buffer.getvalue()


def test_page_is_local_only_and_adds_automatic_rating() -> None:
    page = web.INDEX.read_text(encoding="utf-8")
    assert 'location.protocol === "file:" ? "http://127.0.0.1:8000"' in page
    assert ".innerHTML" not in page
    assert 'aria-label="Workflow: image to prompt to new image"' in page
    assert "IMAGE <small>your source</small>" in page
    assert "PROMPT <small>editable text</small>" in page
    assert "NEW IMAGE <small>invented pixels</small>" in page
    assert "local Qwen-Image-2.1" in page
    assert 'id="generator"' not in page
    assert "Codex" not in page
    assert "Pollinations" not in page
    assert "Automatic1111" not in page
    assert 'request("/api/rate"' in page
    assert "not a human rating or proof" in page
    assert "semantic_spreads" in page
    assert 'id="theme"' in page
    assert 'data-theme="dark"' in page
    assert 'localStorage.setItem("llmpeg-theme", theme)' in page


def test_config_defaults_to_local_qwen(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("OLLAMA_VISION_HOST", "LLMPEG_MODEL", "LLMPEG_COMFYUI_HOST"):
        monkeypatch.delenv(name, raising=False)
    config = web.Config()
    assert config.vision_host == DEFAULT_OLLAMA_VISION_HOST
    assert config.model == DEFAULT_VISION_MODEL
    assert config.comfyui_host == "http://127.0.0.1:8188"
    assert config.rating_repeats == 3


def test_config_allows_file_origin(web_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(web.CONFIG, "vision_host", "http://vision.test:11434")
    monkeypatch.setattr(web, "comfyui_reachable", lambda: True)
    request = urllib.request.Request(
        f"{web_server}/api/config", headers={"Origin": web.FILE_ORIGIN}
    )
    with urllib.request.urlopen(request) as response:
        payload = json.load(response)
        assert response.headers["Access-Control-Allow-Origin"] == web.FILE_ORIGIN
    assert payload["vision_host"] == "http://vision.test:11434"
    assert payload["vision_configured"] is True
    assert payload["generator"] == "comfyui/qwen-image-2.1"
    assert payload["comfyui_reachable"] is True
    assert payload["rating_repeats"] == web.CONFIG.rating_repeats


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


def test_generate_route_uses_only_local_qwen(
    web_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, int, int]] = []

    def generate(prompt: str, resolution: int, seed: int) -> bytes:
        calls.append((prompt, resolution, seed))
        return _png()

    monkeypatch.setattr(web, "generate_comfyui", generate)
    request = urllib.request.Request(
        f"{web_server}/api/generate",
        data=json.dumps({"prompt": "cat", "width": 768, "height": 768, "seed": 7}).encode(),
        method="POST",
        headers={"Content-Type": "application/json", "Origin": web.FILE_ORIGIN},
    )

    with urllib.request.urlopen(request) as response:
        assert response.read().startswith(b"\x89PNG")
        assert response.headers["X-llmPEG-Generator"] == "comfyui/qwen-image-2.1"
        assert response.headers["Access-Control-Expose-Headers"] == "X-llmPEG-Generator"
    assert calls == [("cat", 768, 7)]


def test_encode_reports_plain_and_gzip_sizes(
    artifact: Artifact, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web, "encode_image", lambda _path, _provider, _profile: artifact)
    result = web.encode(_png(), FidelityProfile.DETAILED)

    assert result["artifact_bytes"] == len(artifact.to_bytes())
    assert result["artifact_gzip_bytes"] == len(artifact.to_gzip_bytes())
    assert result["gzip_ratio"] == round(result["encoded_bytes"] / len(artifact.to_gzip_bytes()), 1)
    assert '["Ratio (gzip)", `${data.gzip_ratio}:1`]' in web.INDEX.read_text(encoding="utf-8")


def test_encode_rejects_non_image_upload(web_server: str) -> None:
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


def _rejected_upload(web_server: str, data: bytes) -> urllib.error.HTTPError:
    request = urllib.request.Request(
        f"{web_server}/api/encode",
        data=data,
        method="POST",
        headers={"Content-Type": "image/png"},
    )
    with pytest.raises(urllib.error.HTTPError) as caught:
        urllib.request.urlopen(request)
    return caught.value


def test_encode_refuses_too_many_pixels_before_decoding(
    web_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(web, "DEFAULT_MAX_IMAGE_PIXELS", 1000)
    error = _rejected_upload(web_server, _png())
    assert error.code == 400
    assert json.load(error)["error"] == "image has 3072 pixels; limit is 1000 pixels"


def test_encode_answers_a_decompression_bomb(
    web_server: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1000)
    error = _rejected_upload(web_server, _png())
    assert error.code == 400
    assert json.load(error)["error"].startswith("image too large:")


def test_generation_request_accepts_ui_values() -> None:
    assert web.generation_request(
        {"prompt": "a tabby cat", "width": 1024, "height": 1024, "seed": 42}
    ) == ("a tabby cat", 1024, 42)


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"prompt": "cat", "width": "wide"},
        {"prompt": "cat", "width": 128},
        {"prompt": "cat", "height": 2048},
        {"prompt": "cat", "width": 768, "height": 1024},
        {"prompt": "cat", "width": 1000, "height": 1000},
        {"prompt": "x" * (web.MAX_PROMPT_CHARS + 1)},
    ],
)
def test_generation_request_rejects_invalid_values(payload: object) -> None:
    with pytest.raises(ArtifactError):
        web.generation_request(payload)


def test_comfyui_wrapper_passes_runtime_configuration(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[object, ...]] = []
    monkeypatch.setattr(web.CONFIG, "comfyui_host", "http://comfy.test")
    monkeypatch.setattr(web.CONFIG, "timeout", 99.0)
    def generate(*args: object) -> bytes:
        calls.append(args)
        return b"image"

    monkeypatch.setattr("llmpeg.generators.generate_comfyui", generate)
    assert web.generate_comfyui("cat", 1024, 7) == b"image"
    assert calls == [("cat", 1024, 7, "http://comfy.test", 99.0)]


def test_rating_request_decodes_images_and_validates_metadata() -> None:
    source = _png()
    reconstruction = _png(color="purple")
    result = web.rating_request(
        {
            "source": base64.b64encode(source).decode(),
            "reconstruction": base64.b64encode(reconstruction).decode(),
            "prompt": " cat ",
            "critical_text": ["CAT"],
        }
    )
    assert result == (source, reconstruction, "cat", ("CAT",))


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {},
        {"prompt": "cat", "source": "!", "reconstruction": "!"},
        {"prompt": "cat", "source": "eA==", "reconstruction": "eA==", "critical_text": "x"},
        {
            "prompt": "cat",
            "source": "eA==",
            "reconstruction": "eA==",
            "critical_text": ["x" * 601],
        },
    ],
)
def test_rating_request_rejects_invalid_values(payload: object) -> None:
    with pytest.raises(ArtifactError):
        web.rating_request(payload)


def test_rate_route_returns_local_rating(web_server: str, monkeypatch: pytest.MonkeyPatch) -> None:
    source = _png()
    reconstruction = _png(color="purple")
    expected: dict[str, object] = {"method": "experimental", "verdict": "partial"}
    calls: list[tuple[bytes, bytes, str, tuple[str, ...]]] = []

    def rate(
        first: bytes, second: bytes, prompt: str, critical: tuple[str, ...]
    ) -> dict[str, object]:
        calls.append((first, second, prompt, critical))
        return expected

    monkeypatch.setattr(web, "rate_reconstruction", rate)
    request = urllib.request.Request(
        f"{web_server}/api/rate",
        data=json.dumps(
            {
                "source": base64.b64encode(source).decode(),
                "reconstruction": base64.b64encode(reconstruction).decode(),
                "prompt": "cat",
                "critical_text": ["CAT"],
            }
        ).encode(),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request) as response:
        assert json.load(response) == expected
    assert calls == [(source, reconstruction, "cat", ("CAT",))]


def test_index_exists_in_prototype_directory() -> None:
    assert Path(web.__file__).resolve().parent / "index.html" == web.INDEX

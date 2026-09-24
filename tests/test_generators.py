from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from typing import Any

import pytest
from PIL import Image

from llmpeg.artifact import ArtifactError
from llmpeg.generators import (
    GeneratorUnavailable,
    _first_image,
    _http_error_detail,
    _qwen_workflow,
    _raise_execution_error,
    _remaining_timeout,
    _request_bytes,
    _request_json,
    comfyui_reachable,
    generate_comfyui,
)


class Response(io.BytesIO):
    def __enter__(self) -> Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def png_bytes() -> bytes:
    stream = io.BytesIO()
    Image.new("RGB", (8, 6), "navy").save(stream, format="PNG")
    return stream.getvalue()


def image_result(prompt_id: str = "job-1") -> dict[str, Any]:
    return {
        prompt_id: {
            "status": {"status_str": "success", "messages": []},
            "outputs": {
                "8": {
                    "images": [
                        {
                            "filename": "image.png",
                            "subfolder": "llmpeg",
                            "type": "output",
                        }
                    ]
                }
            },
        }
    }


def test_comfyui_health_check(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_qwen_workflow_matches_the_local_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmpeg.generators.uuid.uuid4", lambda: type("UUID", (), {"hex": "abc"})())
    workflow = _qwen_workflow("a purple cat", 768, 7)

    assert workflow["1"]["inputs"]["unet_name"] == "qwen_image_2.1_int8_convrot.safetensors"
    assert workflow["2"]["inputs"] == {
        "clip_name": "qwen3vl_8b_w4a8.safetensors",
        "type": "qwen_image",
        "device": "default",
    }
    assert workflow["4"]["inputs"]["device"] == "cpu"
    assert workflow["4"]["inputs"]["dtype"] == "int8"
    assert workflow["5"]["inputs"]["prompt"] == "a purple cat"
    assert workflow["5"]["inputs"]["resolution"] == 768
    assert workflow["6"]["inputs"]["seed"] == 7
    assert workflow["6"]["inputs"]["steps"] == 30
    assert workflow["6"]["inputs"]["cfg"] == 3.5
    assert workflow["6"]["inputs"]["sampler_name"] == "euler"
    assert workflow["6"]["inputs"]["scheduler"] == "simple"
    assert workflow["8"]["inputs"]["filename_prefix"] == "llmpeg/abc"


def test_qwen_workflow_applies_tone_experiment_overrides() -> None:
    default = _qwen_workflow("cat", 512, 42)
    workflow = _qwen_workflow("cat", 512, 42, cfg=1.5, steps=25, extra_negative=" sepia, tint ")

    assert workflow["6"]["inputs"]["cfg"] == 1.5
    assert workflow["6"]["inputs"]["steps"] == 25
    assert workflow["5"]["inputs"]["negative_prompt"] == (
        default["5"]["inputs"]["negative_prompt"] + ", sepia, tint"
    )
    assert _qwen_workflow("cat", 512, 42, extra_negative="  ")["5"] == default["5"]


def test_generate_comfyui_submits_polls_and_fetches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    submitted: dict[str, Any] = {}
    histories = [{}, image_result()]

    def urlopen(request: str | urllib.request.Request, timeout: float) -> Response:
        assert timeout > 0
        url = request.full_url if isinstance(request, urllib.request.Request) else request
        calls.append(url)
        if url.endswith("/prompt"):
            assert isinstance(request, urllib.request.Request)
            assert isinstance(request.data, bytes)
            submitted.update(json.loads(request.data))
            return Response(b'{"prompt_id":"job-1"}')
        if "/history/" in url:
            return Response(json.dumps(histories.pop(0)).encode())
        if "/view?" in url:
            assert "filename=image.png" in url
            assert "subfolder=llmpeg" in url
            assert "type=output" in url
            return Response(png_bytes())
        if url.endswith("/free"):
            assert isinstance(request, urllib.request.Request)
            assert isinstance(request.data, bytes)
            assert json.loads(request.data) == {
                "unload_models": True,
                "free_memory": True,
            }
            return Response()
        raise AssertionError(url)

    monkeypatch.setattr("llmpeg.generators.comfyui_reachable", lambda *_args: True)
    monkeypatch.setattr("llmpeg.generators.urllib.request.urlopen", urlopen)
    monkeypatch.setattr("llmpeg.generators.time.sleep", lambda _seconds: None)

    assert generate_comfyui(" cat ", 1024, 42, "http://comfy.test/", 30) == png_bytes()
    workflow = submitted["prompt"]
    assert workflow["5"]["inputs"]["prompt"] == "cat"
    assert workflow["5"]["inputs"]["resolution"] == 1024
    assert workflow["6"]["inputs"]["seed"] == 42
    assert calls == [
        "http://comfy.test/prompt",
        "http://comfy.test/history/job-1",
        "http://comfy.test/history/job-1",
        "http://comfy.test/view?filename=image.png&subfolder=llmpeg&type=output",
        "http://comfy.test/free",
    ]


@pytest.mark.parametrize(
    ("prompt", "resolution", "seed", "timeout", "poll_interval", "message"),
    [
        (" ", 1024, 42, 5, 1, "prompt is empty"),
        ("cat", 128, 42, 5, 1, "between 256 and 1536"),
        ("cat", 2048, 42, 5, 1, "between 256 and 1536"),
        ("cat", 1000, 42, 5, 1, "divisible by 16"),
        ("cat", 1024, 42, 0, 1, "timeout must be positive"),
        ("cat", 1024, 42, 5, 0, "poll interval must be positive"),
    ],
)
def test_generate_comfyui_validates_request(
    prompt: str,
    resolution: int,
    seed: int,
    timeout: float,
    poll_interval: float,
    message: str,
) -> None:
    with pytest.raises(ArtifactError, match=message):
        generate_comfyui(prompt, resolution, seed, timeout=timeout, poll_interval=poll_interval)


def test_generate_comfyui_rejects_non_positive_overrides() -> None:
    with pytest.raises(ArtifactError, match="cfg must be positive"):
        generate_comfyui("cat", 1024, 42, cfg=0)
    with pytest.raises(ArtifactError, match="steps must be positive"):
        generate_comfyui("cat", 1024, 42, steps=0)


def test_generate_comfyui_fails_closed_when_local_service_is_down(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("llmpeg.generators.comfyui_reachable", lambda *_args: False)
    with pytest.raises(GeneratorUnavailable, match="local ComfyUI is unavailable"):
        generate_comfyui("cat", 1024, 42, "http://comfy.test", 5)


@pytest.mark.parametrize(
    ("submission", "message"),
    [({}, "prompt_id"), ({"prompt_id": 7}, "prompt_id")],
)
def test_generate_comfyui_requires_prompt_id(
    monkeypatch: pytest.MonkeyPatch, submission: object, message: str
) -> None:
    monkeypatch.setattr("llmpeg.generators.comfyui_reachable", lambda *_args: True)
    monkeypatch.setattr("llmpeg.generators._request_json", lambda *_args: submission)
    with pytest.raises(ArtifactError, match=message):
        generate_comfyui("cat", 1024, 42, timeout=5)


@pytest.mark.parametrize(
    ("history", "message"),
    [
        ([], "history response root"),
        ({"job-1": "bad"}, "history entry"),
        ({"job-1": {"outputs": {}}}, "produced no image"),
        ({"job-1": {"outputs": {"8": {"images": [{"filename": "x"}]}}}}, "no image"),
        (
            {
                "job-1": {
                    "status": {
                        "status_str": "error",
                        "messages": [["execution_error", {"exception_message": "model missing"}]],
                    }
                }
            },
            "model missing",
        ),
    ],
)
def test_generate_comfyui_rejects_bad_history(
    monkeypatch: pytest.MonkeyPatch, history: object, message: str
) -> None:
    responses = iter([{"prompt_id": "job-1"}, history])
    monkeypatch.setattr("llmpeg.generators.comfyui_reachable", lambda *_args: True)
    monkeypatch.setattr("llmpeg.generators._request_json", lambda *_args: next(responses))
    with pytest.raises(ArtifactError, match=message):
        generate_comfyui("cat", 1024, 42, timeout=5)


@pytest.mark.parametrize(("payload", "message"), [(b"bad", "invalid image")])
def test_generate_comfyui_rejects_bad_image(
    monkeypatch: pytest.MonkeyPatch, payload: bytes, message: str
) -> None:
    responses = iter([{"prompt_id": "job-1"}, image_result()])
    monkeypatch.setattr("llmpeg.generators.comfyui_reachable", lambda *_args: True)
    monkeypatch.setattr("llmpeg.generators._request_json", lambda *_args: next(responses))
    monkeypatch.setattr("llmpeg.generators._request_bytes", lambda *_args: payload)
    with pytest.raises(ArtifactError, match=message):
        generate_comfyui("cat", 1024, 42, timeout=5)


def test_image_fetch_has_a_size_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmpeg.generators.MAX_GENERATED_IMAGE_BYTES", 8)
    monkeypatch.setattr(
        "llmpeg.generators.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(b"x" * 9),
    )
    with pytest.raises(ArtifactError, match="exceeds"):
        _request_bytes("http://comfy.test/view", 5)


def test_request_json_reports_comfyui_http_message(monkeypatch: pytest.MonkeyPatch) -> None:
    error = urllib.error.HTTPError(
        "http://comfy.test/prompt",
        400,
        "Bad Request",
        Message(),
        Response(b'{"error":{"message":"unknown node"}}'),
    )
    monkeypatch.setattr(
        "llmpeg.generators.urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    with pytest.raises(ArtifactError, match=r"400.*unknown node"):
        _request_json("http://comfy.test/prompt", {}, 5)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        (b"plain failure", "plain failure"),
        (b'{"error":{"type":"missing_model"}}', "missing_model"),
        (b'{"unexpected":true}', '{"unexpected":true}'),
    ],
)
def test_http_error_detail_handles_comfyui_error_shapes(body: bytes, message: str) -> None:
    error = urllib.error.HTTPError(
        "http://comfy.test/prompt", 400, "Bad Request", Message(), Response(body)
    )
    assert message in _http_error_detail(error)


def test_request_helpers_report_transport_and_json_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "llmpeg.generators.urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )
    with pytest.raises(ArtifactError, match=r"request failed.*offline"):
        _request_json("http://comfy.test/history/job", None, 5)
    with pytest.raises(ArtifactError, match=r"image fetch failed.*offline"):
        _request_bytes("http://comfy.test/view", 5)

    monkeypatch.setattr(
        "llmpeg.generators.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(b"not-json"),
    )
    with pytest.raises(ArtifactError, match="request failed"):
        _request_json("http://comfy.test/history/job", None, 5)


def test_request_json_bounds_response_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmpeg.generators.MAX_COMFYUI_JSON_BYTES", 4)
    monkeypatch.setattr(
        "llmpeg.generators.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(b'{"ok":true}'),
    )
    with pytest.raises(ArtifactError, match="JSON response exceeds 4 bytes"):
        _request_json("http://comfy.test/history/job", None, 5)


def test_image_fetch_reports_http_detail(monkeypatch: pytest.MonkeyPatch) -> None:
    error = urllib.error.HTTPError(
        "http://comfy.test/view",
        500,
        "Internal Server Error",
        Message(),
        Response(b"generation failed"),
    )
    monkeypatch.setattr(
        "llmpeg.generators.urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(error),
    )
    with pytest.raises(ArtifactError, match=r"500.*generation failed"):
        _request_bytes("http://comfy.test/view", 5)


def test_execution_error_and_image_parsing_fail_closed() -> None:
    with pytest.raises(ArtifactError, match=r"workflow failed$"):
        _raise_execution_error(
            {
                "status": {
                    "status_str": "error",
                    "messages": ["bad", ["other", {}], ["execution_error", []]],
                }
            }
        )
    with pytest.raises(ArtifactError, match="TypeError"):
        _raise_execution_error(
            {
                "status": {
                    "status_str": "error",
                    "messages": [["execution_error", {"exception_type": "TypeError"}]],
                }
            }
        )

    with pytest.raises(ArtifactError, match="produced no image"):
        _first_image(
            {
                "outputs": {
                    "bad": [],
                    "missing": {},
                    "mixed": {"images": [None, {"filename": "x"}]},
                }
            }
        )


def test_remaining_timeout_reports_the_total_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("llmpeg.generators.time.monotonic", lambda: 10.0)
    assert _remaining_timeout(12.5, 30) == 2.5
    with pytest.raises(ArtifactError, match="timed out after 30s"):
        _remaining_timeout(10.0, 30)


def test_workflow_resource_is_checked_in() -> None:
    workflow = Path(__file__).parent.parent / "src/llmpeg/workflows/qwen_image_2_1_t2i_api.json"
    assert workflow.is_file()

from __future__ import annotations

import io
import json
import urllib.error
from email.message import Message
from typing import Any
from unittest.mock import patch

import pytest

from llmpeg.artifact import ArtifactError, FidelityProfile
from llmpeg.providers import OllamaVisionProvider, _vision_instruction


class Response:
    def __init__(self, payload: Any) -> None:
        self.payload = payload

    def __enter__(self) -> Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, _amount: int = -1) -> bytes:
        return json.dumps(self.payload).encode()


def test_ollama_provider_request_and_fenced_json(description: dict[str, Any]) -> None:
    response = Response({"message": {"content": f"```json\n{json.dumps(description)}\n```"}})
    with patch("urllib.request.urlopen", return_value=response) as opened:
        provider = OllamaVisionProvider("http://vision.test/", timeout=12)
        assert provider.describe(b"image", "image/png", FidelityProfile.DETAILED) == description
    request = opened.call_args.args[0]
    body = json.loads(request.data)
    assert request.full_url == "http://vision.test/api/chat"
    assert body["messages"][0]["images"] == ["aW1hZ2U="]
    assert "/no_think" in body["messages"][0]["content"]
    assert body["think"] is False
    assert body["keep_alive"] == 0
    assert body["options"]["num_ctx"] == 8192
    assert body["format"]["properties"]["palette"]["maxItems"] == 8
    assert body["format"]["properties"]["generation_prompt"]["maxLength"] < 2000
    assert provider.provenance.model == "qwen3.5:4b"


@pytest.mark.parametrize(
    ("payload", "message"),
    [
        ({"error": "model missing"}, "provider error"),
        ({"done_reason": "length", "message": {"content": ""}}, "empty content"),
        ({"message": {"content": "not json"}}, "invalid JSON"),
        ({"message": {"content": "[]"}}, "JSON object"),
        ({"message": "wrong"}, "message must"),
        ({"message": {"content": 12}}, "content must"),
        ({"message": {"content": "", "thinking": 12}}, "thinking must"),
        ([], "response root"),
    ],
)
def test_ollama_provider_rejects_bad_responses(payload: Any, message: str) -> None:
    with (
        patch("urllib.request.urlopen", return_value=Response(payload)),
        pytest.raises(ArtifactError, match=message),
    ):
        OllamaVisionProvider("http://vision.test").describe(
            b"image", "image/png", FidelityProfile.GIST
        )


def test_ollama_provider_wraps_network_error() -> None:
    with (
        patch("urllib.request.urlopen", side_effect=OSError("offline")),
        pytest.raises(ArtifactError, match="request failed"),
    ):
        OllamaVisionProvider("http://vision.test").describe(
            b"image", "image/png", FidelityProfile.GIST
        )


def test_ollama_http_error_includes_response_detail() -> None:
    error = urllib.error.HTTPError(
        "http://vision.test/api/chat",
        400,
        "Bad Request",
        Message(),
        io.BytesIO(b'{"error":"unsupported schema"}'),
    )
    with (
        patch("urllib.request.urlopen", side_effect=error),
        pytest.raises(ArtifactError, match=r"400.*unsupported schema"),
    ):
        OllamaVisionProvider("http://vision.test").describe(
            b"image", "image/png", FidelityProfile.GIST
        )


def test_ollama_bounds_response_bytes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmpeg.providers.MAX_VISION_RESPONSE_BYTES", 4)
    with (
        patch("urllib.request.urlopen", return_value=Response({"message": {"content": "x"}})),
        pytest.raises(ArtifactError, match="response exceeds 4 bytes"),
    ):
        OllamaVisionProvider("http://vision.test").describe(
            b"image", "image/png", FidelityProfile.GIST
        )


def test_profile_instructions_differ() -> None:
    assert "subjects" in _vision_instruction(FidelityProfile.GIST)
    assert "spatial" in _vision_instruction(FidelityProfile.BALANCED)
    assert "verbatim" in _vision_instruction(FidelityProfile.DETAILED)
    assert "visual identity" in _vision_instruction(FidelityProfile.DETAILED)
    assert "percentages" in _vision_instruction(FidelityProfile.DETAILED)


def test_instruction_fixes_region_format_and_leaves_tone_to_pixels() -> None:
    instruction = _vision_instruction(FidelityProfile.DETAILED)
    assert 'exactly "x A-B%, y C-D%"' in instruction
    assert "measured from the pixels separately" in instruction
    assert "never mood, symbolism, or intent" in instruction


def test_ollama_accepts_valid_json_from_thinking_field(description: dict[str, Any]) -> None:
    response = Response({"message": {"content": "", "thinking": json.dumps(description)}})
    with patch("urllib.request.urlopen", return_value=response):
        assert (
            OllamaVisionProvider("http://vision.test").describe(
                b"image", "image/png", FidelityProfile.DETAILED
            )
            == description
        )


def test_extra_instruction_is_appended_without_changing_the_base() -> None:
    base = _vision_instruction(FidelityProfile.BALANCED)
    focused = _vision_instruction(FidelityProfile.BALANCED, "  Count every visible person.  ")
    assert "Extra focus" not in base
    assert focused.startswith(base)
    assert focused.endswith("Count every visible person.")
    assert _vision_instruction(FidelityProfile.BALANCED, "   ") == base

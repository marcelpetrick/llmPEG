from __future__ import annotations

import json
from typing import Any
from unittest.mock import patch

import pytest

from promptpress.artifact import ArtifactError, FidelityProfile
from promptpress.providers import OllamaVisionProvider, _vision_instruction


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
    assert body["format"]["properties"]["palette"]["maxItems"] == 8
    assert provider.provenance.model == "qwen3-vl:32b-ctx49k"


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


def test_profile_instructions_differ() -> None:
    assert "subjects" in _vision_instruction(FidelityProfile.GIST)
    assert "spatial" in _vision_instruction(FidelityProfile.BALANCED)
    assert "verbatim" in _vision_instruction(FidelityProfile.DETAILED)
    assert "visual identity" in _vision_instruction(FidelityProfile.DETAILED)
    assert "percentages" in _vision_instruction(FidelityProfile.DETAILED)


def test_ollama_accepts_valid_json_from_thinking_field(description: dict[str, Any]) -> None:
    response = Response({"message": {"content": "", "thinking": json.dumps(description)}})
    with patch("urllib.request.urlopen", return_value=response):
        assert (
            OllamaVisionProvider("http://vision.test").describe(
                b"image", "image/png", FidelityProfile.DETAILED
            )
            == description
        )

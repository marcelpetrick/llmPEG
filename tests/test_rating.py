from __future__ import annotations

import io
import json
import urllib.error
import urllib.request
from typing import Any

import pytest
from PIL import Image

from llmpeg.artifact import ArtifactError
from llmpeg.rating import (
    OllamaSimilarityRater,
    _ollama_content,
    _prepare_image,
    _string_tuple,
)


class Response(io.BytesIO):
    def __enter__(self) -> Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def image_bytes(color: str = "navy") -> bytes:
    output = io.BytesIO()
    Image.new("RGB", (64, 48), color).save(output, format="PNG")
    return output.getvalue()


def verdict(score: int, *, difference: str = "none") -> dict[str, Any]:
    return {
        "subject_fidelity": score,
        "identity_fidelity": score,
        "composition_fidelity": score,
        "text_fidelity": score,
        "style_fidelity": score,
        "differences": [difference],
        "prompt_improvements": [f"improve {difference}"],
    }


def ollama_response(value: object, *, thinking: bool = False) -> bytes:
    message = (
        {"content": "", "thinking": json.dumps(value)}
        if thinking
        else {"content": json.dumps(value)}
    )
    return json.dumps({"message": message}).encode()


def test_similarity_rater_reports_medians_spread_and_trials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = iter(
        [
            verdict(80, difference="hat changed"),
            verdict(70, difference="hat changed"),
            verdict(40, difference="pose changed"),
        ]
    )
    requests: list[dict[str, Any]] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> Response:
        assert timeout == 12
        assert isinstance(request.data, bytes)
        requests.append(json.loads(request.data))
        return Response(ollama_response(next(responses)))

    monkeypatch.setattr("llmpeg.rating.urllib.request.urlopen", urlopen)
    rating = OllamaSimilarityRater("http://vision.test", "qwen", 12, repeats=3).rate(
        image_bytes(),
        image_bytes("purple"),
        "draw the same cat",
        ("CAT",),
    )

    assert rating.semantic_median == 70.0
    assert set(rating.semantic_medians.values()) == {70.0}
    assert set(rating.semantic_spreads.values()) == {40}
    assert rating.unstable is True
    assert rating.verdict in {"partial", "poor"}
    assert rating.differences == ("hat changed", "pose changed")
    assert rating.prompt_improvements == ("improve hat changed", "improve pose changed")
    assert [trial.seed for trial in rating.trials] == [42, 43, 44]
    assert rating.to_dict()["method"].endswith("not calibrated to human ratings")
    assert len(requests) == 3
    assert requests[0]["model"] == "qwen"
    assert requests[0]["options"]["temperature"] == 0.0
    assert requests[0]["options"]["seed"] == 42
    assert [request["keep_alive"] for request in requests] == ["30m", "30m", 0]
    assert len(requests[0]["messages"][0]["images"]) == 2
    assert "draw the same cat" in requests[0]["messages"][0]["content"]
    assert "CAT" in requests[0]["messages"][0]["content"]


@pytest.mark.parametrize("repeats", [0, 6])
def test_similarity_rater_bounds_repeats(repeats: int) -> None:
    with pytest.raises(ArtifactError, match="rating repeats"):
        OllamaSimilarityRater(repeats=repeats).rate(image_bytes(), image_bytes(), "cat")


@pytest.mark.parametrize(
    ("payload", "message"),
    [(b"", "empty"), (b"not image", "not a supported image")],
)
def test_prepare_image_rejects_invalid_input(payload: bytes, message: str) -> None:
    with pytest.raises(ArtifactError, match=message):
        _prepare_image(payload, "source")


def test_prepare_image_bounds_bytes_and_pixels(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("llmpeg.rating.MAX_RATING_IMAGE_BYTES", 2)
    with pytest.raises(ArtifactError, match="bytes; limit"):
        _prepare_image(image_bytes(), "source")

    monkeypatch.setattr("llmpeg.rating.MAX_RATING_IMAGE_BYTES", 1_000_000)
    monkeypatch.setattr("llmpeg.rating.DEFAULT_MAX_IMAGE_PIXELS", 10)
    with pytest.raises(ArtifactError, match="pixels; limit"):
        _prepare_image(image_bytes(), "source")


def test_similarity_rater_reports_network_and_schema_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "llmpeg.rating.urllib.request.urlopen",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(urllib.error.URLError("offline")),
    )
    with pytest.raises(ArtifactError, match=r"request failed.*offline"):
        OllamaSimilarityRater(repeats=1).rate(image_bytes(), image_bytes(), "cat")

    monkeypatch.setattr(
        "llmpeg.rating.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(ollama_response({"subject_fidelity": 10})),
    )
    with pytest.raises(ArtifactError, match="violates its schema"):
        OllamaSimilarityRater(repeats=1).rate(image_bytes(), image_bytes(), "cat")

    bad = verdict(101)
    monkeypatch.setattr(
        "llmpeg.rating.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(ollama_response(bad)),
    )
    with pytest.raises(ArtifactError, match="between 0 and 100"):
        OllamaSimilarityRater(repeats=1).rate(image_bytes(), image_bytes(), "cat")


def test_ollama_content_accepts_fenced_thinking_and_rejects_bad_shapes() -> None:
    value = verdict(80)
    raw = {"message": {"content": "", "thinking": f"```json\n{json.dumps(value)}\n```"}}
    assert _ollama_content(raw, "rater") == value

    payloads: tuple[object, ...] = (
        [],
        {"error": "broken"},
        {"message": []},
        {"message": {"content": []}},
        {"message": {"content": "not json", "thinking": ""}},
        {"message": {"content": "[]", "thinking": ""}},
    )
    for payload in payloads:
        with pytest.raises(ArtifactError):
            _ollama_content(payload, "rater")


def test_string_tuple_validates_and_strips() -> None:
    assert _string_tuple([" one ", ""], "items") == ("one",)
    with pytest.raises(ArtifactError, match="string array"):
        _string_tuple([1], "items")


@pytest.mark.parametrize(
    ("preferences", "accepted", "consistent", "logical"),
    [
        (("B", "A"), True, True, ("challenger", "challenger")),
        (("A", "B"), False, True, ("baseline", "baseline")),
        (("B", "B"), False, False, ("challenger", "baseline")),
        (("tie", "A"), False, False, ("tie", "challenger")),
    ],
)
def test_pairwise_rating_reverses_candidate_order(
    monkeypatch: pytest.MonkeyPatch,
    preferences: tuple[str, str],
    accepted: bool,
    consistent: bool,
    logical: tuple[str, str],
) -> None:
    responses = iter(preferences)
    requests: list[dict[str, Any]] = []

    def urlopen(request: urllib.request.Request, timeout: float) -> Response:
        del timeout
        assert isinstance(request.data, bytes)
        requests.append(json.loads(request.data))
        return Response(ollama_response({"preferred": next(responses), "reason": "closer"}))

    monkeypatch.setattr("llmpeg.rating.urllib.request.urlopen", urlopen)
    result = OllamaSimilarityRater(repeats=1).compare_pairwise(
        image_bytes(),
        image_bytes("navy"),
        image_bytes("purple"),
    )

    assert result.accepted is accepted
    assert result.consistent is consistent
    assert tuple(trial.preferred for trial in result.trials) == logical
    assert result.trials[0].order == ("baseline", "challenger")
    assert result.trials[1].order == ("challenger", "baseline")
    assert len(requests[0]["messages"][0]["images"]) == 3
    assert "Judge the pixels only" in requests[0]["messages"][0]["content"]
    assert "candidate prompt" in requests[1]["messages"][0]["content"]
    assert [request["keep_alive"] for request in requests] == ["30m", 0]
    assert result.to_dict()["accepted"] is accepted


def test_pairwise_rating_rejects_bad_schema(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "llmpeg.rating.urllib.request.urlopen",
        lambda *_args, **_kwargs: Response(ollama_response({"preferred": "C", "reason": 1})),
    )
    with pytest.raises(ArtifactError, match="violates its schema"):
        OllamaSimilarityRater(repeats=1).compare_pairwise(
            image_bytes(), image_bytes(), image_bytes()
        )

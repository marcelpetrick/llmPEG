"""Local Qwen-Image-2.1 generation through ComfyUI's HTTP API."""

from __future__ import annotations

import copy
import io
import json
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from importlib import resources
from typing import Any

from PIL import Image

from llmpeg.artifact import ArtifactError

DEFAULT_COMFYUI_HOST = "http://127.0.0.1:8188"
DEFAULT_GENERATION_TIMEOUT = 1200.0
DEFAULT_QWEN_RESOLUTION = 1024
DEFAULT_QWEN_SEED = 42
MIN_QWEN_RESOLUTION = 256
MAX_QWEN_RESOLUTION = 1536
MAX_GENERATED_IMAGE_BYTES = 100 * 1024 * 1024
MAX_COMFYUI_JSON_BYTES = 1024 * 1024
POLL_INTERVAL_SECONDS = 1.0
WORKFLOW_RESOURCE = "workflows/qwen_image_2_1_t2i_api.json"


class GeneratorUnavailable(ArtifactError):
    """Raised when the required local ComfyUI service cannot be reached."""


def comfyui_reachable(host: str, timeout: float) -> bool:
    """Return whether ComfyUI answers its lightweight health endpoint."""
    try:
        with urllib.request.urlopen(host.rstrip("/") + "/system_stats", timeout=min(timeout, 2.0)):
            return True
    except OSError, urllib.error.URLError:
        return False


def generate_comfyui(
    prompt: str,
    resolution: int,
    seed: int,
    host: str = DEFAULT_COMFYUI_HOST,
    timeout: float = DEFAULT_GENERATION_TIMEOUT,
    *,
    poll_interval: float = POLL_INTERVAL_SECONDS,
) -> bytes:
    """Render one square image with the bundled Qwen-Image-2.1 ComfyUI workflow."""
    prompt = prompt.strip()
    if not prompt:
        raise ArtifactError("generation prompt is empty")
    if not MIN_QWEN_RESOLUTION <= resolution <= MAX_QWEN_RESOLUTION:
        raise ArtifactError(
            f"resolution must be between {MIN_QWEN_RESOLUTION} and {MAX_QWEN_RESOLUTION}"
        )
    if resolution % 16:
        raise ArtifactError("resolution must be divisible by 16")
    if timeout <= 0:
        raise ArtifactError("generation timeout must be positive")
    if poll_interval <= 0:
        raise ArtifactError("ComfyUI poll interval must be positive")

    base = host.rstrip("/")
    if not comfyui_reachable(base, timeout):
        raise GeneratorUnavailable(f"local ComfyUI is unavailable at {base}")

    workflow = _qwen_workflow(prompt, resolution, seed)
    deadline = time.monotonic() + timeout
    submitted = _request_json(
        base + "/prompt",
        {"prompt": workflow},
        _remaining_timeout(deadline, timeout),
    )
    if not isinstance(submitted, dict) or not isinstance(submitted.get("prompt_id"), str):
        raise ArtifactError("ComfyUI submission did not return a prompt_id")
    prompt_id = submitted["prompt_id"]

    result = _wait_for_result(base, prompt_id, deadline, timeout, poll_interval)
    image = _first_image(result)
    query = urllib.parse.urlencode(image)
    data = _request_bytes(
        f"{base}/view?{query}",
        _remaining_timeout(deadline, timeout),
    )
    validated = _validated_image(data, "ComfyUI/Qwen-Image-2.1")
    _release_models(base, _remaining_timeout(deadline, timeout))
    return validated


def _qwen_workflow(prompt: str, resolution: int, seed: int) -> dict[str, Any]:
    """Return an isolated workflow with only request-specific values changed."""
    resource = resources.files("llmpeg").joinpath(WORKFLOW_RESOURCE)
    try:
        with resource.open("r", encoding="utf-8") as stream:
            loaded = json.load(stream)
    except (OSError, json.JSONDecodeError) as error:  # pragma: no cover - broken installation
        raise ArtifactError(f"bundled Qwen workflow is unreadable: {error}") from error
    if not isinstance(loaded, dict):  # pragma: no cover - guarded by a workflow structure test
        raise ArtifactError("bundled Qwen workflow root must be a JSON object")
    workflow: dict[str, Any] = copy.deepcopy(loaded)
    try:
        workflow["5"]["inputs"]["prompt"] = prompt
        workflow["5"]["inputs"]["resolution"] = resolution
        workflow["6"]["inputs"]["seed"] = seed
        workflow["8"]["inputs"]["filename_prefix"] = f"llmpeg/{uuid.uuid4().hex}"
    except (KeyError, TypeError) as error:  # pragma: no cover - structure is unit-tested
        raise ArtifactError("bundled Qwen workflow has an unexpected structure") from error
    return workflow


def _wait_for_result(
    host: str,
    prompt_id: str,
    deadline: float,
    timeout: float,
    poll_interval: float,
) -> dict[str, Any]:
    while True:
        history = _request_json(
            f"{host}/history/{urllib.parse.quote(prompt_id, safe='')}",
            None,
            _remaining_timeout(deadline, timeout),
        )
        if not isinstance(history, dict):
            raise ArtifactError("ComfyUI history response root must be a JSON object")
        result = history.get(prompt_id)
        if result is not None:
            if not isinstance(result, dict):
                raise ArtifactError("ComfyUI history entry must be a JSON object")
            _raise_execution_error(result)
            return result
        time.sleep(min(poll_interval, _remaining_timeout(deadline, timeout)))


def _raise_execution_error(result: dict[str, Any]) -> None:
    status = result.get("status")
    if not isinstance(status, dict) or status.get("status_str") != "error":
        return
    detail = ""
    messages = status.get("messages")
    if isinstance(messages, list):
        for message in reversed(messages):
            if not isinstance(message, list) or len(message) != 2:
                continue
            name, payload = message
            if name != "execution_error" or not isinstance(payload, dict):
                continue
            value = payload.get("exception_message") or payload.get("exception_type")
            if isinstance(value, str):
                detail = value.strip()
                break
    raise ArtifactError(f"ComfyUI Qwen workflow failed{f': {detail}' if detail else ''}")


def _first_image(result: dict[str, Any]) -> dict[str, str]:
    outputs = result.get("outputs")
    if not isinstance(outputs, dict):
        raise ArtifactError("ComfyUI Qwen workflow produced no image")
    for output in outputs.values():
        if not isinstance(output, dict):
            continue
        images = output.get("images")
        if not isinstance(images, list):
            continue
        for image in images:
            if not isinstance(image, dict):
                continue
            fields = {name: image.get(name) for name in ("filename", "subfolder", "type")}
            if all(isinstance(value, str) for value in fields.values()):
                return {name: str(value) for name, value in fields.items()}
    raise ArtifactError("ComfyUI Qwen workflow produced no image")


def _request_json(url: str, payload: object | None, timeout: float) -> object:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {} if data is None else {"Content-Type": "application/json"}
    request = urllib.request.Request(url, data=data, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = response.read(MAX_COMFYUI_JSON_BYTES + 1)
        if len(data) > MAX_COMFYUI_JSON_BYTES:
            raise ArtifactError(f"ComfyUI JSON response exceeds {MAX_COMFYUI_JSON_BYTES} bytes")
        return json.loads(data)
    except urllib.error.HTTPError as error:
        detail = _http_error_detail(error)
        raise ArtifactError(f"ComfyUI request failed ({error.code}){detail}") from error
    except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
        raise ArtifactError(f"ComfyUI request failed: {error}") from error


def _request_bytes(url: str, timeout: float) -> bytes:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            data = response.read(MAX_GENERATED_IMAGE_BYTES + 1)
    except urllib.error.HTTPError as error:
        detail = _http_error_detail(error)
        raise ArtifactError(f"ComfyUI image fetch failed ({error.code}){detail}") from error
    except (OSError, urllib.error.URLError) as error:
        raise ArtifactError(f"ComfyUI image fetch failed: {error}") from error
    if len(data) > MAX_GENERATED_IMAGE_BYTES:
        raise ArtifactError(f"ComfyUI image exceeds {MAX_GENERATED_IMAGE_BYTES} bytes")
    return bytes(data)


def _release_models(host: str, timeout: float) -> None:
    """Release ComfyUI's GPU allocation for the local Ollama vision/rating phase."""
    request = urllib.request.Request(
        host.rstrip("/") + "/free",
        data=json.dumps({"unload_models": True, "free_memory": True}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout):
            return
    except urllib.error.HTTPError as error:
        detail = _http_error_detail(error)
        raise ArtifactError(f"ComfyUI model release failed ({error.code}){detail}") from error
    except (OSError, urllib.error.URLError) as error:
        raise ArtifactError(f"ComfyUI model release failed: {error}") from error


def _http_error_detail(error: urllib.error.HTTPError) -> str:
    try:
        body = error.read(4096).decode("utf-8", errors="replace").strip()
    except OSError:
        return ""
    if not body:
        return ""
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return f": {body}"
    if isinstance(payload, dict):
        detail = payload.get("error")
        if isinstance(detail, dict):
            detail = detail.get("message") or detail.get("type")
        if isinstance(detail, str) and detail.strip():
            return f": {detail.strip()}"
    return f": {body}"


def _remaining_timeout(deadline: float, timeout: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ArtifactError(f"ComfyUI timed out after {timeout:.0f}s")
    return remaining


def _validated_image(data: bytes, provider: str) -> bytes:
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
    except (OSError, SyntaxError) as error:
        raise ArtifactError(f"{provider} produced an invalid image") from error
    return data

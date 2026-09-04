"""Tiny local web UI for the llmPEG round trip: drop an image, read the prompt, regenerate.

The page itself is static HTML. This backend exists for three reasons a browser cannot
handle alone:

* the Ollama vision endpoint usually lives on another machine on the LAN, which a page
  served from localhost cannot call directly (CORS, and mixed content over HTTPS);
* downscaling is done with Pillow's LANCZOS filter, which is better than a canvas resize;
* image generation is proxied so the same code path serves both the free hosted generator
  and a local Stable Diffusion server.

Nothing here is hardened. It binds to 127.0.0.1, it has no authentication, and it is a
prototype for one person on one laptop. Do not expose it.

Usage:
    export OLLAMA_VISION_HOST=http://your-ollama-host:11434
    uv run python prototypeWebUI/server.py
    # then open http://127.0.0.1:8000
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from llmpeg.artifact import ArtifactError, FidelityProfile
from llmpeg.encoder import encode_image, render_generation_prompt
from llmpeg.providers import OllamaVisionProvider

HERE = Path(__file__).resolve().parent
INDEX = HERE / "index.html"

MAX_UPLOAD_BYTES = 40 * 1024 * 1024
MAX_EDGE = 1536
JPEG_QUALITY = 92
MAX_PROMPT_CHARS = 20_000
MIN_GENERATION_EDGE = 256
MAX_GENERATION_EDGE = 1536
FILE_ORIGIN = "null"

POLLINATIONS = "https://image.pollinations.ai/prompt/"


class Config:
    """Runtime configuration read once from the environment."""

    def __init__(self) -> None:
        self.vision_host = os.environ.get("OLLAMA_VISION_HOST", "")
        self.model = os.environ.get("LLMPEG_MODEL", "qwen3-vl:32b-ctx49k")
        self.generator = os.environ.get("LLMPEG_GENERATOR", "pollinations")
        self.sd_host = os.environ.get("LLMPEG_SD_HOST", "http://127.0.0.1:7860")
        self.timeout = float(os.environ.get("LLMPEG_TIMEOUT", "600"))


CONFIG = Config()


def downscale(raw: bytes, max_edge: int = MAX_EDGE) -> tuple[bytes, dict[str, Any]]:
    """Flatten to RGB and shrink the long edge, returning JPEG bytes and what changed."""
    with Image.open(io.BytesIO(raw)) as opened:
        original = (opened.width, opened.height)
        image = opened.convert("RGB")
        if max(image.size) > max_edge:
            image.thumbnail((max_edge, max_edge), Image.Resampling.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=JPEG_QUALITY)
        scaled = image.size
    data = buffer.getvalue()
    return data, {
        "original_width": original[0],
        "original_height": original[1],
        "encoded_width": scaled[0],
        "encoded_height": scaled[1],
        "was_downscaled": original != scaled,
        "upload_bytes": len(raw),
        "encoded_bytes": len(data),
    }


def encode(raw: bytes, profile: FidelityProfile) -> dict[str, Any]:
    """Downscale, hand the image to the vision model, and render its generation prompt."""
    if not CONFIG.vision_host:
        raise ArtifactError("OLLAMA_VISION_HOST is not set, so no vision model can be reached")
    prepared, info = downscale(raw)
    provider = OllamaVisionProvider(CONFIG.vision_host, CONFIG.model, CONFIG.timeout)
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "upload.jpg"
        path.write_bytes(prepared)
        artifact = encode_image(path, provider, profile)
    artifact_bytes = len(artifact.to_bytes())
    return {
        **info,
        "profile": profile.value,
        "model": CONFIG.model,
        "summary": artifact.summary,
        "prompt": render_generation_prompt(artifact),
        "artifact": json.loads(artifact.to_bytes().decode("utf-8")),
        "artifact_bytes": artifact_bytes,
        "ratio": round(info["encoded_bytes"] / artifact_bytes, 1),
    }


def generate_pollinations(prompt: str, width: int, height: int, seed: int) -> bytes:
    """Fetch one image from the free hosted generator. The prompt leaves this machine."""
    query = urllib.parse.urlencode(
        {"width": width, "height": height, "seed": seed, "nologo": "true"}
    )
    url = f"{POLLINATIONS}{urllib.parse.quote(prompt, safe='')}?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "llmPEG-prototype/0.1"})
    with urllib.request.urlopen(request, timeout=CONFIG.timeout) as response:
        return bytes(response.read())


def generate_local(prompt: str, width: int, height: int, seed: int) -> bytes:
    """Call a local Automatic1111-compatible `/sdapi/v1/txt2img` server.

    Untested in the environment this prototype was written in: no local Stable Diffusion
    server was reachable. Treat it as a starting point rather than a working path.
    """
    payload = json.dumps(
        {
            "prompt": prompt,
            "width": width,
            "height": height,
            "seed": seed,
            "steps": 25,
            "sampler_name": "DPM++ 2M",
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        CONFIG.sd_host.rstrip("/") + "/sdapi/v1/txt2img",
        payload,
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=CONFIG.timeout) as response:
        body = json.load(response)
    images = body.get("images") or []
    if not images:
        raise ArtifactError("local generator returned no images")
    return base64.b64decode(images[0])


def generate_codex(prompt: str, width: int, height: int, seed: int) -> bytes:
    """Drive the Codex CLI's built-in image tool.

    Codex is an agent, not an image API: it is handed a directory containing only the
    prompt and asked to save `out.png` there. Slower and it consumes the account's quota,
    but the quality is the best of the three and the prompt never reaches a public service.
    """
    del seed  # the built-in image tool exposes no seed
    binary = shutil.which("codex")
    if binary is None:
        raise ArtifactError("the `codex` CLI is not on PATH")
    orientation = "landscape" if width > height else "portrait" if height > width else "square"
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        (work / "prompt.txt").write_text(prompt, encoding="utf-8")
        try:
            subprocess.run(
                [
                    binary,
                    "exec",
                    "--skip-git-repo-check",
                    "-C",
                    str(work),
                    "-s",
                    "workspace-write",
                    "The file prompt.txt in this directory contains an image-generation prompt. "
                    "Generate exactly that image with your built-in image generation tool and "
                    "save it as out.png in this directory. Use the prompt as written; add no "
                    f"subject, text or decoration of your own. Orientation must be {orientation}. "
                    "When finished reply with only: DONE",
                ],
                check=True,
                capture_output=True,
                timeout=CONFIG.timeout,
            )
        except subprocess.TimeoutExpired as error:
            raise ArtifactError(f"codex timed out after {CONFIG.timeout:.0f}s") from error
        except subprocess.CalledProcessError as error:
            tail = (error.stderr or b"").decode("utf-8", "replace")[-300:]
            raise ArtifactError(f"codex failed: {tail}") from error
        produced = work / "out.png"
        if not produced.is_file():
            raise ArtifactError("codex produced no image")
        return produced.read_bytes()


def image_media_type(data: bytes) -> str:
    """Sniff the format, since the three generators do not agree on one."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


def generate(prompt: str, width: int, height: int, seed: int) -> bytes:
    """Dispatch to the configured generator."""
    if CONFIG.generator == "local":
        return generate_local(prompt, width, height, seed)
    if CONFIG.generator == "codex":
        return generate_codex(prompt, width, height, seed)
    if CONFIG.generator == "pollinations":
        return generate_pollinations(prompt, width, height, seed)
    raise ArtifactError(f"unsupported generator: {CONFIG.generator}")


def generation_request(payload: object) -> tuple[str, int, int, int]:
    """Validate and normalize an image-generation request."""
    if not isinstance(payload, dict):
        raise ArtifactError("request body must be a JSON object")
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ArtifactError("a prompt is required")
    if len(prompt) > MAX_PROMPT_CHARS:
        raise ArtifactError(f"prompt exceeds {MAX_PROMPT_CHARS} characters")
    try:
        width = int(payload.get("width", 1024))
        height = int(payload.get("height", 1024))
        seed = int(payload.get("seed", 42))
    except (TypeError, ValueError) as error:
        raise ArtifactError("width, height, and seed must be integers") from error
    if not MIN_GENERATION_EDGE <= width <= MAX_GENERATION_EDGE:
        raise ArtifactError(
            f"width must be between {MIN_GENERATION_EDGE} and {MAX_GENERATION_EDGE}"
        )
    if not MIN_GENERATION_EDGE <= height <= MAX_GENERATION_EDGE:
        raise ArtifactError(
            f"height must be between {MIN_GENERATION_EDGE} and {MAX_GENERATION_EDGE}"
        )
    return prompt, width, height, seed


class Handler(BaseHTTPRequestHandler):
    """Minimal framework-free router for the page and its API."""

    server_version = "llmPEGPrototype/0.1"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write(f"{self.address_string()} {format % args}\n")

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self.headers.get("Origin") == FILE_ORIGIN:
            self.send_header("Access-Control-Allow-Origin", FILE_ORIGIN)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, Any]) -> None:
        self._send(status, json.dumps(payload).encode("utf-8"), "application/json")

    def _body(self) -> bytes:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            raise ArtifactError("empty request body")
        if length > MAX_UPLOAD_BYTES:
            raise ArtifactError(f"upload exceeds {MAX_UPLOAD_BYTES} bytes")
        body = bytes(self.rfile.read(length))
        if len(body) != length:
            raise ArtifactError("incomplete request body")
        return body

    def do_OPTIONS(self) -> None:
        """Allow API requests from this page when it was opened through ``file://``."""
        route = urllib.parse.urlparse(self.path).path
        if not route.startswith("/api/") or self.headers.get("Origin") != FILE_ORIGIN:
            self._send_json(403, {"error": "cross-origin request not allowed"})
            return
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", FILE_ORIGIN)
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        if self.headers.get("Access-Control-Request-Private-Network") == "true":
            self.send_header("Access-Control-Allow-Private-Network", "true")
        self.send_header("Content-Length", "0")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()

    def do_GET(self) -> None:
        route = urllib.parse.urlparse(self.path).path
        if route in ("/", "/index.html"):
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
            return
        if route == "/api/config":
            self._send_json(
                200,
                {
                    "generator": CONFIG.generator,
                    "model": CONFIG.model,
                    "vision_configured": bool(CONFIG.vision_host),
                    "vision_host": CONFIG.vision_host,
                },
            )
            return
        self._send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        route = urllib.parse.urlparse(self.path).path
        try:
            if route == "/api/encode":
                query = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                name = (query.get("profile") or ["balanced"])[0]
                self._send_json(200, encode(self._body(), FidelityProfile(name)))
                return
            if route == "/api/generate":
                prompt, width, height, seed = generation_request(
                    json.loads(self._body().decode("utf-8"))
                )
                image = generate(prompt, width, height, seed)
                self._send(200, image, image_media_type(image))
                return
            self._send_json(404, {"error": "not found"})
        except ArtifactError as error:
            self._send_json(400, {"error": str(error)})
        except ValueError as error:
            self._send_json(400, {"error": f"bad request: {error}"})
        except UnidentifiedImageError:
            self._send_json(400, {"error": "uploaded data is not a supported image"})
        except (OSError, urllib.error.URLError) as error:
            self._send_json(502, {"error": f"upstream failed: {error}"})


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the llmPEG prototype web UI.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument(
        "--vision-host",
        default=CONFIG.vision_host,
        help="Ollama base URL (defaults to OLLAMA_VISION_HOST)",
    )
    args = parser.parse_args(argv)
    CONFIG.vision_host = args.vision_host.rstrip("/")

    if not CONFIG.vision_host:
        print("warning: OLLAMA_VISION_HOST is not set; encoding will fail", file=sys.stderr)
    print(f"llmPEG prototype on http://{args.host}:{args.port}  (generator: {CONFIG.generator})")
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nllmPEG prototype stopped")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

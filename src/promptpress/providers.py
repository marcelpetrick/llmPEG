"""Vision-provider boundary and Ollama implementation."""

from __future__ import annotations

import base64
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from promptpress.artifact import ArtifactError, FidelityProfile, Provenance


class VisionProvider(Protocol):
    """Anything capable of turning image bytes into structured scene data."""

    @property
    def provenance(self) -> Provenance:
        """Describe the provider settings used for encoding."""

    def describe(self, image: bytes, media_type: str, profile: FidelityProfile) -> dict[str, Any]:
        """Return structured semantic fields for an image."""


@dataclass(frozen=True)
class OllamaVisionProvider:
    """Minimal Ollama `/api/chat` client compatible with `claude-vision`."""

    host: str
    model: str = "qwen3-vl:32b-ctx49k"
    timeout: float = 600.0
    seed: int = 42
    temperature: float = 0.0

    @property
    def provenance(self) -> Provenance:
        """Return stable request provenance."""
        return Provenance("ollama", self.model, self.seed, self.temperature)

    def describe(self, image: bytes, media_type: str, profile: FidelityProfile) -> dict[str, Any]:
        """Ask Ollama for strict JSON and normalize common fenced responses."""
        del media_type  # Ollama infers the type from image bytes.
        payload = {
            "model": self.model,
            "stream": False,
            "keep_alive": "30m",
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_predict": 4096,
            },
            "messages": [
                {
                    "role": "user",
                    "content": _vision_instruction(profile),
                    "images": [base64.b64encode(image).decode("ascii")],
                }
            ],
        }
        request = urllib.request.Request(
            self.host.rstrip("/") + "/api/chat",
            json.dumps(payload).encode("utf-8"),
            {"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                raw = json.load(response)
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as error:
            raise ArtifactError(f"vision provider request failed: {error}") from error
        if raw.get("error"):
            raise ArtifactError(f"vision provider error: {raw['error']}")
        content = (raw.get("message") or {}).get("content", "").strip()
        if not content:
            reason = raw.get("done_reason", "unknown")
            raise ArtifactError(f"vision provider returned empty content (done_reason={reason})")
        if content.startswith("```"):
            lines = content.splitlines()
            if lines[-1].strip() == "```":
                content = "\n".join(lines[1:-1])
                if content.lstrip().startswith("json"):
                    content = content.lstrip()[4:].lstrip("\n")
        try:
            result = json.loads(content)
        except json.JSONDecodeError as error:
            raise ArtifactError(f"vision provider returned invalid JSON: {error}") from error
        if not isinstance(result, dict):
            raise ArtifactError("vision provider response must be a JSON object")
        return result


def _vision_instruction(profile: FidelityProfile) -> str:
    detail = {
        FidelityProfile.GIST: "Keep only subjects, action, setting, palette, and broad layout.",
        FidelityProfile.BALANCED: (
            "Also preserve spatial relations, lighting, style, major objects, and critical text."
        ),
        FidelityProfile.DETAILED: (
            "Preserve all readable text verbatim, object attributes, approximate geometry, "
            "typography intent, and fine visual details."
        ),
    }[profile]
    return f"""/no_think
Analyze the attached image for lossy semantic reconstruction. {detail}
Return ONLY one valid JSON object with exactly these fields:
{{
  "summary": "one factual sentence",
  "generation_prompt": "standalone generator-ready visual description",
  "critical_text": ["exact visible strings worth preserving"],
  "composition": [{{
    "region": "normalized area such as top or lower-right",
    "description": "visible content"
  }}],
  "palette": ["#RRGGBB"],
  "style": "medium and visual treatment",
  "avoid": ["likely reconstruction errors to avoid"]
}}
Describe only what is visible. Do not wrap the JSON in Markdown."""

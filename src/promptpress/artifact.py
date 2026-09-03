"""Versioned, deterministic PromptPress artifact format."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import tempfile
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

SCHEMA_VERSION = 1
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class ArtifactError(ValueError):
    """Raised when an artifact is invalid or cannot be safely written."""


class FidelityProfile(StrEnum):
    """How much semantic detail an encoder should retain."""

    GIST = "gist"
    BALANCED = "balanced"
    DETAILED = "detailed"

    def budget(self, source_bytes: int) -> int:
        """Return the maximum artifact bytes for this source size."""
        if source_bytes < 1:
            raise ArtifactError("source_bytes must be positive")
        fixed, fraction = {
            self.GIST: (1024, 0.02),
            self.BALANCED: (4096, 0.05),
            self.DETAILED: (16384, 0.15),
        }[self]
        return max(fixed, math.ceil(source_bytes * fraction))


@dataclass(frozen=True)
class SourceInfo:
    """Non-image metadata retained about the source."""

    width: int
    height: int
    byte_size: int
    media_type: str
    sha256: str


@dataclass(frozen=True)
class Region:
    """A normalized named area of the original composition."""

    region: str
    description: str


@dataclass(frozen=True)
class Provenance:
    """Encoder settings needed to understand or reproduce an encoding."""

    provider: str
    model: str
    seed: int | None
    temperature: float | None


@dataclass(frozen=True)
class Artifact:
    """The portable semantic representation of an image."""

    schema_version: int
    profile: FidelityProfile
    source: SourceInfo
    summary: str
    generation_prompt: str
    critical_text: tuple[str, ...]
    composition: tuple[Region, ...]
    palette: tuple[str, ...]
    style: str
    avoid: tuple[str, ...]
    provenance: Provenance

    def validate(self) -> None:
        """Validate all invariants of the current schema."""
        if self.schema_version != SCHEMA_VERSION:
            raise ArtifactError(f"unsupported schema_version: {self.schema_version}")
        if self.source.width < 1 or self.source.height < 1 or self.source.byte_size < 1:
            raise ArtifactError("source dimensions and byte_size must be positive")
        if self.source.media_type not in {"image/jpeg", "image/png", "image/webp"}:
            raise ArtifactError(f"unsupported source media_type: {self.source.media_type}")
        if not re.fullmatch(r"[0-9a-f]{64}", self.source.sha256):
            raise ArtifactError("source sha256 must be 64 lowercase hexadecimal characters")
        for name, value in {
            "summary": self.summary,
            "generation_prompt": self.generation_prompt,
            "style": self.style,
            "provider": self.provenance.provider,
            "model": self.provenance.model,
        }.items():
            if not value.strip():
                raise ArtifactError(f"{name} must not be empty")
        if any(not item.strip() for item in (*self.critical_text, *self.avoid)):
            raise ArtifactError("critical_text and avoid entries must not be empty")
        if any(
            not region.region.strip() or not region.description.strip()
            for region in self.composition
        ):
            raise ArtifactError("composition regions and descriptions must not be empty")
        if any(not HEX_COLOR.fullmatch(color) for color in self.palette):
            raise ArtifactError("palette entries must use #RRGGBB")

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready representation."""
        self.validate()
        data = asdict(self)
        data["profile"] = self.profile.value
        return data

    def to_bytes(self) -> bytes:
        """Serialize to canonical compact UTF-8 JSON."""
        return json.dumps(
            self.to_dict(), ensure_ascii=False, separators=(",", ":"), sort_keys=True
        ).encode("utf-8")

    def enforce_budget(self) -> None:
        """Raise when the canonical artifact exceeds its profile's size budget."""
        actual = len(self.to_bytes())
        budget = self.profile.budget(self.source.byte_size)
        if actual > budget:
            raise ArtifactError(
                f"artifact is {actual} bytes; {self.profile.value} budget is {budget} bytes"
            )

    def write(self, path: Path, *, overwrite: bool = False) -> None:
        """Atomically write an artifact without overwriting by default."""
        self.enforce_budget()
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not overwrite:
            raise ArtifactError(f"refusing to overwrite existing file: {path}")
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(self.to_bytes())
                stream.flush()
                os.fsync(stream.fileno())
            if path.exists() and not overwrite:
                raise ArtifactError(f"refusing to overwrite existing file: {path}")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Parse and validate an artifact dictionary."""
        try:
            required = {
                "schema_version",
                "profile",
                "source",
                "summary",
                "generation_prompt",
                "critical_text",
                "composition",
                "palette",
                "style",
                "avoid",
                "provenance",
            }
            extra = set(data) - required
            missing = required - set(data)
            if missing or extra:
                raise ArtifactError(
                    f"artifact keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
                )
            artifact = cls(
                schema_version=int(data["schema_version"]),
                profile=FidelityProfile(data["profile"]),
                source=SourceInfo(**data["source"]),
                summary=str(data["summary"]),
                generation_prompt=str(data["generation_prompt"]),
                critical_text=tuple(str(item) for item in data["critical_text"]),
                composition=tuple(Region(**item) for item in data["composition"]),
                palette=tuple(str(item) for item in data["palette"]),
                style=str(data["style"]),
                avoid=tuple(str(item) for item in data["avoid"]),
                provenance=Provenance(**data["provenance"]),
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, ArtifactError):
                raise
            raise ArtifactError(f"invalid artifact structure: {error}") from error
        artifact.validate()
        return artifact

    @classmethod
    def read(cls, path: Path) -> Self:
        """Read a UTF-8 JSON artifact from disk."""
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise ArtifactError(f"cannot read artifact {path}: {error}") from error
        if not isinstance(data, dict):
            raise ArtifactError("artifact root must be a JSON object")
        return cls.from_dict(data)


def source_digest(content: bytes) -> str:
    """Return a lowercase SHA-256 digest for source bytes."""
    return hashlib.sha256(content).hexdigest()

"""Versioned, deterministic llmPEG artifact format."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import math
import os
import re
import tempfile
import zlib
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Self

from llmpeg._version import __version__

HEADER_KEY = "llmpeg"
MAGIC = "llmPEG"

# Container format version. Major changes are breaking: a reader that does not
# know the major refuses the file. Minor changes are additive: a reader accepts
# a higher minor and ignores fields it does not know, the way PNG lets decoders
# skip ancillary chunks.
FORMAT_MAJOR = 1
FORMAT_MINOR = 1
FORMAT_VERSION = f"{FORMAT_MAJOR}.{FORMAT_MINOR}"

# Brands follow the ISO base media file format idea used by AVIF and HEIF: the
# major brand is the specification this file claims to follow, and the
# compatible brands list every specification a reader may use to interpret it.
MAJOR_BRAND = "lpg1"
COMPATIBLE_BRANDS: tuple[str, ...] = ("lpg1",)

CODEC_NAME = "llmpeg"
CODEC_VERSION = __version__
MIN_READER_VERSION = "0.1.0"

# Stated plainly so nobody mistakes this container for something self-contained:
# reconstruction needs an external text-to-image model and never returns pixels.
DECODER_REQUIREMENT = "text-to-image model; lossy; non-deterministic; not bundled"

# Artifacts written before the header existed carried a bare `schema_version: 1`.
LEGACY_SCHEMA_VERSION = 1

# An artifact may be stored inside one gzip member (RFC 1952). The reader recognises the
# envelope by gzip's own two-byte signature, never by file name, and the JSON inside is the
# unchanged canonical artifact, so `gunzip` turns it back into a plain `.llmpeg.json`.
GZIP_MAGIC = b"\x1f\x8b"
# Level 9 with a zero mtime and no stored file name keeps the envelope byte-stable.
GZIP_LEVEL = 9
# The most canonical JSON a reader inflates. The largest budget reachable under the encoder's
# default 25 MiB image limit is under 4 MiB; the cap stops a tiny hostile file inflating
# without bound.
MAX_ARTIFACT_BYTES = 8 * 1024 * 1024

FORMAT_VERSION_PATTERN = re.compile(r"^(\d+)\.(\d+)$")
HEX_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


class ArtifactError(ValueError):
    """Raised when an artifact is invalid or cannot be safely written."""


class UnsupportedFormatError(ArtifactError):
    """Raised when a file was written by a newer, incompatible llmPEG format."""


@dataclass(frozen=True)
class FormatHeader:
    """Identifies the container so a reader knows whether it can decode it.

    This is the JSON equivalent of a magic number plus a version field: PNG's
    signature, GIF's `GIF89a`, PDF's `%PDF-1.7`, and the `ftyp` box that AVIF
    and HEIF use to declare which specification a decoder needs.
    """

    magic: str = MAGIC
    format_version: str = FORMAT_VERSION
    major_brand: str = MAJOR_BRAND
    compatible_brands: tuple[str, ...] = COMPATIBLE_BRANDS
    encoder: str = f"{CODEC_NAME}/{CODEC_VERSION}"
    min_reader_version: str = MIN_READER_VERSION
    decoder: str = DECODER_REQUIREMENT

    @property
    def version_tuple(self) -> tuple[int, int]:
        """Return the format version as (major, minor)."""
        match = FORMAT_VERSION_PATTERN.fullmatch(self.format_version)
        if match is None:
            raise ArtifactError(f"format_version must be MAJOR.MINOR, got {self.format_version!r}")
        return int(match.group(1)), int(match.group(2))

    def validate(self) -> None:
        """Validate the header and reject formats this build cannot read."""
        if self.magic != MAGIC:
            raise ArtifactError(f"not an llmPEG artifact: magic is {self.magic!r}")
        major, _ = self.version_tuple
        if major > FORMAT_MAJOR:
            raise UnsupportedFormatError(
                f"artifact uses format {self.format_version}; this build reads "
                f"{FORMAT_MAJOR}.x and needs llmpeg >= {self.min_reader_version}"
            )
        if not self.major_brand.strip():
            raise ArtifactError("major_brand must not be empty")
        if self.major_brand not in self.compatible_brands:
            raise ArtifactError("compatible_brands must include the major_brand")
        for name, value in {
            "encoder": self.encoder,
            "min_reader_version": self.min_reader_version,
            "decoder": self.decoder,
        }.items():
            if not value.strip():
                raise ArtifactError(f"header {name} must not be empty")

    def is_strict(self) -> bool:
        """Unknown fields are an error unless the file comes from a newer minor."""
        return self.version_tuple <= (FORMAT_MAJOR, FORMAT_MINOR)

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready header."""
        return {
            "magic": self.magic,
            "format_version": self.format_version,
            "major_brand": self.major_brand,
            "compatible_brands": list(self.compatible_brands),
            "encoder": self.encoder,
            "min_reader_version": self.min_reader_version,
            "decoder": self.decoder,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Parse a header, tolerating unknown fields from a newer minor version."""
        required = {
            "magic",
            "format_version",
            "major_brand",
            "compatible_brands",
            "encoder",
            "min_reader_version",
            "decoder",
        }
        missing = required - set(data)
        if missing:
            raise ArtifactError(f"header keys missing={sorted(missing)}")
        brands = _require_list(data["compatible_brands"], "header.compatible_brands")
        header = cls(
            magic=_require_string(data["magic"], "header.magic"),
            format_version=_require_string(data["format_version"], "header.format_version"),
            major_brand=_require_string(data["major_brand"], "header.major_brand"),
            compatible_brands=tuple(
                _require_string(brand, f"header.compatible_brands[{index}]")
                for index, brand in enumerate(brands)
            ),
            encoder=_require_string(data["encoder"], "header.encoder"),
            min_reader_version=_require_string(
                data["min_reader_version"], "header.min_reader_version"
            ),
            decoder=_require_string(data["decoder"], "header.decoder"),
        )
        header.validate()
        extra = set(data) - required
        if extra and header.is_strict():
            raise ArtifactError(f"header keys mismatch; extra={sorted(extra)}")
        return header


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
class Tone:
    """Global exposure and colour statistics measured from the source pixels, not described.

    Every value is an integer on a 0-255 scale: mean Rec. 601 luminance, luminance standard
    deviation, and mean HSV saturation. `warmth` is mean red minus mean blue, -255 to 255.
    """

    luminance: int
    contrast: int
    saturation: int
    warmth: int


# Format 1.1 added the optional `tone` object.
TONE_FORMAT = (1, 1)


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

    header: FormatHeader
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
    tone: Tone | None = None

    def validate(self) -> None:
        """Validate all invariants of the current schema."""
        self.header.validate()
        if any(
            type(value) is not int
            for value in (self.source.width, self.source.height, self.source.byte_size)
        ):
            raise ArtifactError("source dimensions and byte_size must be integers")
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
        if self.tone is not None:
            if self.header.version_tuple < TONE_FORMAT:
                raise ArtifactError(f"tone requires format 1.1, got {self.header.format_version}")
            for name, value in asdict(self.tone).items():
                if type(value) is not int:
                    raise ArtifactError(f"tone.{name} must be an integer")
                low = -255 if name == "warmth" else 0
                if not low <= value <= 255:
                    raise ArtifactError(f"tone.{name} must be between {low} and 255")

    def to_dict(self) -> dict[str, Any]:
        """Return the JSON-ready representation."""
        self.validate()
        data = asdict(self)
        data[HEADER_KEY] = self.header.to_dict()
        del data["header"]
        data["profile"] = self.profile.value
        data["critical_text"] = list(self.critical_text)
        data["composition"] = [asdict(region) for region in self.composition]
        data["palette"] = list(self.palette)
        data["avoid"] = list(self.avoid)
        if self.tone is None:
            # Optional since 1.1; omitted rather than null so 1.0 artifacts round-trip unchanged.
            del data["tone"]
        return data

    def to_bytes(self) -> bytes:
        """Serialize to canonical compact UTF-8 JSON with the header first.

        Key order is fixed rather than merely sorted so the magic is the first
        thing in the file and `head -c 40` identifies it, the way a binary
        format's signature sits at offset zero.
        """
        data = self.to_dict()
        ordered: dict[str, Any] = {HEADER_KEY: data.pop(HEADER_KEY)}
        ordered.update({key: _deep_sorted(data[key]) for key in sorted(data)})
        return json.dumps(ordered, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    def to_gzip_bytes(self) -> bytes:
        """Wrap the canonical JSON in one deterministic gzip member.

        Decompressing it yields exactly `to_bytes()`. The profile budget still applies to that
        JSON: gzip shrinks what is stored, it does not let the encoder keep more content.
        """
        return gzip.compress(self.to_bytes(), compresslevel=GZIP_LEVEL, mtime=0)

    def enforce_budget(self) -> None:
        """Raise when the canonical artifact exceeds its profile's size budget."""
        actual = len(self.to_bytes())
        budget = self.profile.budget(self.source.byte_size)
        if actual > budget:
            raise ArtifactError(
                f"artifact is {actual} bytes; {self.profile.value} budget is {budget} bytes"
            )

    def write(self, path: Path, *, overwrite: bool = False, compress: bool = False) -> None:
        """Atomically write an artifact without overwriting by default.

        The serialized bytes are parsed back before anything touches the disk, so
        the tool can never emit a file that does not conform to its own format.
        With `compress`, the file is the gzip envelope from `to_gzip_bytes()`.
        """
        self.enforce_budget()
        payload = self.to_gzip_bytes() if compress else self.to_bytes()
        _verify_round_trip(self, payload)
        path = path.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and not overwrite:
            raise ArtifactError(f"refusing to overwrite existing file: {path}")
        handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(handle, "wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            if path.exists() and not overwrite:
                raise ArtifactError(f"refusing to overwrite existing file: {path}")
            if overwrite:
                os.replace(temporary, path)
            else:
                try:
                    os.link(temporary, path)
                except FileExistsError as error:
                    raise ArtifactError(f"refusing to overwrite existing file: {path}") from error
                os.unlink(temporary)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Parse and validate an artifact dictionary."""
        try:
            if HEADER_KEY in data:
                header = FormatHeader.from_dict(_require_mapping(data[HEADER_KEY], HEADER_KEY))
            elif data.get("schema_version") == LEGACY_SCHEMA_VERSION:
                # Written before the header existed. It is upgraded to the current
                # format on read, so anything this tool writes conforms; the unknown
                # encoder is what records that the original predated the header.
                header = FormatHeader(encoder=f"{CODEC_NAME}/unknown")
            else:
                raise ArtifactError(
                    f"missing {HEADER_KEY!r} header: this is not an llmPEG artifact"
                )
            required = {
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
            body = {
                key: value
                for key, value in data.items()
                if key not in {HEADER_KEY, "schema_version"}
            }
            optional = {"tone"} if header.version_tuple >= TONE_FORMAT else set()
            missing, extra = required - set(body), set(body) - required - optional
            if missing or (extra and header.is_strict()):
                raise ArtifactError(
                    f"artifact keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
                )
            source = _require_mapping(data["source"], "source")
            _require_keys(
                source, {"width", "height", "byte_size", "media_type", "sha256"}, "source"
            )
            provenance = _require_mapping(data["provenance"], "provenance")
            _require_keys(provenance, {"provider", "model", "seed", "temperature"}, "provenance")
            composition_data = _require_list(data["composition"], "composition")
            composition: list[Region] = []
            for index, item in enumerate(composition_data):
                region = _require_mapping(item, f"composition[{index}]")
                _require_keys(region, {"region", "description"}, f"composition[{index}]")
                composition.append(
                    Region(
                        _require_string(region["region"], f"composition[{index}].region"),
                        _require_string(region["description"], f"composition[{index}].description"),
                    )
                )
            tone: Tone | None = None
            if "tone" in body and "tone" in optional:
                tone_data = _require_mapping(data["tone"], "tone")
                _require_keys(tone_data, {"luminance", "contrast", "saturation", "warmth"}, "tone")
                tone = Tone(
                    _require_integer(tone_data["luminance"], "tone.luminance"),
                    _require_integer(tone_data["contrast"], "tone.contrast"),
                    _require_integer(tone_data["saturation"], "tone.saturation"),
                    _require_integer(tone_data["warmth"], "tone.warmth"),
                )
            artifact = cls(
                header=header,
                profile=FidelityProfile(_require_string(data["profile"], "profile")),
                source=SourceInfo(
                    _require_integer(source["width"], "source.width"),
                    _require_integer(source["height"], "source.height"),
                    _require_integer(source["byte_size"], "source.byte_size"),
                    _require_string(source["media_type"], "source.media_type"),
                    _require_string(source["sha256"], "source.sha256"),
                ),
                summary=_require_string(data["summary"], "summary"),
                generation_prompt=_require_string(data["generation_prompt"], "generation_prompt"),
                critical_text=_string_tuple(data["critical_text"], "critical_text"),
                composition=tuple(composition),
                palette=_string_tuple(data["palette"], "palette"),
                style=_require_string(data["style"], "style"),
                avoid=_string_tuple(data["avoid"], "avoid"),
                provenance=Provenance(
                    _require_string(provenance["provider"], "provenance.provider"),
                    _require_string(provenance["model"], "provenance.model"),
                    _optional_integer(provenance["seed"], "provenance.seed"),
                    _optional_number(provenance["temperature"], "provenance.temperature"),
                ),
                tone=tone,
            )
        except (KeyError, TypeError, ValueError) as error:
            if isinstance(error, ArtifactError):
                raise
            raise ArtifactError(f"invalid artifact structure: {error}") from error
        artifact.validate()
        return artifact

    @classmethod
    def from_file_bytes(cls, data: bytes) -> Self:
        """Parse stored artifact bytes: plain UTF-8 JSON or JSON inside a gzip envelope."""
        try:
            value = json.loads(unwrap_envelope(data).decode("utf-8"))
        except (UnicodeError, json.JSONDecodeError) as error:
            raise ArtifactError(f"cannot read artifact: {error}") from error
        if not isinstance(value, dict):
            raise ArtifactError("artifact root must be a JSON object")
        return cls.from_dict(value)

    @classmethod
    def read_stored(cls, path: Path) -> tuple[Self, bytes]:
        """Read an artifact from disk together with the exact bytes it occupies there."""
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ArtifactError(f"cannot read artifact {path}: {error}") from error
        return cls.from_file_bytes(data), data

    @classmethod
    def read(cls, path: Path) -> Self:
        """Read a plain or gzip-wrapped artifact from disk."""
        return cls.read_stored(path)[0]


def envelope_of(data: bytes) -> str:
    """Name the storage envelope of artifact bytes: `gzip` or `none`."""
    return "gzip" if data.startswith(GZIP_MAGIC) else "none"


def unwrap_envelope(data: bytes) -> bytes:
    """Return the JSON inside a gzip envelope, or the bytes unchanged when there is none."""
    if not data.startswith(GZIP_MAGIC):
        return data
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            inflated = stream.read(MAX_ARTIFACT_BYTES + 1)
    except (OSError, EOFError, zlib.error) as error:
        raise ArtifactError(f"corrupt gzip envelope: {error}") from error
    if len(inflated) > MAX_ARTIFACT_BYTES:
        raise ArtifactError(f"gzip envelope inflates beyond {MAX_ARTIFACT_BYTES} bytes")
    return inflated


def source_digest(content: bytes) -> str:
    """Return a lowercase SHA-256 digest for source bytes."""
    return hashlib.sha256(content).hexdigest()


def _deep_sorted(value: Any) -> Any:
    """Recursively sort mapping keys so serialization is byte-stable."""
    if isinstance(value, dict):
        return {key: _deep_sorted(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [_deep_sorted(item) for item in value]
    return value


def _require_keys(data: dict[str, Any], expected: set[str], context: str) -> None:
    extra, missing = set(data) - expected, expected - set(data)
    if missing or extra:
        raise ArtifactError(
            f"{context} keys mismatch; missing={sorted(missing)}, extra={sorted(extra)}"
        )


def _require_mapping(value: Any, name: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ArtifactError(f"{name} must be an object")
    return value


def _require_list(value: Any, name: str) -> list[Any]:
    if not isinstance(value, list):
        raise ArtifactError(f"{name} must be an array")
    return value


def _require_string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ArtifactError(f"{name} must be a string")
    return value.strip()


def _require_integer(value: Any, name: str) -> int:
    if type(value) is not int:
        raise ArtifactError(f"{name} must be an integer")
    return value


def _optional_integer(value: Any, name: str) -> int | None:
    return None if value is None else _require_integer(value, name)


def _optional_number(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ArtifactError(f"{name} must be a number or null")
    return float(value)


def _string_tuple(value: Any, name: str) -> tuple[str, ...]:
    return tuple(
        _require_string(item, f"{name}[{index}]")
        for index, item in enumerate(_require_list(value, name))
    )


def _verify_round_trip(artifact: Artifact, payload: bytes) -> None:
    """Fail before writing if the stored bytes do not parse back to the same artifact."""
    encoded = artifact.to_bytes()
    try:
        reparsed = Artifact.from_file_bytes(payload)
    except ArtifactError as error:
        raise ArtifactError(f"refusing to write a non-conforming artifact: {error}") from error
    if reparsed.to_bytes() != encoded:
        raise ArtifactError("refusing to write an artifact that does not round-trip")

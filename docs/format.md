# The `.llmpeg.json` container format

Version **1.0**. This document is the normative description of the file llmPEG writes.

A conventional image format starts with a signature so a reader can answer two questions before
parsing anything: *is this mine?* and *can my version read it?* PNG opens with an eight-byte
signature, GIF spells its version into the magic itself (`GIF87a`, `GIF89a`), PDF writes
`%PDF-1.7`, and AVIF and HEIF carry an ISO base media `ftyp` box naming a **major brand** plus a
list of **compatible brands** a decoder may use.

llmPEG artifacts are JSON, so the signature is a JSON object — but it answers the same questions,
and it comes first in the file.

## The header

Every artifact begins with a single `llmpeg` object:

```json
{"llmpeg":{
  "magic":"llmPEG",
  "format_version":"1.0",
  "major_brand":"lpg1",
  "compatible_brands":["lpg1"],
  "encoder":"llmpeg/0.3.0",
  "min_reader_version":"0.1.0",
  "decoder":"text-to-image model; lossy; non-deterministic; not bundled"
}, ...}
```

| Field | Meaning |
| --- | --- |
| `magic` | Always `llmPEG`. Identifies the file as this format, independent of its extension. |
| `format_version` | `MAJOR.MINOR` of the **container**, not of the tool. |
| `major_brand` | The specification this file claims to follow. `lpg1` is format 1.x. |
| `compatible_brands` | Every specification a reader may use to interpret the file. Must contain `major_brand`. |
| `encoder` | The tool and version that wrote it, as `name/version`. |
| `min_reader_version` | The oldest llmPEG release able to read this file. |
| `decoder` | What is needed to reconstruct an image. Deliberately blunt: llmPEG ships no decoder. |

The header is written **first** in the byte stream. JSON objects are unordered by specification,
but the serializer fixes the order anyway, so `head -c 40` identifies a file the way `file(1)`
identifies a PNG:

```console
$ head -c 40 photo.jpg.llmpeg.json
{"llmpeg":{"magic":"llmPEG","format_
```

## Compatibility rules

Borrowed from PNG's critical/ancillary chunk distinction, expressed through the version number:

| File version vs. reader | Behaviour |
| --- | --- |
| Higher **major** | **Refuse.** Raise `UnsupportedFormatError` naming the version needed. |
| Higher **minor**, same major | **Accept**, and ignore unknown fields. Minor bumps are additive only. |
| Same or lower | **Accept strictly** — an unknown field is an error, because at a version we fully know, an unrecognised key is a bug or a typo, not a feature. |

Consequences for anyone extending the format:

- Adding an optional field → bump the **minor**. Old readers keep working.
- Removing or repurposing a field, or changing a meaning → bump the **major** and add a new brand.
- Never add a field without a version bump: at the current version, strict mode will reject it.

## Body

After the header, the body carries the semantic payload. Every field is required at 1.0:

| Field | Type | Meaning |
| --- | --- | --- |
| `profile` | string | `gist`, `balanced`, or `detailed` — the fidelity contract and byte budget. |
| `source` | object | `width`, `height`, `byte_size`, `media_type`, `sha256` of the original. |
| `summary` | string | One factual sentence. |
| `generation_prompt` | string | Standalone description a generator can render. |
| `critical_text` | array | Strings that must survive verbatim. |
| `composition` | array | `{region, description}` for each area of the frame. |
| `palette` | array | `#RRGGBB` colours. |
| `style` | string | Medium and visual treatment. |
| `avoid` | array | Errors a generator should not make. |
| `provenance` | object | `provider`, `model`, `seed`, `temperature` of the encoding run. |

**The body never contains image bytes.** `source.sha256` identifies the original so an evaluation
can prove it is comparing against the right file; it does not let anyone recover it.

## Canonical serialization

Byte-stable, so a hash or a size measurement means something:

1. UTF-8, no ASCII escaping (`ensure_ascii=False`).
2. Compact separators — no insignificant whitespace.
3. The `llmpeg` header first, retaining its declared field order so `magic` leads.
4. Every other top-level key sorted, and all nested object keys sorted recursively.

The header costs **228 bytes**. Migrating an old artifact also removed the 19-byte
`"schema_version":1,` field it replaced, so existing files grew by **209 bytes net**. That is real
overhead and it is charged honestly against every compression ratio this project reports.

## Conformance

Two guarantees, both enforced in code rather than documented and hoped for:

**Nothing non-conforming is ever written.** `Artifact.write()` serializes, parses the bytes back,
and compares — if the round trip is not byte-identical, it raises before touching the disk. A
malformed artifact cannot reach a file.

**Anything written stays inside its budget.** `enforce_budget()` runs first; over-budget output
fails rather than silently dropping content to flatter a ratio.

Check any file:

```console
$ llmpeg verify photo.jpg.llmpeg.json
llmPEG 1.0 (lpg1)
compatible brands: lpg1
written by: llmpeg/0.3.0
needs reader: llmpeg >= 0.1.0
decoder: text-to-image model; lossy; non-deterministic; not bundled
profile: balanced
encoder model: ollama/qwen3-vl:32b-ctx49k
conforms: yes
```

`verify` exits `0` when the file conforms and `2` when it does not, so it works in a pipeline.

## File naming

`llmpeg encode photo.jpg` writes `photo.jpg.llmpeg.json`: the suffix is **appended** to the whole
name rather than replacing the extension. `photo.jpg` and `photo.png` therefore keep separate
artifacts instead of colliding, and an artifact always names the file it came from. Nothing in the
format depends on the file name — `magic` is the identifier — so any name is readable.

## Legacy files

Artifacts written before the header existed carried a bare `schema_version: 1` and no `llmpeg`
object. They are still readable: the reader recognises them, upgrades them to 1.0 in memory, and
records `encoder: "llmpeg/unknown"` because the writing version was never stored. Writing such an
artifact emits current-format bytes, so the upgrade is one-way and automatic.

Every artifact in this repository has been migrated. Fifteen grew by exactly 209 bytes; two moved
by 210 and 208 because the same commit also normalised a `temperature` value and a stray space in
their bodies.

## What the format deliberately does not do

- **No compression of the JSON itself.** It is meant to be read by a person; gzip belongs at the
  transport layer.
- **No embedded thumbnail.** A thumbnail would dominate the artifact and quietly turn a semantic
  codec into a bad image format.
- **No signature or encryption.** `sha256` identifies the source; it does not authenticate the
  artifact.
- **No promise that two decodes match.** `decoder` says `non-deterministic` because that is true,
  and the format would rather say so in every file than let a reader assume otherwise.

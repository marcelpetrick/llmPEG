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
  "encoder":"llmpeg/0.4.0",
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

## Optional gzip envelope

Since llmpeg 0.4.0 an artifact may also be stored inside a single gzip member (RFC 1952),
conventionally named `photo.jpg.llmpeg.json.gz` — the name `gzip photo.jpg.llmpeg.json` produces.
`llmpeg encode --gzip` writes one; every command that reads an artifact accepts either form.

- **The JSON inside is unchanged.** Decompressing yields exactly the canonical bytes described
  above, header first, still format 1.0. `gunzip` turns an envelope back into a plain artifact,
  and `gzip` turns a plain artifact into a readable envelope.
- **Recognised by content, not by name.** A file that starts with gzip's signature `1f 8b` is an
  envelope; anything else is parsed as JSON.
- **Deterministic when llmPEG writes it.** Compression level 9, `mtime` 0, no stored file name, so
  the same artifact always produces the same bytes. Envelopes written by other tools, with a name
  or timestamp in their gzip header, read the same.
- **Bounded.** A reader refuses an envelope that inflates beyond 8 MiB, and reports corrupt,
  truncated, or trailing data as an error.
- **The budget is charged on the JSON.** A profile's byte budget applies to the canonical JSON,
  not to the envelope, so compression shrinks what is stored without letting the encoder keep
  more description.
- **Ratios are charged on the stored file.** `inspect` divides the source size by the bytes on
  disk: the format header, the body, and gzip's 18 bytes of header and trailer.

**Why this is not a format version bump.** No field is added, removed, or reinterpreted, so the
JSON contract and the compatibility rules above hold unchanged. A version number could not have
warned an older reader anyway: the header sits inside the compressed stream, so gzip's own
signature at offset zero is what identifies an envelope. Releases before 0.4.0 cannot open one
directly; `gunzip` it first.

Measured on all 17 checked-in artifacts by `scripts/measure_gzip.py`, recorded in
[`gzip-measurement.json`](gzip-measurement.json):

| Stored as | Total bytes |
| --- | ---: |
| Plain canonical JSON | 48,817 |
| gzip envelope | **21,801** (44.7%) |

Per file the envelope is 34.2% to 56.9% of the plain size. The shortest artifacts shrink least:
the 1,206-byte `cat-on-grass` becomes 686 bytes (56.9%), while the 4,173-byte `street-bicycles`
becomes 1,518 (36.4%). On the same bytes, zstd at level 22 totals 21,790, xz 22,968, and bz2
23,019. gzip is 11 bytes behind zstd across all 17 files and every system can already read it.

## Conformance

Two guarantees, both enforced in code rather than documented and hoped for:

**Nothing non-conforming is ever written.** `Artifact.write()` serializes, parses the bytes back,
and compares — if the round trip is not byte-identical, it raises before touching the disk. A
malformed artifact cannot reach a file. For a gzip envelope the check decompresses the bytes about
to be written, so the envelope is verified too.

**Anything written stays inside its budget.** `enforce_budget()` runs first; over-budget output
fails rather than silently dropping content to flatter a ratio.

Check any file:

```console
$ llmpeg verify photo.jpg.llmpeg.json
llmPEG 1.0 (lpg1)
compatible brands: lpg1
written by: llmpeg/0.4.0
needs reader: llmpeg >= 0.1.0
decoder: text-to-image model; lossy; non-deterministic; not bundled
envelope: none (1206 bytes on disk)
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

- **No compression inside the JSON.** The JSON stays readable by a person. Compression is the
  optional gzip envelope around it, never a packed field within it.
- **No embedded thumbnail.** A thumbnail would dominate the artifact and quietly turn a semantic
  codec into a bad image format.
- **No signature or encryption.** `sha256` identifies the source; it does not authenticate the
  artifact.
- **No promise that two decodes match.** `decoder` says `non-deterministic` because that is true,
  and the format would rather say so in every file than let a reader assume otherwise.

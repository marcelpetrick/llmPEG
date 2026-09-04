# llmPEG

[![CI](https://github.com/marcelpetrick/llmPEG/actions/workflows/ci.yml/badge.svg?branch=master)](https://github.com/marcelpetrick/llmPEG/actions/workflows/ci.yml)
[![License: GPL v3 or later](https://img.shields.io/badge/license-GPLv3%20or%20later-blue.svg)](LICENSE)
[![Python 3.14](https://img.shields.io/badge/Python-3.14-3776ab.svg)](https://www.python.org/)
[![Ruff](https://img.shields.io/badge/lint-ruff-261230.svg)](https://docs.astral.sh/ruff/)
[![mypy strict](https://img.shields.io/badge/types-mypy%20strict-2a6db2.svg)](https://mypy-lang.org/)
[![Coverage 96.5%](https://img.shields.io/badge/coverage-96.5%25-brightgreen.svg)](#development)

**llmPEG** — the *LLM Photo Expert Group*, after JPEG's **J**oint **P**hotographic **E**xperts
**G**roup. In JPEG the codec is an algorithm. Here the codec is a **large language model**: an LLM
does the compressing, and a second model does the "decompressing".

The joke came first. A satirical article does the rounds every few months — *"teenager compresses
family photos into AI prompts and deletes the originals, 6 MB down to 200 bytes!"* Deletion has
been renamed compression. Everybody laughs.

llmPEG is that joke, built for real and measured honestly. A vision model turns your image into a
small text description. Later, an image generator reads that description and paints a **brand new
picture**. If you delete the original, it is gone. What comes back is not your photo — it is a
stranger's photo of the same idea.

**Author: Marcel Petrick <mail@marcelpetrick.it>**

**Note: project is generated with AI.**

**License: GPLv3 or later. See `LICENSE`.**

> ## ⚠️ This is TOTALLY LOSSY
>
> llmPEG does not preserve pixels. It does not preserve faces, text, brands, or how many things
> were in the picture. It throws the image away and keeps a caption.
>
> Never use it for archives, evidence, medical images, identity documents, irreplaceable family
> photos, or anything you cannot afford to lose. It is not a backup. It is not JPEG. It is an
> experiment about how much meaning survives when you delete everything else.

## How it works, for non-technical readers

```mermaid
flowchart LR
    A["📷 Your photo<br/>800 KB"] -->|"a vision model<br/>looks at it"| B["📝 A description<br/>1.2 KB of text"]
    B --> C["💾 You keep ONLY this<br/>660x smaller"]
    A -.->|"the original is<br/>thrown away"| D["🗑️ Gone forever"]
    C -->|"later, an image model<br/>reads the description"| E["🎨 A NEW picture<br/>painted from words"]
    E --> F["👀 The same scene —<br/>but not the same photo"]

    style A fill:#dbeafe,stroke:#2563eb,color:#102a43
    style C fill:#fef3c7,stroke:#d97706,color:#3b2f0b
    style D fill:#fee2e2,stroke:#dc2626,color:#450a0a
    style E fill:#f3e8ff,stroke:#9333ea,color:#3b0764
    style F fill:#dcfce7,stroke:#16a34a,color:#052e16
```

Think of it as describing a painting to a friend over the phone, throwing the painting away, and
years later asking a different artist to paint it back from your description. You get *a*
painting. You do not get *your* painting.

There is no decompressor. "Decompression" here means an image generator inventing a new picture
from text — which is why everything below is scored rather than trusted.

## Try it on your own photo

[`prototypeWebUI/`](prototypeWebUI/README.md) is a small local web page: drop an image, watch the
vision model describe it, read the description, then have the Codex CLI paint a new picture from
those words alone.

```bash
export OLLAMA_VISION_HOST=http://your-ollama-host:11434
uv run python prototypeWebUI/server.py     # then open http://127.0.0.1:8000
```

Generation defaults to the logged-in Codex CLI and explicitly invokes its `$imagegen` skill.
The page can switch per request to a sibling ComfyUI checkout, Pollinations with an API key, or an
Automatic1111-compatible server. The ComfyUI adapter uses its existing self-starting shell script
and falls back to Codex only when that local service is unavailable. The prompt remains editable
before generation—the one real perk of a codec whose compressed form is readable.

Doing this to a photo you took yourself makes the point faster than any table below.

## The cat, the ratio, and the catch

| Source photo | Prompt-only reconstruction |
| --- | --- |
| ![Cat stretched on grass, public domain](survey/sources/cat-on-grass.jpg) | ![llmPEG reconstruction of the cat](survey/reconstructions/cat-on-grass.png) |

| Measurement | Result |
| --- | ---: |
| Source JPEG | 799,983 bytes |
| Semantic artifact | 1,206 bytes |
| **Compression ratio** | **663:1** |
| Size reduction | 99.85% |
| Visual proxy score | 0.595 (pass, `balanced`) |
| Layout score | 0.706 (pass) |
| dHash similarity | 0.500 |

**663:1.** That is the whole seduction of the idea, and it is real — 1,206 bytes of text stood in
for an 800 KB photograph, and what comes back is unmistakably a cat stretched out on grass.

Now the catch: it is **not the same cat**. The markings are invented, the pose is approximate, the
fur is a different fur. And this is the *lowest* visual-proxy score of the three cats tested — the
best ratio in this repository buys the weakest resemblance. That trade-off is the finding, not a
footnote.

## The hard case: a page of text

| Source | Prompt-only reconstruction |
| --- | --- |
| ![Satirical source article](media/newsArticle.jpg) | ![llmPEG reconstruction](examples/news-article.reconstructed.png) |

The satirical article that inspired the project is also the cruelest test for it, because its
meaning *is* its text. Generated from [the rendered prompt](examples/news-article.prompt.txt)
alone — the generator never saw the source.

| Measurement | Result |
| --- | ---: |
| Source JPEG | 123,585 bytes |
| Semantic artifact | 3,543 bytes |
| Size reduction | 97.13% (35:1) |
| Visual proxy score | 0.770 (pass) |
| Layout score | 0.812 (pass) |
| Palette distance | 0.059 (pass; lower is better) |
| Critical-text recall | 0.600 (**fail**) |
| `detailed` profile verdict | **fail** |

That last row matters most. The output kept the masthead, headline, article grid, boy with laptop,
crying family, and palette — then invented new body copy. It is a good semantic reconstruction and
a bad copy of a document. The checked-in
[evaluation report](examples/news-article.evaluation.json) records both facts, and this demo stays
in the README **because** it fails.

The reconstruction PNG is 1.88 MB — larger than the input JPEG. The storage win exists only while
you keep the artifact and regenerate on demand; model weights and compute are not free.

## Benchmarks

### Cat survey (`n=3`, `balanced`)

Open [`survey/index.html`](survey/index.html) for interactive comparisons with machine metrics,
exact prompts, source/license links, 1–5 human-rating controls, and JSON export.

| Aggregate | Result |
| --- | ---: |
| Cases passing proxy thresholds | 3/3 |
| Mean visual proxy | 0.667 |
| Mean layout score | 0.686 |
| Mean palette distance | 0.081 |
| Mean dHash similarity | 0.474 |

The codec reliably preserved "what kind of cat is doing what, where?" It did not preserve the same
cat, exact markings, fur texture, or pixels.

The [detailed identity survey](survey/detailed.html) repeats the experiment with 2.5–3.2 KB
artifacts carrying subject bounds, pose landmarks, marking boundaries, and camera geometry. It
improves two visual-proxy scores and slightly lowers one — extra detail helps selectively rather
than guaranteeing identity.

### Expanded scene benchmark (`n=10`, `detailed`) — complete

Harder question: what survives in a busy scene full of people, objects, and signage? Ten complex
sources, all reconstructed from their prompts alone and evaluated. Per-case table in
[`survey/EXPANDED.md`](survey/EXPANDED.md), visuals in
[`survey/expanded.html`](survey/expanded.html).

| Aggregate | Result |
| --- | ---: |
| Cases measured | 10 of 10 |
| Passing all thresholds | 9 |
| Failing a threshold | 1 (crew portrait, on text recall) |
| Mean visual proxy | 0.737 |
| Mean layout score | 0.746 |
| Mean palette distance | 0.069 |
| Mean critical-text recall | 0.950 |

**Text survived far better than expected.** Nine of ten cases recalled every critical string — one
reconstruction rendered a Japanese platform sign, `山手線 / Yamanote Line / 東京・上野・駒込方面`,
correctly from the description alone.

**Identity still did not.** The single failure is the one that depends on *who* is in the frame:
the six-person astronaut crew portrait recalled half its text and invented the rest, turning six
specific people into six plausible ones. More cases did not soften that.

Two caveats on the 0.950: recall does not punish *invented* text (one reconstruction adds a
fictional bike number and still scores 1.00), and duplicate expected strings all match a single
rendered occurrence. Both are documented in `EXPANDED.md`.

### What a full cycle costs

Measured by [`scripts/benchmark_cycle.py`](scripts/benchmark_cycle.py) against a local
`qwen3-vl:32b-ctx49k` endpoint — three images, two runs each, `balanced` profile. Raw data in
[`docs/benchmark-cycle.json`](docs/benchmark-cycle.json).

| Stage | Mean | Range |
| --- | ---: | ---: |
| **Compress** (image → artifact) | 78.0 s | 63.5 – 104.7 s |
| **Render prompt** (artifact → generator prompt) | < 1 ms | — |
| **Evaluate** (source vs reconstruction) | 0.12 s | 0.11 – 0.13 s |
| **Decompress** (prompt → new image) | not measured | external generator |

The cost is wildly asymmetric. Compressing one photograph costs over a minute of GPU time;
everything in the core package afterwards is effectively free. The expensive generation step was
not measured in this benchmark. The prototype can invoke a generator, but that compute remains an
external cost. A codec whose decompressor is "rent a diffusion model" has an honesty problem with
the word *compression*, which is the joke.

**Reproducibility is worse than the ratio suggests.** Re-encoding `cat-on-grass` for this
benchmark produced a **1,275-byte** artifact where the checked-in run produced **997 bytes** —
627:1 instead of 802:1, from the same image, the same model name, the same seed `42` and
temperature `0`. The compression ratio is not a property of your photo. It is a property of one
particular run of one particular model, and it moves by 28% between runs.

(Both figures predate the format header, so they are comparable with each other but not with the
tables above. The header is a constant and does not affect the spread.)

### Does the score match a human eye? We still cannot say

A vision-model judge rated every checked-in pair on scene, identity, composition, mood, and an
overall "is this a faithful stand-in?".

An earlier version of this README reported that `visual_proxy_score` correlates **−0.468** with
that judge — that the headline metric pointed the wrong way. **That claim is withdrawn.** A second
run, differing only by a formatting instruction added to the judge's prompt, changed **11 of 12
verdicts by an average of 1.67 points** on a 1–5 scale, at temperature 0 with a fixed seed. The
correlation moved with them:

| Metric | ρ, run 1 (n=12) | ρ, run 2 (n=16) |
| --- | ---: | ---: |
| **`visual_proxy_score`** | **−0.468** | **+0.007** |
| `edge_similarity` | −0.392 | +0.389 |
| `palette_distance` (inverted) | −0.725 | +0.287 |

Every correlation flipped sign or collapsed. The finding is therefore not about the metrics at
all: **a single-run vision-model judge is not a stable enough instrument to validate them.** Both
runs are checked in so the flip can be recomputed rather than believed.

What survives: `aspect_similarity` is degenerate in both runs (σ ≈ 0.004), and the structural
signals remain blind to subject identity by construction — edges and histograms cannot encode
*who* is in a photograph. Treat `visual_proxy_score` as a structural sanity check, not a quality
score. Full analysis, both datasets, and what would actually settle the question in
[`docs/metrics.md`](docs/metrics.md).

### Can the codec improve itself? Not yet

[`scripts/adversarial_refine.py`](scripts/adversarial_refine.py) runs a GAN-*shaped* loop — no
gradients, no trained discriminator, just the useful part of the idea: the extraction instruction
proposes, a critic that sees the original and only the generated prompt attacks, and its
complaints steer the next round.

| Round | Mean reconstructability | Severe misses | Mean artifact bytes |
| ---: | ---: | ---: | ---: |
| 0 (baseline) | 3.00 | 6 | 2,767 |
| 1 | 3.00 | 10 | 2,408 |
| 2 | 3.00 | 10 | 2,418 |

It failed, and the failure is the useful part: **the critic returned exactly 3 for all nine
case-rounds.** A discriminator with no dynamic range provides no gradient, so nothing downstream
could work. Told to prioritise counts and positions, the encoder produced *smaller* artifacts with
*more* severe misses — focus instructions compete for a fixed byte budget, and nothing decided
what was safe to drop. Diagnosis and the fix worth trying next (pairwise forced choice instead of
absolute scoring) in [`docs/adversarial.md`](docs/adversarial.md).

Regenerate any survey page after changing a manifest or result:

```bash
uv run llmpeg survey survey/manifest.json --output survey/index.html --overwrite
uv run llmpeg survey survey/detailed-manifest.json --output survey/detailed.html --overwrite
uv run llmpeg survey survey/expanded-manifest.json --output survey/expanded.html --overwrite
```

View the checked-in comparisons directly on GitHub Pages:

- [Balanced cat survey](https://marcelpetrick.github.io/llmPEG/)
- [Detailed cat survey](https://marcelpetrick.github.io/llmPEG/detailed.html)
- [Expanded scene survey](https://marcelpetrick.github.io/llmPEG/expanded.html)

## Media and licensing

The project requires every benchmark and survey image to be freely licensed, with attribution
read from its source record rather than guessed. The three cat images and eight traced expanded
images meet that rule; two older expanded images remain explicitly unverified:

| Set | Images | Licensing |
| --- | ---: | --- |
| Cat survey | 3 | Public domain dedication — [per-case credits](survey/README.md) |
| Expanded scene benchmark | 10 (8 traced, 2 unverified) | CC0 1.0 and NASA public domain — [per-case credits](survey/EXPANDED.md#sources-and-licensing) |

Sources are stored unmodified apart from being resized to at most 1920 px on the longest edge, and
every artifact embeds its source's SHA-256 hash.

Two expanded-benchmark sources (`kitchen-table`, `living-room`) have **no traced Commons record**.
Their URLs were never recorded, and three search passes verified by perceptual hash failed to find
them, so they are labelled unverified in the gallery rather than credited on a guess. They must be
traced before this benchmark is published anywhere that asserts licensing.

One further exception, stated plainly: `media/newsArticle.jpg` is **not** free-licensed media. It is the
third-party satirical image that motivated the project, reproduced here for commentary and as a
deliberately difficult test case. It is not part of the licensed benchmark set.

## The file format

A real image format tells you, before you parse anything, whether the file is yours and whether
your version can read it. PNG opens with an eight-byte signature. GIF spells the version into the
magic itself (`GIF87a`, `GIF89a`). PDF writes `%PDF-1.7`. AVIF and HEIF carry an ISO base media
`ftyp` box naming a **major brand** and the **compatible brands** a decoder may use.

llmPEG artifacts are JSON, so the signature is a JSON object — but it answers the same questions,
and it comes first in the file:

```json
{"llmpeg":{
  "magic":"llmPEG",
  "format_version":"1.0",
  "major_brand":"lpg1",
  "compatible_brands":["lpg1"],
  "encoder":"llmpeg/0.2.0",
  "min_reader_version":"0.1.0",
  "decoder":"text-to-image model; lossy; non-deterministic; not bundled"
}, ...}
```

That last field is the one this format needs and others do not. A PNG decoder ships with the
library; llmPEG's does not exist here at all, so the container says so in every single file.

```console
$ head -c 40 photo.jpg.llmpeg.json
{"llmpeg":{"magic":"llmPEG","format_

$ llmpeg verify photo.jpg.llmpeg.json
llmPEG 1.0 (lpg1)
written by: llmpeg/0.2.0
needs reader: llmpeg >= 0.1.0
decoder: text-to-image model; lossy; non-deterministic; not bundled
conforms: yes
```

`verify` exits `0` when a file conforms and `2` when it does not, so it works in a pipeline.

**Compatibility** follows PNG's critical/ancillary split, expressed through the version number:

| File version vs. your build | Behaviour |
| --- | --- |
| Higher **major** | **Refused**, naming the release you need |
| Higher **minor** | **Accepted**; unknown fields ignored, because minor bumps are additive |
| Same or older | **Accepted strictly** — an unknown key is a bug, not a feature |

**Conformance is enforced, not promised.** `write()` serializes the artifact, parses its own bytes
back, and compares — if the round trip is not byte-identical it raises *before* touching the disk.
The encoder cannot emit a file it could not read.

**What the header cost.** 228 bytes per artifact. Migrating an old file also dropped the 19-byte
`schema_version` field it replaced, so the checked-in artifacts grew by 209 bytes net. That is real
overhead and it is charged against every ratio in this README: the cat went from 802:1 to **663:1** and the news article from
37:1 to **35:1** when the header landed. All 17 checked-in artifacts were migrated and every
published figure re-measured, because the alternative — quoting the old ratios against the new
files — is exactly the kind of accounting this project exists to make fun of.

Files written before the header existed remain readable and upgrade on read. Full specification,
including the body schema and the canonical serialization rules, in
[`docs/format.md`](docs/format.md).

## Architecture

See the [styled C4 architecture guide](docs/architecture.md) for system-context, container,
component, and reconstruction-lifecycle diagrams.

```text
image ──vision model──> versioned .llmpeg.json ──prompt renderer──> generator prompt
  │                                                                  │
  └──────────────────── evaluation harness <──new image───────────────┘
```

The artifact holds source dimensions and hash, a fidelity profile, generation prompt, critical
text, composition regions, palette, style, avoid-list, and encoder provenance. It never contains
the original image bytes. JSON is serialized canonically, byte budgets are enforced, and source
files are never modified or deleted. The codec remains generator-neutral; the CLI and prototype
Web UI add optional adapters around it.

## Quick start

llmPEG needs Python 3.14+ and [uv](https://docs.astral.sh/uv/). Dependencies are pinned in
`uv.lock`.

```bash
uv sync --extra dev
uv run llmpeg --help
```

Point it at your vision server once, then the everyday commands take no flags at all:

```bash
export OLLAMA_VISION_HOST=http://your-ollama-server:11434

uv run llmpeg encode photo.jpg               # -> photo.jpg.llmpeg.json; reports bytes and ratio
uv run llmpeg reconstruct photo.jpg.llmpeg.json > photo.prompt.txt
uv run llmpeg generate photo.jpg.llmpeg.json # -> photo.jpg.reconstructed.png
uv run llmpeg verify photo.jpg.llmpeg.json
uv run llmpeg inspect photo.jpg.llmpeg.json
```

`encode` writes `<whole file name>.llmpeg.json` beside the image and prints the ratio, so the
common case needs no `--output` and no follow-up command. `reconstruct` writes the prompt to
stdout so it pipes. `generate` asks the sibling ComfyUI checkout first and uses the logged-in
Codex CLI only when that adapter or service is unavailable. `evaluate` finds the artifact the same
way:

```bash
uv run llmpeg evaluate photo.jpg regenerated.png   # uses photo.jpg.llmpeg.json
```

Use `--generator codex` to select Codex directly. Override ComfyUI discovery with
`--comfyui-script`, `LLMPEG_COMFYUI_SCRIPT`, `--comfyui-host`, or `LLMPEG_COMFYUI_HOST`. Codex's
built-in image generation produced the checked-in demos; both generator paths receive only the
rendered text prompt, never the source image.

Output files are never overwritten unless `--overwrite` is supplied. Encoding sends the full image
to the configured Ollama endpoint, so only use a server you trust.

### When you need the details

Everything above has an explicit form, and every default is overridable:

```bash
uv run llmpeg encode photo.jpg \
  --profile detailed \                 # gist | balanced (default) | detailed
  --output artifacts/photo.jpg.llmpeg.json \
  --host http://other-host:11434 \
  --model qwen3-vl:32b-ctx49k \
  --timeout 600 \
  --max-image-bytes 26214400 \
  --max-image-pixels 50000000 \
  --overwrite

uv run llmpeg evaluate photo.jpg regenerated.png \
  --artifact artifacts/photo.jpg.llmpeg.json \
  --ocr-text regenerated.txt \
  --output evaluation.json
```

The client uses Ollama's `/api/chat`, structured output, temperature `0`, seed `42`, and
`/no_think`. Ollama 0.32 with this Qwen build sometimes places valid schema-constrained JSON in
`message.thinking` despite `think:false`; llmPEG accepts that field only when it parses as
complete valid JSON. It fails closed on empty, truncated, malformed, or over-budget output.

`evaluate` exits `0` for pass, `1` for threshold failure, `2` for usage/data errors, and `3` when
a required check (normally `detailed`-profile OCR) was not evaluated. `verify` exits `0` when a
file conforms to the format and `2` when it does not.

## Convert a whole folder, and convert it back

The joke in full: turn a folder of photographs into a folder of text, then paint them back. The
commands below use `--project` so `uv` remains attached to this checkout after entering the photo
folder. Set the photo directory and trusted Ollama endpoint before running them.

### 1. Compress every photo

```bash
LLMPEG_PROJECT=/home/mpetrick/repos/llmPEG
PHOTO_DIR=/path/to/photos
cd "$PHOTO_DIR"
export OLLAMA_VISION_HOST=http://your-ollama-host:11434
mkdir -p llmpeg/artifacts llmpeg/restored

find . -maxdepth 1 -type f \( -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.png' \) -print0 |
  while IFS= read -r -d '' f; do
    n=$(basename "${f#./}")
    uv run --project "$LLMPEG_PROJECT" llmpeg encode "${f#./}" \
      --output "llmpeg/artifacts/$n.llmpeg.json"
  done

du -sh llmpeg/artifacts          # compact text artifacts; originals still remain
```

`encode` appends `.llmpeg.json` to the **whole** file name, so `photo.jpg` and `photo.png` in one
folder produce two artifacts instead of one silently overwriting the other. The explicit output
path places them where the later loops expect them. With no `--overwrite`, re-running stops on an
existing artifact rather than spending more model time. `find` avoids zsh's unmatched-glob error;
`-print0` handles spaces in file names.

### 2. Check what you actually have

```bash
for a in llmpeg/artifacts/*.llmpeg.json; do
  uv run --project "$LLMPEG_PROJECT" llmpeg verify "$a" | head -1  # llmPEG 1.0 (lpg1)
  uv run --project "$LLMPEG_PROJECT" llmpeg inspect "$a" | grep ratio
done
```

### 3. Delete the originals — the destructive step

> ### 🔥 STOP
>
> This is the part of the meme that is a joke. Your photographs do **not** come back. What comes
> back is a new picture of a similar scene: different faces, different pets, different text.
> **Never run this on photographs you care about.** Run it on copies, or on the sample folder
> below, and only to see the point made.

The step is deliberately not a one-liner. Set the variable in the same command so it cannot happen
by scroll-back accident:

```bash
I_UNDERSTAND_THIS_DELETES_MY_PHOTOS=yes bash -c '
  [ "$I_UNDERSTAND_THIS_DELETES_MY_PHOTOS" = yes ] || exit 1
  for a in llmpeg/artifacts/*.llmpeg.json; do
    rm -f -- "$(basename "$a" .llmpeg.json)"   # photo.jpg.llmpeg.json -> photo.jpg
  done
  echo "originals deleted; only the text remains"
'
```

### 4. Convert back

Generate a new image from each artifact. The CLI renders the text prompt internally, tries the
sibling ComfyUI adapter first, and falls back to Codex only if that adapter or service is
unavailable:

```bash
for a in llmpeg/artifacts/*.llmpeg.json; do
  n=$(basename "$a" .llmpeg.json)
  uv run --project "$LLMPEG_PROJECT" llmpeg generate "$a" \
    --output "llmpeg/restored/$n.png" --overwrite
done
```

The default ComfyUI adapter is discovered at `../ComfyUI/generate_image.sh`. If the repositories
are elsewhere, pass `--comfyui-script /path/to/generate_image.sh`. To bypass ComfyUI and use the
[Codex CLI](https://github.com/openai/codex) directly:

```bash
for a in llmpeg/artifacts/*.llmpeg.json; do
  n=$(basename "$a" .llmpeg.json)
  uv run --project "$LLMPEG_PROJECT" llmpeg generate "$a" --generator codex \
    --output "llmpeg/restored/$n.png" --overwrite
done
```

`reconstruct` remains available when you want to inspect, edit, or pipe the exact prompt without
generating an image. There is still no decompressor: every output is a newly invented image.

For the artifacts already written under this repository's `llmpeg-output/`, run:

```bash
cd /home/mpetrick/repos/llmPEG
mkdir -p llmpeg-output/generated
for a in llmpeg-output/artifacts/*.llmpeg.json; do
  n=$(basename "$a" .llmpeg.json)
  uv run llmpeg generate "$a" --output "llmpeg-output/generated/$n.png"
done
```

### What it costs: five photos, measured

A real run over five CC0 photographs (3,125,477 bytes total), `balanced` profile, local
`qwen3-vl:32b-ctx49k` for encoding and Codex for generation:

| Stage | Time |
| --- | ---: |
| Compress 5 photos | **101 s** (14–27 s each, mean 20 s) |
| Render 5 prompts | **< 1 s** |
| "Decompress" 5 photos | **304 s** (51–69 s each, mean 61 s) |
| **Total wall clock** | **405 s — under 7 minutes** |

| Folder | Size |
| --- | ---: |
| 5 original photos | 3,125,477 bytes |
| 5 artifacts | **9,018 bytes** |
| Ratio | **347:1** (99.71% smaller) |

Roughly **80 seconds per photo** for the full round trip, almost all of it model time. Compression
is the cheap half; painting the picture back costs three times as much and needs a service you do
not control.

And at the end of it you have five pictures that are not your photographs.

## Fidelity profiles

| Profile | Intended preservation | Artifact budget |
| --- | --- | ---: |
| `gist` | subject, action, setting, palette, broad composition | max(1 KiB, 2% of source) |
| `balanced` | gist plus relationships, lighting, style, major objects, critical text | max(4 KiB, 5%) |
| `detailed` | balanced plus OCR text, attributes, approximate geometry, typography intent | max(16 KiB, 15%) |

If a model response does not fit, encoding **fails** instead of silently dropping content to
improve the ratio.

## What the score means

The offline harness uses Pillow to compare aspect ratio, dHash, RGB histograms, edge density, and
dominant colors, combining them into `visual_proxy_score` and `layout_score`. These are fast
structural proxies — not human judgment, not CLIP similarity, and not proof that two images mean
the same thing. An attempt to validate them against a vision-model judge was inconclusive — the
judge itself proved unstable ([`docs/metrics.md`](docs/metrics.md)) — so read `visual_proxy_score`
as a structural sanity check rather than a quality score. Critical-text recall is scored
separately and reports `not_evaluated` when no transcript is supplied.

The demo transcript was verified by hand because the local Tesseract installation had no language
data. llmPEG consumes OCR text; it does not ship an OCR engine.

## Development

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests scripts prototypeWebUI
uv run pytest --cov=llmpeg --cov-report=term-missing --cov-fail-under=95
uv run python -m build
```

The suite is offline and injects fake providers. Live Ollama and image-generation runs are manual
demo steps, not CI dependencies. Current suite: **121 tests, 96.5% branch-aware coverage**.

[`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs all five gates on Python 3.14 for
every push and pull request.

See [AGENTS.md](AGENTS.md) for the contributor working agreement, including the Conventional
Commits requirement.

### Releases

Pushing a `v*` tag runs [`.github/workflows/release.yml`](.github/workflows/release.yml), which
builds an sdist and a wheel with `uv build`, checks them with twine, and attaches both to a
generated GitHub Release.

The current release is [`v0.2.0`](https://github.com/marcelpetrick/llmPEG/releases/tag/v0.2.0).

There is no PyPI upload: the distribution name `llmpeg` is already registered there by an
unrelated project, so installing is done from a release artifact or from a checkout:

```bash
uv pip install llmpeg-0.2.0-py3-none-any.whl   # from a GitHub Release
uv pip install .                               # from a clone
```

## Limitations

- Regeneration is non-deterministic and depends on provider, model version, seed, settings, and
  service availability.
- Faces, identity, exact poses, text, type metrics, fine texture, and small objects change.
- Prompts can preserve private facts even though they are smaller than images.
- A compact artifact can exceed a tiny or already well-compressed source.
- Evaluation proxies can be fooled and cannot establish evidentiary equivalence.
- Generator compute and model weights dwarf the artifact; this is a storage experiment, not a
  claim about total-system efficiency.

Inspired by [this LinkedIn post](https://lnkd.in/p/eSqXmyvw) and the satirical
["New Compression Technique"](https://programmerhumor.io/ai-memes/new-compression-technique-9yp7)
article. See the [product vision](docs/vision.md) for the contract and the
[delivery plan](docs/plan.md) for its implementation history.

Licensed under the [GNU General Public License v3.0 or later](LICENSE).

# llmPEG vision

The name is the thesis in miniature. JPEG comes from the **J**oint **P**hotographic **E**xperts
**G**roup; llmPEG is the **LLM P**hoto **E**xpert **G**roup — a codec whose "expert" is a language
model, which is exactly as reassuring as it sounds. The pun is deliberate, and so is the warning
inside it: this format is authored by something that guesses.

llmPEG is an experimental **semantic image codec**. It replaces an image with a compact,
portable description and later asks an image generator to render that description. The result
should preserve what a person remembers about the image, not its pixels.

That distinction is the product. A JPEG/PNG codec answers “how can I reproduce these pixels?”
llmPEG answers “what must a new image communicate to count as the same scene?” It can save a
great deal of storage when exact reproduction does not matter, but it is intentionally lossy,
non-deterministic, and unsuitable for evidence, archival masters, medical imagery, identity
records, diagrams with exact geometry, or text that must remain readable.

## Starting point

The spark for this experiment is [this LinkedIn post](https://lnkd.in/p/eSqXmyvw), together with
the article image saved in this repository. The short link may require LinkedIn access; the local
image keeps the motivating artifact available to the project and its tests. The same image is
presented as satire in ProgrammerHumor.io’s
[“New Compression Technique”](https://programmerhumor.io/ai-memes/new-compression-technique-9yp7),
whose joke is precisely that deletion has been renamed compression. No verifiable publication,
research result, or real “Eugene Hogwood” project is asserted here; the mock article is a prompt,
not evidence.

The reference image in `media/newsArticle.jpg` is the joke made concrete: a mock Daily News Tech
page claims that a 13-year-old compresses family photos into tiny prompts and destroys the
originals. It is also a deliberately difficult test image. Its semantic content includes:

- a dark navy newspaper masthead and a bold two-line headline;
- a subheading, multiple body paragraphs, a pull quote, captions, and small labels;
- a main photo of a boy using a laptop and a smaller family photo;
- a precise editorial grid, icons, rules, typography, and color accents.

A generated reconstruction may plausibly recover the newspaper look, hierarchy, boy, laptop,
family, and overall story. Today’s generators should not be expected to reproduce the exact copy,
font metrics, faces, photograph details, or layout. For text-heavy images, the compact artifact
must therefore carry important text verbatim and the evaluator must score OCR separately from
visual similarity. llmPEG must never imply that plausible invented text is preserved data.

The supplied JPEG is 123,585 bytes—not 6 MB—so all compression claims in this repository use
measured file sizes rather than the motivating article’s hypothetical numbers.

## MVP outcome

The product is a Python package, command-line tool, and localhost prototype that can:

1. inspect an image with a vision model and encode the result into a versioned JSON prompt
   artifact;
2. validate that artifact, report its byte size, and calculate the measured size ratio;
3. turn the artifact into a generator-ready prompt;
4. generate a new image through local ComfyUI/Qwen-Image-2.1;
5. compare it with transparent structural proxies and repeated local semantic judgments; and
6. run fully offline tests by substituting deterministic fake providers.

Real providers live behind small interfaces. Encoding and experimental similarity rating target
local Ollama with `qwen3.5:4b`. Generation has one fail-closed local path: a bundled
Qwen-Image-2.1 workflow submitted directly to ComfyUI. Hosted and unverified fallback adapters are
not active product paths. The core artifact and prompt remain generator-neutral, and the whole
suite stays testable without a network, GPU, model, or credentials.

## Fidelity contract

The user chooses what “close” means before encoding:

| Profile | Preserve | May regenerate | MVP acceptance target |
| --- | --- | --- | --- |
| `gist` | subject count/type, major action, setting, dominant palette, broad composition | identity, texture, small objects, all non-essential text | CLIP-like semantic score ≥ 0.55 and palette distance ≤ 0.30 |
| `balanced` | gist plus spatial relations, lighting, style, major objects, headline/critical text | exact faces, fonts, fine texture, incidental text | semantic score ≥ 0.65, layout score ≥ 0.60, palette distance ≤ 0.22 |
| `detailed` | balanced plus OCR text, object attributes, approximate geometry, typography intent | pixels, exact identity, microscopic detail, generator-specific variation | semantic score ≥ 0.72, layout score ≥ 0.70, critical-text recall ≥ 0.90 |

These are initial product targets, not claims of achieved quality. The default test harness uses
cheap deterministic proxies (perceptual hash, color histograms, edges, dimensions, and optional
OCR text recall). A pluggable learned semantic scorer can later promote these targets into a
proper model benchmark. Passing a score never makes the reconstruction evidentially equivalent.

For the newspaper reference, `detailed` is the only honest profile: layout and exact text are
central to its meaning. Even then, the expected MVP reconstruction is “recognizably the same
article concept,” not a readable duplicate.

## Artifact and size budget

The encoded `.llmpeg.json` file opens with a versioned format header — magic, format version,
brands, encoder, and the decoder it requires — followed by the fidelity profile, source
dimensions, generation prompt, critical verbatim text, normalized composition regions, palette,
and model provenance. It does not embed the source image. Canonical compact JSON makes byte counts
stable. The header is 228 bytes; migrated artifacts grew by 209 bytes after the obsolete 19-byte
`schema_version` field was removed. Every reported ratio includes the full header. See
[format.md](format.md). New encodes default to a deterministic gzip envelope
(`.llmpeg.json.gz`); `--plain` opts out. Its ratio is charged on the compressed file, while the
budgets below still apply to the canonical JSON.

Budgets are deliberately tied to source size:

- `gist`: at most 1 KiB or 2% of the source, whichever is larger;
- `balanced`: at most 4 KiB or 5% of the source, whichever is larger;
- `detailed`: at most 16 KiB or 15% of the source, whichever is larger.

If critical text exceeds a profile’s budget, the encoder must fail clearly or require the user to
choose what to drop. It must not silently discard facts to manufacture an impressive ratio.

## Standing requirements

Constraints set by the project owner. They are recorded here because they are decisions, not
preferences to be re-derived each session.

### Identity and framing

- The name is the thesis: **llmPEG**, the *LLM Photo Expert Group*, against JPEG's Joint
  Photographic Experts Group. The pun must stay legible in the README.
- The project is a **meme built for real**. Lead with the joke, then the measured prototype, then
  the applicable background. It can be done — and the interesting part is where it breaks.
- Say **TOTALLY LOSSY**, loudly and above the fold. Never let a reader assume otherwise.
- The package, CLI, and artifact extension are all `llmpeg`. The original name was PromptPress and
  survives only in early commit messages.

### Licensing and attribution

- **GPLv3 or later.** Author: Marcel Petrick <mail@marcelpetrick.it>. The README carries a bold
  author / AI-generated / licence block.
- **Every benchmark and survey image must be freely licensed** (CC0 or public domain) with its
  author, licence, and source URL read from the source record — never guessed. Say so in the
  README. An image whose provenance cannot be verified is labelled unverified rather than quietly
  credited or quietly dropped.

### Format

- The artifact carries a **versioned header** so a reader knows which tooling can decode it,
  modelled on how real image formats do metadata. See [format.md](format.md).
- **Output must always conform.** The encoder cannot emit a file that does not parse back as a
  valid artifact; conformance is enforced in code, not documented and hoped for.

### Documentation

- A **mermaid data-flow diagram for non-technical readers**, encoding through semantic
  reconstruction.
- A **copy-pasteable folder round trip**: convert a whole folder of photos, restore it, with real
  wall-clock timing so a new user knows what they are in for.
- Benchmarks report **how long a full cycle takes** and **how close the result is**.
- CI, licence, and coverage **badges** in the README.

### Engineering

- **Python 3.14** baseline.
- **Conventional Commits**, reviewed and corrected rather than assumed.
- Dependencies **pinned exactly** and kept at the latest stable release.
- A **GitHub Action builds the wheel** and attaches release artifacts.
- Everything must fit **current best standards**; when a gate cannot pass, say so rather than
  claiming green.

### Method

- Keep the active model path local: Ollama/Qwen for encoding and rating, ComfyUI/Qwen-Image-2.1
  for generation. Fail closed instead of switching to a hosted provider.
- Improvement work is **iterative and auditable**: every claim traceable to a checked-in record a
  reader can recompute, and **negative results published as prominently as positive ones**.

### Automatic comparison

- Do not describe any automatic rating as human perception. SSIM-style structure, learned
  perceptual distance, and semantic model judgments measure different things.
- Keep deterministic metrics unchanged and visible beside five semantic dimensions: subject,
  identity, composition, text, and style.
- Expose repeated-trial spread. Pairwise prompt tuning must reverse candidate order and reject a
  challenger when the two choices disagree or a passing deterministic guard regresses.
- Human calibration remains open work. The first local experiment is evidence about one source,
  not a general quality claim; see [`creator-rater/report.json`](creator-rater/report.json).

## Principles and non-goals

- **Honest terminology:** semantic reconstruction, not conventional compression.
- **Keep the original by default:** encoding never deletes or modifies source images.
- **Measure every claim:** store byte counts, provider/model provenance, and evaluation results.
- **Portable artifacts:** JSON is readable and generator-neutral; schemas are versioned.
- **Decoder provenance matters:** model, version, seed, and settings affect the output; a retired
  model or unavailable service can make later reconstruction drift or fail.
- **Reproducible plumbing:** deterministic serialization, seeded provider requests where possible,
  dependency injection, fixtures, and offline tests.
- **Privacy is explicit:** remote encoding or generation may disclose image contents; local
  providers are preferred and endpoint use is visible.

The MVP does not promise pixel-perfect restoration, stable human identity, security through
obscurity, guaranteed compression on tiny images, or a replacement for JPEG, PNG, backups, or
archives. Its success criterion is simpler: demonstrate a working and measurable loop from image
to compact semantic artifact to a credible regenerated image, while making the loss impossible to
miss.

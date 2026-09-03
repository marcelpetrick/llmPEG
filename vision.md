# llmPEG vision

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

The MVP is a Python package and command-line tool that can:

1. inspect an image with a vision model and encode the result into a versioned JSON prompt
   artifact;
2. validate that artifact, report its byte size, and calculate the measured size ratio;
3. turn the artifact into a generator-ready prompt;
4. evaluate a reconstructed image with transparent, repeatable structural metrics; and
5. run fully offline tests by substituting deterministic fake providers.

Real encode/decode providers live behind small interfaces. The first real encoder targets the
locally available Ollama vision endpoint used by the `claude-vision` shell function. Generation
can be performed interactively with Codex image generation or through a future/API adapter; the
core codec must remain testable without network access or credentials.

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

The encoded `.llmpeg.json` file contains a schema version, fidelity profile, source dimensions,
generation prompt, critical verbatim text, normalized composition regions, palette, and model
provenance. It does not embed the source image. Canonical compact JSON makes byte counts stable.

Budgets are deliberately tied to source size:

- `gist`: at most 1 KiB or 2% of the source, whichever is larger;
- `balanced`: at most 4 KiB or 5% of the source, whichever is larger;
- `detailed`: at most 16 KiB or 15% of the source, whichever is larger.

If critical text exceeds a profile’s budget, the encoder must fail clearly or require the user to
choose what to drop. It must not silently discard facts to manufacture an impressive ratio.

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

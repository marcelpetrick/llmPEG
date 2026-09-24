# llmPEG architecture

> **Architecture goal:** exchange exact pixels for a compact, inspectable semantic artifact while
> making that irreversible loss explicit and measurable.

The diagrams use the [C4 model](https://c4model.com/) from system context down to components. Blue
elements are llmPEG, purple elements are models outside its deterministic core, and amber
elements are durable evidence.

Both models run locally: Qwen3.5 (`qwen3.5:4b`) behind Ollama encodes, and Qwen-Image-2.1 behind
ComfyUI generates. Early experiments used a remote `qwen3-vl:32b` endpoint and hosted image
generators (Codex's built-in tool, briefly others); those adapters are gone, and only their
labelled evidence remains under `survey/`.

## 1. System context

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Inter, ui-sans-serif, system-ui","primaryColor":"#E8F1FF","primaryBorderColor":"#2563EB","primaryTextColor":"#102A43","lineColor":"#64748B","secondaryColor":"#F3E8FF","tertiaryColor":"#FFF7D6"}}}%%
C4Context
  title llmPEG — semantic image reconstruction
  Person(reviewer, "Reviewer", "Encodes images and judges whether regenerated meaning is sufficient")
  System(llmpeg, "llmPEG", "Produces portable semantic artifacts, prompts, metrics, and surveys")
  System_Ext(vision, "Local vision model", "Qwen3.5 behind Ollama for encoding and comparison")
  System_Ext(generator, "Local image generator", "Qwen-Image-2.1 through ComfyUI; sees rendered text only")

  Rel(reviewer, llmpeg, "Encodes, reconstructs, inspects, evaluates", "CLI / HTML")
  Rel(llmpeg, vision, "Sends source image and strict extraction schema", "Ollama /api/chat")
  Rel(llmpeg, generator, "Supplies generator-neutral prompt", "Text")
  Rel(generator, llmpeg, "Returns a novel generated image")
  Rel(llmpeg, reviewer, "Shows provenance, compression ratio, comparisons, and ratings")

  UpdateElementStyle(llmpeg, $bgColor="#DBEAFE", $fontColor="#102A43", $borderColor="#2563EB")
  UpdateElementStyle(vision, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
  UpdateElementStyle(generator, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
```

## 2. Containers and trust boundaries

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Inter, ui-sans-serif, system-ui","lineColor":"#64748B"}}}%%
C4Container
  title llmPEG — containers and evidence flow
  Person(user, "Experimenter", "Runs a deliberately lossy reconstruction experiment")

  System_Boundary(pp, "llmPEG") {
    Container(cli, "CLI", "Python / argparse", "Coordinates encode, reconstruct, generate, inspect, evaluate, and survey commands")
    Container(core, "Codec core", "Python", "Validates images and creates canonical semantic artifacts")
    Container(eval, "Evaluation harness", "Python / Pillow", "Computes deterministic structural proxy metrics")
    Container(survey, "Survey renderer", "Python", "Builds a portable interactive HTML report")
    Container(web, "Prototype Web UI", "HTML / CSS / JavaScript", "Runs image → prompt → new image → experimental rating")
    Container(webBackend, "Prototype backend", "Python HTTP server", "Bounds uploads and coordinates local model calls")
    ContainerDb(files, "Experiment evidence", "JSON, text, PNG/JPEG", "Sources, artifacts, prompts, reconstructions, metrics, manifests")
    Container(html, "Static survey", "HTML/CSS/JS", "Side-by-side inspection, browser-local ratings, JSON export")
    Container(scripts, "Measurement scripts", "Python", "Sweeps, benchmarks, and tone experiments against the live local models; never run in CI")
  }

  System_Ext(ollama, "Ollama + Qwen3.5", "Local non-deterministic extraction and rating boundary")
  System_Ext(imagegen, "ComfyUI + Qwen-Image-2.1", "Local non-deterministic generation boundary")

  Rel(user, cli, "Runs")
  Rel(user, web, "Drops an image and reviews the prompt")
  Rel(web, webBackend, "Encode, generate, and rate requests", "HTTP on localhost")
  Rel(cli, core, "Invokes")
  Rel(webBackend, core, "Invokes")
  Rel(core, ollama, "Image + extraction contract", "HTTP/JSON")
  Rel(webBackend, ollama, "Images + strict extraction/rating contracts", "HTTP/JSON")
  Rel(webBackend, imagegen, "Editable prompt only", "Local HTTP")
  Rel(imagegen, webBackend, "Generated image")
  Rel(core, files, "Writes canonical .llmpeg.json and prompt")
  Rel(cli, imagegen, "Rendered prompt only; fail closed", "Local HTTP")
  Rel(files, imagegen, "Prompt only — never source pixels")
  Rel(imagegen, files, "Writes reconstruction PNG")
  Rel(cli, eval, "Invokes")
  Rel(eval, files, "Reads image pair; writes evaluation JSON")
  Rel(cli, survey, "Invokes")
  Rel(survey, files, "Reads manifest and evidence")
  Rel(survey, html, "Generates")
  Rel(user, html, "Reviews and rates", "Browser")
  Rel(scripts, core, "Encode, generate, measure")
  Rel(scripts, files, "Writes measurements.json and evidence")

  UpdateElementStyle(files, $bgColor="#FFF7D6", $fontColor="#713F12", $borderColor="#D97706")
  UpdateElementStyle(web, $bgColor="#DBEAFE", $fontColor="#102A43", $borderColor="#2563EB")
  UpdateElementStyle(webBackend, $bgColor="#DBEAFE", $fontColor="#102A43", $borderColor="#2563EB")
  UpdateElementStyle(ollama, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
  UpdateElementStyle(imagegen, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
```

The model calls are trust boundaries: provenance records the encoder configuration, but llmPEG
cannot make model output deterministic. The prototype sends a bounded copy to local Ollama and
only the resulting editable prompt to local ComfyUI. Its rating step sends source and generated
images to Ollama, never to the generator. Validation, canonical JSON, budgets, prompt rendering,
proxy evaluation, and HTML rendering are local and testable.

## 3. Codec components

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Inter, ui-sans-serif, system-ui","lineColor":"#64748B"}}}%%
C4Component
  title Codec core — Python components
  Container_Boundary(core, "llmpeg") {
    Component(cli, "Command dispatcher", "cli.py", "Parses commands and maps failures to exit codes")
    Component(guard, "Image guard", "encoder.py + Pillow", "Checks type, byte/pixel limits, dimensions, and source digest; measures tone from pixels")
    Component(adapter, "Vision adapter", "providers.py", "Calls Ollama with a strict JSON schema and fidelity-specific instructions")
    Component(codec, "Artifact builder", "encoder.py", "Converts extracted fields into a validated artifact")
    Component(model, "Artifact model", "artifact.py", "Writes the versioned header, validates the schema, enforces the byte budget, and writes canonical JSON, plain or gzip-wrapped, atomically")
    Component(renderer, "Prompt renderer", "encoder.py", "Expands the artifact into a model-neutral generation brief")
    Component(generator, "Qwen generator adapter", "generators.py", "Runs one bundled ComfyUI workflow and fails closed")
    Component(grading, "Tone correction", "grading.py", "Measures a render's tone error against the artifact; steers a second render or regrades the image")
    Component(metrics, "Metric engine", "evaluation.py", "Measures aspect, dHash, histogram, edges, palette, layout, and text recall")
    Component(rater, "Similarity rater", "rating.py", "Repeats local semantic comparisons and order-reversed A/B judgments")
    Component(report, "Survey renderer", "survey.py", "Combines evidence into interactive static HTML")
  }

  Container_Ext(ollama, "Qwen3.5", "Local Ollama vision model")
  Container_Ext(imagegen, "Qwen-Image-2.1", "Local ComfyUI image model")
  ContainerDb_Ext(evidence, "Evidence files", "Image, JSON, text, HTML")

  Rel(cli, guard, "encode")
  Rel(guard, adapter, "Verified image bytes")
  Rel(adapter, ollama, "Schema-constrained request")
  Rel(adapter, codec, "Structured description")
  Rel(codec, model, "Constructs and validates")
  Rel(model, evidence, "Atomic canonical write, optionally gzip")
  Rel(cli, renderer, "reconstruct")
  Rel(renderer, model, "Reads")
  Rel(renderer, evidence, "Writes prompt")
  Rel(cli, generator, "generate")
  Rel(generator, renderer, "Uses rendered prompt")
  Rel(generator, imagegen, "Prompt only")
  Rel(generator, evidence, "Writes new image")
  Rel(cli, grading, "generate --tone-correction")
  Rel(grading, generator, "Second render with feedback negatives")
  Rel(cli, metrics, "evaluate")
  Rel(metrics, evidence, "Reads pair; writes result")
  Rel(rater, ollama, "Source + reconstruction under strict schema")
  Rel(rater, metrics, "Keeps deterministic metric vector separate")
  Rel(rater, evidence, "Writes auditable trials and A/B verdicts")
  Rel(cli, report, "survey")
  Rel(report, evidence, "Reads manifest; writes HTML")

  UpdateElementStyle(model, $bgColor="#FFF7D6", $fontColor="#713F12", $borderColor="#D97706")
  UpdateElementStyle(adapter, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
```

## 4. CLI reconstruction lifecycle

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Inter, ui-sans-serif, system-ui","actorBkg":"#DBEAFE","actorBorder":"#2563EB","signalColor":"#475569","activationBkgColor":"#FFF7D6","activationBorderColor":"#D97706"}}}%%
sequenceDiagram
  autonumber
  actor U as Experimenter
  participant C as llmPEG CLI
  participant V as Ollama / Qwen3.5
  participant A as .llmpeg.json.gz
  participant G as ComfyUI / Qwen-Image-2.1
  participant E as Evaluator
  participant H as HTML survey

  U->>C: encode source.jpg --profile detailed
  C->>C: Validate type, size, pixels, and source hash
  C->>C: Measure tone (luminance, contrast, saturation, warmth)
  C->>V: Image + strict identity-landmark schema
  V-->>C: Description, regions, palette, style, avoid-list
  C->>A: Validate canonical budget and atomically persist (gzip default)
  Note over A: Original pixels are not embedded
  U->>C: reconstruct artifact
  C-->>U: Text prompt
  U->>C: generate artifact
  C->>G: Text prompt only (local, fail closed)
  G-->>C: Novel reconstruction PNG
  opt --tone-correction loop
    C->>C: Measure the render's tone against the artifact
    C->>G: Same prompt + feedback negatives, same seed
    G-->>C: Second render
  end
  C-->>U: Output path and concrete local provider
  U->>C: evaluate source + reconstruction + artifact
  C->>E: Verified source pair
  E-->>A: Structural metrics and threshold checks
  U->>C: survey manifest
  C->>H: Generate self-contained report
  H-->>U: Visual inspection + human ratings export
```

The CLI's `generate` command has one path: direct local ComfyUI HTTP with the bundled
Qwen-Image-2.1 workflow. Unreachable services, workflow errors, invalid images, and model-release
errors remain visible; no hosted fallback runs. The Web UI exposes the same adapter through
`/api/generate`. `/api/rate` combines unchanged deterministic metrics with three local semantic
trials; its result is explicitly uncalibrated. Ollama and ComfyUI release their models between
phases so the workloads can share an 8 GB GPU. The Web UI remains a localhost prototype, not a
hardened network service.

## Architectural consequences

| Property | What the architecture guarantees | What it cannot guarantee |
| --- | --- | --- |
| Portability | Artifact and rendered prompt are plain UTF-8 JSON/text; the optional gzip envelope opens with standard `gunzip` | Future models interpret the prompt identically |
| Reproducibility | Source hash, dimensions, profile, model, seed, and temperature are recorded; the same artifact, seed, and local setup render identical pixels | Identical pixels across machines, model versions, or settings; identity of the original subject |
| Safety | Inputs are bounded; artifacts validate; writes are atomic; source is never deleted | A prompt captures every visually important detail |
| Evaluation | Deterministic metrics, measured tone, repeat spread, raw semantic trials, and human survey exports remain separate and inspectable | Any automatic score equals human perceptual or identity similarity |
| Compression | Stored artifacts remain far smaller than source photographs | Regenerated PNGs, model weights, and compute are free |

The central design choice is intentional: **the `.llmpeg.json` artifact is a semantic memory, not a
compressed photograph**. The detailed profile spends more bytes on identity landmarks, but any
feature absent from that artifact is irrecoverably replaced by the generator's prior.

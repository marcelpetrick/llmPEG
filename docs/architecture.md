# PromptPress architecture

> **Architecture goal:** exchange exact pixels for a compact, inspectable semantic artifact while
> making that irreversible loss explicit and measurable.

The diagrams use the [C4 model](https://c4model.com/) from system context down to components. Blue
elements are PromptPress, purple elements are models outside its deterministic core, and amber
elements are durable evidence.

## 1. System context

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Inter, ui-sans-serif, system-ui","primaryColor":"#E8F1FF","primaryBorderColor":"#2563EB","primaryTextColor":"#102A43","lineColor":"#64748B","secondaryColor":"#F3E8FF","tertiaryColor":"#FFF7D6"}}}%%
C4Context
  title PromptPress — semantic image reconstruction
  Person(reviewer, "Reviewer", "Encodes images and judges whether regenerated meaning is sufficient")
  System(promptpress, "PromptPress", "Produces portable semantic artifacts, prompts, metrics, and surveys")
  System_Ext(vision, "Vision model", "Qwen3-VL behind the local claude-vision/Ollama setup")
  System_Ext(generator, "Image generator", "Creates a new image from rendered text only")

  Rel(reviewer, promptpress, "Encodes, reconstructs, inspects, evaluates", "CLI / HTML")
  Rel(promptpress, vision, "Sends source image and strict extraction schema", "Ollama /api/chat")
  Rel(promptpress, generator, "Supplies generator-neutral prompt", "Text")
  Rel(generator, promptpress, "Returns a novel reconstruction", "PNG")
  Rel(promptpress, reviewer, "Shows provenance, compression ratio, comparisons, and ratings")

  UpdateElementStyle(promptpress, $bgColor="#DBEAFE", $fontColor="#102A43", $borderColor="#2563EB")
  UpdateElementStyle(vision, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
  UpdateElementStyle(generator, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
```

## 2. Containers and trust boundaries

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Inter, ui-sans-serif, system-ui","lineColor":"#64748B"}}}%%
C4Container
  title PromptPress — containers and evidence flow
  Person(user, "Experimenter", "Runs a deliberately lossy reconstruction experiment")

  System_Boundary(pp, "PromptPress") {
    Container(cli, "CLI", "Python / argparse", "Coordinates encode, reconstruct, inspect, evaluate, and survey commands")
    Container(core, "Codec core", "Python", "Validates images and creates canonical semantic artifacts")
    Container(eval, "Evaluation harness", "Python / Pillow", "Computes deterministic structural proxy metrics")
    Container(survey, "Survey renderer", "Python", "Builds a portable interactive HTML report")
    ContainerDb(files, "Experiment evidence", "JSON, text, PNG/JPEG", "Sources, artifacts, prompts, reconstructions, metrics, manifests")
    Container(html, "Static survey", "HTML/CSS/JS", "Side-by-side inspection, browser-local ratings, JSON export")
  }

  System_Ext(ollama, "Ollama + Qwen3-VL", "Non-deterministic semantic extraction boundary")
  System_Ext(imagegen, "Codex image generation", "Non-deterministic reconstruction boundary")

  Rel(user, cli, "Runs")
  Rel(cli, core, "Invokes")
  Rel(core, ollama, "Image + extraction contract", "HTTP/JSON")
  Rel(core, files, "Writes canonical .ppress.json and prompt")
  Rel(files, imagegen, "Prompt only — never source pixels")
  Rel(imagegen, files, "Writes reconstruction PNG")
  Rel(cli, eval, "Invokes")
  Rel(eval, files, "Reads image pair; writes evaluation JSON")
  Rel(cli, survey, "Invokes")
  Rel(survey, files, "Reads manifest and evidence")
  Rel(survey, html, "Generates")
  Rel(user, html, "Reviews and rates", "Browser")

  UpdateElementStyle(files, $bgColor="#FFF7D6", $fontColor="#713F12", $borderColor="#D97706")
  UpdateElementStyle(ollama, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
  UpdateElementStyle(imagegen, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
```

The model calls are trust boundaries: provenance records their configuration, but PromptPress
cannot make their outputs deterministic. Everything after extraction—validation, canonical JSON,
budgets, prompt rendering, proxy evaluation, and HTML rendering—is local and testable.

## 3. Codec components

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Inter, ui-sans-serif, system-ui","lineColor":"#64748B"}}}%%
C4Component
  title Codec core — Python components
  Container_Boundary(core, "promptpress") {
    Component(cli, "Command dispatcher", "cli.py", "Parses commands and maps failures to exit codes")
    Component(guard, "Image guard", "encoder.py + Pillow", "Checks type, byte/pixel limits, dimensions, and source digest")
    Component(adapter, "Vision adapter", "providers.py", "Calls Ollama with a strict JSON schema and fidelity-specific instructions")
    Component(codec, "Artifact builder", "encoder.py", "Converts extracted fields into a validated artifact")
    Component(model, "Artifact model", "artifact.py", "Validates schema, enforces byte budget, and writes canonical JSON atomically")
    Component(renderer, "Prompt renderer", "encoder.py", "Expands the artifact into a model-neutral generation brief")
    Component(metrics, "Metric engine", "evaluation.py", "Measures aspect, dHash, histogram, edges, palette, layout, and text recall")
    Component(report, "Survey renderer", "survey.py", "Combines evidence into interactive static HTML")
  }

  Container_Ext(ollama, "Qwen3-VL", "Vision model")
  ContainerDb_Ext(evidence, "Evidence files", "Image, JSON, text, HTML")

  Rel(cli, guard, "encode")
  Rel(guard, adapter, "Verified image bytes")
  Rel(adapter, ollama, "Schema-constrained request")
  Rel(adapter, codec, "Structured description")
  Rel(codec, model, "Constructs and validates")
  Rel(model, evidence, "Atomic canonical write")
  Rel(cli, renderer, "reconstruct")
  Rel(renderer, model, "Reads")
  Rel(renderer, evidence, "Writes prompt")
  Rel(cli, metrics, "evaluate")
  Rel(metrics, evidence, "Reads pair; writes result")
  Rel(cli, report, "survey")
  Rel(report, evidence, "Reads manifest; writes HTML")

  UpdateElementStyle(model, $bgColor="#FFF7D6", $fontColor="#713F12", $borderColor="#D97706")
  UpdateElementStyle(adapter, $bgColor="#F3E8FF", $fontColor="#3B0764", $borderColor="#9333EA")
```

## 4. Reconstruction lifecycle

```mermaid
%%{init: {"theme":"base","themeVariables":{"fontFamily":"Inter, ui-sans-serif, system-ui","actorBkg":"#DBEAFE","actorBorder":"#2563EB","signalColor":"#475569","activationBkgColor":"#FFF7D6","activationBorderColor":"#D97706"}}}%%
sequenceDiagram
  autonumber
  actor U as Experimenter
  participant C as PromptPress CLI
  participant V as Qwen3-VL
  participant A as .ppress.json
  participant G as Image generator
  participant E as Evaluator
  participant H as HTML survey

  U->>C: encode source.jpg --profile detailed
  C->>C: Validate type, size, pixels, and source hash
  C->>V: Image + strict identity-landmark schema
  V-->>C: Description, regions, palette, style, avoid-list
  C->>A: Validate budget and atomically persist
  Note over A: Original pixels are not embedded
  U->>C: reconstruct artifact
  C-->>G: Text prompt only
  G-->>U: Novel reconstruction PNG
  U->>C: evaluate source + reconstruction + artifact
  C->>E: Verified source pair
  E-->>A: Structural metrics and threshold checks
  U->>C: survey manifest
  C->>H: Generate self-contained report
  H-->>U: Visual inspection + human ratings export
```

## Architectural consequences

| Property | What the architecture guarantees | What it cannot guarantee |
| --- | --- | --- |
| Portability | Artifact and rendered prompt are plain UTF-8 JSON/text | Future models interpret the prompt identically |
| Reproducibility | Source hash, dimensions, profile, model, seed, and temperature are recorded | A generator recreates identical pixels or identity |
| Safety | Inputs are bounded; artifacts validate; writes are atomic; source is never deleted | A prompt captures every visually important detail |
| Evaluation | Deterministic metrics expose coarse structural drift; HTML collects human judgment | Proxy scores equal perceptual or identity similarity |
| Compression | Stored artifacts remain far smaller than source photographs | Regenerated PNGs, model weights, and compute are free |

The central design choice is intentional: **the `.ppress.json` artifact is a semantic memory, not a
compressed photograph**. The detailed profile spends more bytes on identity landmarks, but any
feature absent from that artifact is irrecoverably replaced by the generator's prior.

# Local Qwen model integration plan

Status: **in progress**  
Started: 2026-09-22  
Target release: **0.5.0**

This is the living implementation record for making both model boundaries local by default:
Ollama with a locally installed vision-capable Qwen model for encoding, and Qwen-Image-2.1
through local ComfyUI for generation. Update the checkboxes and progress log as the work lands.

The artifact remains totally lossy. `reconstruct` still renders text; `generate` asks a model to
invent a new image from that text. There is no decompressor and the source image is never sent to
the generator.

## Evidence gathered before implementation

### Current llmPEG behavior

- `llmpeg encode` defaults to `qwen3-vl:32b-ctx49k`, and the prototype requires an explicitly
  configured Ollama host.
- `llmpeg generate` tries a sibling ComfyUI shell adapter, then sends the prompt to Codex when
  that adapter is unavailable.
- The prototype Web UI offers Codex, ComfyUI with Codex fallback, Pollinations, and an unverified
  Automatic1111-compatible route. Its default is Codex.
- The static survey pages are evidence viewers only. They do not encode or generate and need no
  provider migration.
- The checked-in ComfyUI smoke record covers an older Flux workflow, not Qwen-Image-2.1.

### Local services and models found on 2026-09-22

- Ollama is reachable locally and lists `qwen3.5:4b`, a 4.7B Q4_K_M model whose declared
  capabilities include vision. The old `qwen3-vl:32b-ctx49k` default is not installed.
- ComfyUI is a clean v0.37.0 checkout plus six commits. Its service was not running during the
  initial inspection.
- These Qwen-Image-2.1 files are installed in the standard ComfyUI model directories:
  `qwen_image_2.1_int8_convrot.safetensors`, `qwen3vl_8b_w4a8.safetensors`, and
  `qwen_image_2.1_vae_bf16.safetensors`.
- The local reference workflow uses native ComfyUI nodes: `UNETLoader`, `CLIPLoader` with type
  `qwen_image`, `QwenImage21Cache` on CPU with int8, `TextEncodeQwenImage21`, `KSampler`,
  `VAEDecode`, and `SaveImage`.
- Its generation settings are 30 steps, CFG 3.5, Euler/simple, seed 42, and a 1024-pixel square
  resolution. The model config owns scheduler shift; the workflow must not add another sampling
  shift node.
- Submission and retrieval use ComfyUI's `/prompt`, `/history/{prompt_id}`, and `/view` endpoints.
- The installed Qwen-Image-2.1 weights are governed by the Qwen Research license and are
  non-commercial. llmPEG will not redistribute model files and must state this runtime constraint.

## Decisions

1. **One generation path:** package CLI and prototype Web UI call local ComfyUI directly with a
   bundled Qwen-Image-2.1 API workflow. Remove Codex, Pollinations, Automatic1111, shell-adapter,
   and fallback paths from active product code.
2. **Fail closed:** if ComfyUI is down, the workflow is rejected, or no image is returned, report
   the local failure. Never send a prompt to a hosted provider as recovery.
3. **One encoding default:** use local Ollama at `127.0.0.1` with `qwen3.5:4b`. Preserve explicit
   host/model overrides because they are useful configuration and already form a documented
   privacy boundary; show the actual endpoint and model in CLI/Web UI configuration.
4. **Direct ComfyUI protocol:** replace the checkout-specific shell script with an offline-tested
   HTTP client. Bundle the exact workflow JSON so installed wheels behave like source checkouts.
5. **Measured workflow settings:** expose resolution and seed, but keep the verified model,
   sampler, scheduler, steps, CFG, cache device, and cache dtype in the workflow. Require a square
   resolution because `TextEncodeQwenImage21` accepts one resolution value.
6. **No artifact-format change:** provider defaults and generator plumbing do not add, remove, or
   repurpose artifact fields. Format stays 1.0. The package release moves from 0.4.2 to 0.5.0.
7. **Offline CI, live manual smoke:** tests inject HTTP responses; CI never needs Ollama, ComfyUI,
   a GPU, credentials, or model weights. A final manual smoke exercises both local services.

## Implementation checklist

### 1. Shared configuration and local vision encoding

- [ ] Centralize the default Ollama host and vision model.
- [ ] Make CLI and prototype default to local Ollama plus `qwen3.5:4b`.
- [ ] Keep the upload/privacy boundary visible and preserve exact model provenance in artifacts.
- [ ] Update provider, CLI, and Web UI tests for the new defaults.

### 2. Qwen-Image-2.1 ComfyUI adapter

- [ ] Add the inspected API workflow to the Python package.
- [ ] Submit a copied workflow with request-specific prompt, square resolution, seed, and a unique
      output prefix; never mutate shared template state.
- [ ] Poll history to completion with one total timeout, surface ComfyUI execution errors, fetch
      the first generated image, and validate it with Pillow.
- [ ] Distinguish an unreachable service from a reachable workflow failure without falling back.
- [ ] Test successful submission/poll/view, queued responses, timeouts, malformed responses,
      server errors, missing images, and invalid image bytes entirely offline.
- [ ] Verify the workflow JSON is present in both sdist and wheel.

### 3. CLI behavior

- [ ] Make `llmpeg generate` ComfyUI/Qwen-only.
- [ ] Remove provider selection and shell-script flags; add resolution and seed controls.
- [ ] Check overwrite before submitting expensive work and report the concrete local generator.
- [ ] Preserve `reconstruct` as the prompt-only operation.

### 4. Prototype Web UI behavior

- [ ] Remove hosted and unverified generator implementations and configuration.
- [ ] Remove the generator selector and fallback messaging from HTML/JavaScript.
- [ ] Send every generation request to local Qwen-Image-2.1 through the shared adapter.
- [ ] Report local Ollama/ComfyUI readiness and make privacy text accurately say where data goes.
- [ ] Retain prompt editing, resolution, seed, elapsed time, output dimensions, CORS behavior, and
      bounded request validation.
- [ ] Update offline backend and page-contract tests.

### 5. Documentation and release

- [ ] Update README, product vision, architecture diagrams, delivery plan, and prototype guide.
- [ ] Replace current-provider claims while keeping old benchmark provenance intact: historical
      artifacts and measurements must still name the models/generators that actually produced them.
- [ ] Replace the obsolete current ComfyUI smoke evidence with a reproducible Qwen-Image-2.1
      integration record; do not rewrite historical measurements as if Qwen produced them.
- [ ] State the Qwen-Image-2.1 non-commercial runtime licence and that weights are not bundled.
- [ ] Bump the single release version to 0.5.0 and update every enforced example.
- [ ] Update the measured test-count/coverage statements only from the final gate output.

### 6. Verification and self-review

- [ ] Run a manual local Ollama encoding smoke with `qwen3.5:4b` into temporary output.
- [ ] Start local ComfyUI through the established Qwen setup and run a temporary Qwen generation
      through llmPEG; verify returned media type, dimensions, and image validity.
- [ ] Exercise the prototype's `/api/config`, `/api/encode`, and `/api/generate` routes locally.
- [ ] Run formatting, lint, strict mypy, the full coverage suite, and package build.
- [ ] Review the complete change set for local-only enforcement, prompt/source leakage, timeout and
      queue handling, concurrency, path leakage, package contents, stale docs, and misleading claims.
- [ ] Fix every review finding, rerun the full gate, and commit only green logical units.

## Progress log

- **2026-09-22 — dependency prerequisite complete.** Updated and pinned the development/build
  toolchain in commit `2608620`; all five gates passed with the then-current 137-test suite.
- **2026-09-22 — architecture inventory complete.** Traced the CLI, shared adapters, prototype
  backend/page, static surveys, tests, docs, packaging/version contract, live Ollama inventory,
  installed ComfyUI checkout, model files, and the proven Qwen-Image-2.1 workflow.
- **2026-09-22 — implementation not started.** This document is the agreed execution order; the
  remaining unchecked items are pending.


# Local Qwen model integration plan

Status: **implementation and review complete; release pending**

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

### What image-similarity research says

No single score is "similar to a human eye" for this task:

- [SSIM](https://ece.uwaterloo.ca/~z70wang/publications/ssim.pdf) compares local luminance,
  contrast, and structure and was validated on ordinary image distortions. It is useful when the
  pixels are aligned, but a newly generated scene can move an object while preserving its meaning.
- [LPIPS](https://arxiv.org/abs/1801.03924) showed that deep features match two-alternative human
  perceptual judgments better than shallow metrics on its distortion dataset.
- [DISTS](https://arxiv.org/abs/2004.07728) explicitly combines structure and texture and is more
  tolerant of replacing one plausible texture patch with another.
- [DreamSim](https://arxiv.org/abs/2306.09344) targets holistic human similarity: foreground
  objects, semantic content, color, and layout. Its authors report stronger retrieval and
  reconstruction agreement than pixel/patch metrics on their collected judgments.

Those learned metrics require heavyweight neural runtimes and still do not directly test llmPEG's
contract: counts, identity landmarks, readable text, composition, palette, and style after a
generator has invented new pixels. The implementation will therefore expose a **multi-signal
experimental rating**, not claim a calibrated human score:

1. deterministic full-reference signals already in llmPEG for aspect, coarse layout, edges,
   histogram, and palette;
2. a local Qwen-VL comparison of source and reconstruction with separate, explained ratings for
   subject/count, identity attributes, composition, text, and style/color;
3. agreement information from repeated local judgments, so instability remains visible;
4. no silent pass when OCR or the semantic rater is unavailable.

The repository's own judge experiments are also binding evidence: an absolute 1–5 judge moved
substantially after a cosmetic prompt change, and the old adversarial critic returned a constant
verdict. Automatic ratings may guide experiments, but cannot be promoted to human validation.

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
7. **Quality-first encode defaults:** default to the `detailed` profile and deterministic gzip
   storage. Gzip never buys extra profile budget: budget enforcement remains on canonical JSON,
   and every reported gzip ratio stays beside the corresponding plain ratio.
8. **Experimental rating, not a truth label:** the Web UI shows deterministic proxy metrics and
   local semantic subscores with reasons and repeat spread. It must not call them human ratings or
   hide disagreement behind one number.
9. **Pairwise tuning:** a creator-versus-rater experiment proposes a revised description from the
   source and current miss report, generates a challenger, then judges baseline versus challenger
   twice with candidate order reversed. Accept only a consistent challenger preference that also
   passes deterministic regression guards; a split result is inconclusive.
10. **Offline CI, live manual smoke:** tests inject HTTP responses; CI never needs Ollama, ComfyUI,
   a GPU, credentials, or model weights. A final manual smoke exercises both local services.

## Implementation checklist

### 1. Shared configuration and local vision encoding

- [x] Centralize the default Ollama host and vision model.
- [x] Make CLI and prototype default to local Ollama plus `qwen3.5:4b`.
- [x] Default encoding to the detailed profile and `.llmpeg.json.gz`; retain an explicit plain
      option and keep all profile budgets charged against canonical JSON.
- [x] Keep the upload/privacy boundary visible and preserve exact model provenance in artifacts.
- [x] Strengthen the detailed extraction instruction around exact counts, subject-specific visual
      identity, normalized geometry, readable text, camera, lighting, materials, and negative
      constraints without inventing hidden facts.
- [x] Update provider, CLI, and Web UI tests for the new defaults.

### 2. Qwen-Image-2.1 ComfyUI adapter

- [x] Add the inspected API workflow to the Python package.
- [x] Submit a copied workflow with request-specific prompt, square resolution, seed, and a unique
      output prefix; never mutate shared template state.
- [x] Poll history to completion with one total timeout, surface ComfyUI execution errors, fetch
      the first generated image, and validate it with Pillow.
- [x] Distinguish an unreachable service from a reachable workflow failure without falling back.
- [x] Test successful submission/poll/view, queued responses, timeouts, malformed responses,
      server errors, missing images, and invalid image bytes entirely offline.
- [x] Verify the workflow JSON is present in both sdist and wheel.

### 3. CLI behavior

- [x] Make `llmpeg generate` ComfyUI/Qwen-only.
- [x] Remove provider selection and shell-script flags; add resolution and seed controls.
- [x] Check overwrite before submitting expensive work and report the concrete local generator.
- [x] Preserve `reconstruct` as the prompt-only operation.

### 4. Prototype Web UI behavior

- [x] Remove hosted and unverified generator implementations and configuration.
- [x] Remove the generator selector and fallback messaging from HTML/JavaScript.
- [x] Send every generation request to local Qwen-Image-2.1 through the shared adapter.
- [x] Report local Ollama/ComfyUI readiness and make privacy text accurately say where data goes.
- [x] Retain prompt editing, resolution, seed, elapsed time, output dimensions, CORS behavior, and
      bounded request validation.
- [x] Update offline backend and page-contract tests.

### 5. Automatic reconstruction rating in the Web UI

- [x] Add a local semantic-comparison provider that sends source and reconstruction together to
      Qwen-VL under a strict schema, never to the image generator.
- [x] Rate subject/count, identity attributes, composition, critical text, and style/color
      separately; require concrete differences and prompt-improvement suggestions.
- [x] Run repeated deterministic judgments and report medians plus spread/disagreement instead of
      presenting a single unstable model answer as ground truth.
- [x] Combine this report with existing deterministic metrics as a transparent vector. Do not
      reweight or rename the existing `visual_proxy_score`, whose human validity is unresolved.
- [x] Add `/api/rate` and automatically invoke it after Web UI generation using the selected
      source, returned reconstruction, artifact, and rendered prompt.
- [x] Bound and validate both uploaded images and all model output; cover the full route offline.
- [x] Label the result "experimental automatic rating" and link its limitations and method.

### 6. Creator-versus-rater refinement

- [x] Add a reproducible measurement script that starts from a source, detailed artifact, and
      baseline reconstruction; saves every prompt, artifact size, rating, pairwise verdict, and
      output path needed to audit a round.
- [x] Ask local Qwen-VL to revise only observable description fields using the source and miss
      report, then enforce the normal artifact schema and uncompressed byte budget.
- [x] Generate the challenger through the same Qwen-Image-2.1 workflow and seed.
- [x] Compare baseline/challenger twice with A/B order reversed. Accept only two consistent
      challenger choices and no deterministic threshold regression; otherwise keep the baseline.
- [x] Run the loop on freely licensed checked-in sources, record failures as failures, and use
      repeated findings to improve the general encoder instruction rather than overfit one image.
- [x] Re-run an untouched holdout after any instruction change. Do not claim an improvement unless
      the checked-in evidence supports it.

### 7. Documentation and release

- [x] Update README, product vision, architecture diagrams, delivery plan, and prototype guide.
- [x] Replace current-provider claims while keeping old benchmark provenance intact: historical
      artifacts and measurements must still name the models/generators that actually produced them.
- [x] Replace the obsolete current ComfyUI smoke evidence with a reproducible Qwen-Image-2.1
      integration record; do not rewrite historical measurements as if Qwen produced them.
- [x] State the Qwen-Image-2.1 non-commercial runtime licence and that weights are not bundled.
- [x] Bump the single release version to 0.5.0 and update every enforced example.
- [x] Update the measured test-count/coverage statements only from the final gate output.

### 8. Verification and self-review

- [x] Run a manual local Ollama encoding smoke with `qwen3.5:4b` into temporary output.
- [x] Start local ComfyUI through the established Qwen setup and run a temporary Qwen generation
      through llmPEG; verify returned media type, dimensions, and image validity.
- [x] Exercise the prototype's `/api/config`, `/api/encode`, `/api/generate`, and `/api/rate`
      routes locally.
- [x] Run formatting, lint, strict mypy, the full coverage suite, and package build.
- [x] Review the complete change set for local-only enforcement, prompt/source leakage, timeout and
      queue handling, concurrency, path leakage, package contents, stale docs, and misleading claims.
- [x] Fix every review finding, rerun the full gate, and commit only green logical units.

## Progress log

- **2026-09-22 — dependency prerequisite complete.** Updated and pinned the development/build
  toolchain in commit `2608620`; all five gates passed with the then-current 137-test suite.
- **2026-09-22 — architecture inventory complete.** Traced the CLI, shared adapters, prototype
  backend/page, static surveys, tests, docs, packaging/version contract, live Ollama inventory,
  installed ComfyUI checkout, model files, and the proven Qwen-Image-2.1 workflow.
- **2026-09-22 — similarity research and plan revision complete.** Reviewed SSIM, LPIPS, DISTS,
  and DreamSim primary publications; added experimental Web UI rating, quality-first gzip encode
  defaults, and an order-swapped creator-versus-rater loop with deterministic regression guards.
- **2026-09-22 — local generator and CLI complete.** Replaced subprocess and hosted fallback code
  with a direct, bounded ComfyUI client and bundled Qwen-Image-2.1 workflow; added detailed/gzip
  encode defaults, richer extraction instructions, and offline adapter/CLI coverage. Confirmed the
  workflow resource is present in both built distributions.
- **2026-09-22 — live integration defects found and fixed.** A stale shell
  `OLLAMA_VISION_HOST` first sent the smoke request to an old LAN address; rerunning with loopback
  isolated that configuration issue. Ollama then exposed llama.cpp's grammar failure for a nested
  string `maxLength` of 3,000, so the bound is now 1,800 and HTTP response bodies remain visible.
  The local encode completed in 19.4 seconds at 1,594 canonical bytes and 930 stored gzip bytes.
  Ollama's 30-minute model residency also starved ComfyUI on the 8 GB GPU; each phase now releases
  its model allocation before the next local service runs.
- **2026-09-22 — first live creator/rater images recorded.** The public-domain monochrome-cat run
  produced a baseline and challenger. Its semantic median fell from 85 to 80 while
  `visual_proxy_score` rose from 0.632194 to 0.700023, demonstrating why the signals cannot be
  collapsed into a generic improvement claim. Raw evidence is under
  `survey/qwen/creator-rater/`.
- **2026-09-23 — live Web UI and holdout complete.** All four API routes ran against loopback
  Ollama and ComfyUI; generation returned a valid 256×256 PNG and rating completed three trials.
  The first keyboard-cat holdout attempt failed closed on truncated JSON under Ollama's 4,096-token
  runner context. An 8,192-token encode request completed the rerun. Both order-swapped judgments
  initially appeared to prefer the baseline; raw evidence is under
  `survey/qwen/creator-rater-holdout/`.
- **2026-09-23 — clean-room review removed prompt leakage from pairwise judging.** The first A/B
  implementation supplied candidate prompts, and its reasons visibly judged prompt wording rather
  than only reconstructed pixels. Pixels-only reruns chose the second-presented image in both
  experiments, producing split logical verdicts after order reversal. Both challengers are now
  rejected as inconsistent; the tuning loop has not demonstrated a trustworthy improvement
  gradient.
- **2026-09-23 — intermediate implementation commits complete.** Committed the local codec path as
  `f20c67a` and the Web/rating path as `7e7d03a`, each after its focused offline tests and lint
  checks. Documentation, the final five-gate run, review, and release remain.
- **2026-09-23 — clean-room review and final gate complete.** Review against the 0.4.2 release
  baseline found and fixed prompt leakage in A/B judging, unbounded model JSON responses, missing
  Web model-call serialization, experiment output preflight, and an insufficient CLI privacy
  notice. No Code or Architecture findings remain. The definitive gate passed: 44 files formatted,
  Ruff clean, strict mypy clean across 28 source files, 163 tests passed at 95.40% branch-aware
  coverage, and both 0.5.0 distributions built successfully.
- **2026-09-23 — release asset audit found and corrected an oversized sdist.** The first published
  0.5.0 source archive was 142 MiB because Hatch's default file selection included tracked survey
  reconstructions and presentation videos. The sdist now explicitly contains source, tests,
  measurement tools, prototype code, documentation, lock file, and package metadata while large
  repository media remains available from GitHub's source archive. A clean build from the corrected
  sdist produced a 2.4 MiB source archive and a 60 KiB wheel; neither `media/` nor `survey/` was
  packaged. Replacing the initial tag assets and verifying the corrected release are the remaining
  release steps.

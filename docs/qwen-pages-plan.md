# Qwen comparison pages and 0.5.1 release plan

Status: **complete**

Started: 2026-09-23
Target release: **0.5.1**

## Goal

Make the public visual comparison identify the measured technology on both sides of the llmPEG
round trip. The new landing page must show the checked-in local Qwen experiment: local Ollama with
`qwen3.5:4b` encodes the source into a text artifact, and local ComfyUI with Qwen-Image-2.1 invents
a new image from the rendered text alone. It must not call that second operation decompression or
imply that the generator saw the source image.

Historical survey evidence remains available and keeps its actual provenance: those artifacts
were encoded with `qwen3-vl:32b-ctx49k`, and those reconstructions used Codex's built-in image
generation. Existing measurements and images will not be relabelled as Qwen-Image-2.1 output.

## Implementation plan

### 1. Evidence and metadata

- [x] Move the two local Qwen creator/rater evidence sets under `survey/` so the static Pages site
      can publish the original source links, prompts, artifacts, reports, and generated images
      without duplicated files or network-dependent image URLs.
- [x] Add a Qwen comparison manifest and small derived metric records whose values point back to
      the authoritative creator/rater reports.
- [x] Add structured manifest metadata for encoding technology and reconstruction technology.
- [x] Add the historical technology metadata to every existing manifest without changing any
      historical artifact, reconstruction, or metric.

### 2. HTML comparison experience

- [x] Render a prominent two-stage technology panel on every survey page.
- [x] Label the second stage “reconstruction (not decompression)” and state that only rendered
      text crosses into the image generator.
- [x] Support truthful per-case image labels and findings so the Qwen page can distinguish source,
      baseline, and challenger, and visibly report rejected/inconclusive tuning rounds.
- [x] Generate and check in the Qwen comparison HTML from the manifest.
- [x] Make the Qwen page the GitHub Pages landing page while retaining explicit historical URLs.

### 3. Documentation and verification

- [x] Update README, evidence links, Pages instructions, repository layout, and local-model history.
- [x] Add offline tests for required/escaped technology metadata, custom labels/findings, Qwen
      manifest traceability, and Pages publication layout.
- [x] Regenerate all comparison pages and verify that every referenced local asset exists.
- [x] Run formatting, Ruff, strict mypy, the full branch-coverage suite, and package build.
- [x] Review the complete diff against the release base with the `reviewBranch` procedure, fix all
      confirmed findings, and rerun the full gate.
- [x] Bump the single package version and enforced documentation examples to 0.5.1.
- [x] Commit logical units with Conventional Commit messages, push, tag `v0.5.1`, publish the
      GitHub release, and verify both release assets and public comparison URLs.

## Progress log

- **2026-09-23 — inventory complete.** The public root currently deploys the historical detailed
  cat survey. Its documented pipeline is `qwen3-vl:32b-ctx49k` plus Codex built-in image
  generation. The two measured local Qwen-Image-2.1 runs are stored separately under
  `docs/creator-rater/` and `docs/creator-rater-holdout/`, so the public comparison does not expose
  them. The survey renderer currently has no structured technology metadata.
- **2026-09-23 — Qwen comparison implemented and visually inspected.** Moved the two evidence sets
  under `survey/qwen/`, added traceable derived result records and a Qwen manifest, made the new
  generated page the Pages landing file, and preserved historical URLs. The generic renderer now
  requires and escapes explicit encoding/reconstruction technology, custom image labels, and
  per-case measured outcomes. Focused tests passed, all six page images returned HTTP 200, and
  Chromium screenshots at 1440×1400 and 390×844 confirmed responsive rendering. Full gates,
  release review, version bump, and publication remain.
- **2026-09-23 — first self-review fixes complete.** The initial page showed only canonical JSON
  bytes even though both displayed artifacts are stored in gzip envelopes, and its details linked
  only to a derived metric record. The renderer now reports the plain ratio and the measured gzip
  stored ratio side by side and links each case's authoritative creator/rater report. Focused
  formatting, lint, strict typing, and 20 survey tests pass after regeneration.
- **2026-09-23 — compatibility review fix complete.** Review against `origin/master` found that
  requiring the new technology object would reject otherwise-valid manifests created before
  0.5.1. Missing metadata now renders an explicit “Not recorded” message while malformed supplied
  metadata still fails closed. Each case also exposes the encoder version stored in its artifact
  header, preserving the measured `llmpeg/0.4.2` and `llmpeg/0.5.0` provenance of the two Qwen runs.
- **2026-09-23 — final review and release gate complete.** `reviewBranch` resolved the release base
  as `origin/master @ 7a0cfed` and reviewed 42 changed files (+703/−72 at `32be475`). After fixing
  gzip evidence visibility, authoritative-report links, and legacy-manifest compatibility, no Code
  or Architecture findings remain. The definitive gate passed with 46 files formatted, Ruff clean,
  strict mypy clean across 28 source files, 171 tests at 95.42% branch-aware coverage, a 183 KiB
  sdist, a 62 KiB wheel, and both distributions accepted by Twine. Push, Pages deployment, tag,
  release, and public URL verification remain.
- **2026-09-23 — v0.5.1 published and verified.** CI and Pages passed on release commit `b0303f0`;
  the Qwen comparison, four generated images, two authoritative reports, and all three historical
  page URLs returned HTTP 200. The annotated `v0.5.1` tag and GitHub release point to that commit.
  Downloading the published assets independently confirmed version 0.5.1, archive integrity, a
  62,767-byte wheel, a 187,428-byte sdist, and exclusion of large `media/` and `survey/` content
  from the Python source distribution. This completion note intentionally follows the immutable
  release tag as a documentation-only commit.

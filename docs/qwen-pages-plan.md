# Qwen comparison pages and 0.5.1 release plan

Status: **in progress**

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
- [ ] Run formatting, Ruff, strict mypy, the full branch-coverage suite, and package build.
- [ ] Review the complete diff against the release base with the `reviewBranch` procedure, fix all
      confirmed findings, and rerun the full gate.
- [ ] Bump the single package version and enforced documentation examples to 0.5.1.
- [ ] Commit logical units with Conventional Commit messages, push, tag `v0.5.1`, publish the
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

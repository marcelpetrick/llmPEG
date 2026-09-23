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

- [ ] Move the two local Qwen creator/rater evidence sets under `survey/` so the static Pages site
      can publish the original source links, prompts, artifacts, reports, and generated images
      without duplicated files or network-dependent image URLs.
- [ ] Add a Qwen comparison manifest and small derived metric records whose values point back to
      the authoritative creator/rater reports.
- [ ] Add structured manifest metadata for encoding technology and reconstruction technology.
- [ ] Add the historical technology metadata to every existing manifest without changing any
      historical artifact, reconstruction, or metric.

### 2. HTML comparison experience

- [ ] Render a prominent two-stage technology panel on every survey page.
- [ ] Label the second stage “reconstruction (not decompression)” and state that only rendered
      text crosses into the image generator.
- [ ] Support truthful per-case image labels and findings so the Qwen page can distinguish source,
      baseline, and challenger, and visibly report rejected/inconclusive tuning rounds.
- [ ] Generate and check in the Qwen comparison HTML from the manifest.
- [ ] Make the Qwen page the GitHub Pages landing page while retaining explicit historical URLs.

### 3. Documentation and verification

- [ ] Update README, evidence links, Pages instructions, repository layout, and local-model history.
- [ ] Add offline tests for required/escaped technology metadata, custom labels/findings, Qwen
      manifest traceability, and Pages publication layout.
- [ ] Regenerate all comparison pages and verify that every referenced local asset exists.
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

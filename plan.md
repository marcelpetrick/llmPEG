# PromptPress MVP plan

This plan follows the product contract in `vision.md`. Each phase ends in a small conventional
commit, and the final phase includes a clean-room self-review of the complete diff.

## 1. Establish the project and contracts

- Add a Python 3.11+ `src/` package with a `promptpress` console command.
- Pin runtime and development dependencies in `pyproject.toml`.
- Define a versioned artifact model with strict validation and canonical compact JSON.
- Encode the three fidelity profiles and their prompt-byte budgets as executable policy.
- Add provider protocols so network/model behavior is replaceable in tests.

Exit gate: package builds, artifact round-trips deterministically, invalid schemas fail with useful
messages, and profile budgets have unit tests.

## 2. Implement semantic encode and prompt decode

- Add an Ollama vision provider compatible with the endpoint behind the local `claude-vision`
  alias (`OLLAMA_VISION_HOST`, `/api/chat`, `qwen3-vl:32b-ctx49k`).
- Ask the model for strict structured scene data, using `/no_think`, temperature 0, and a seed by
  default; strip Markdown fences and validate the response.
- Treat image bytes as untrusted input: enforce supported formats and a configurable size limit.
- Write artifacts atomically and never remove or modify the source image.
- Render a provider-neutral generation prompt from an artifact. `promptpress reconstruct` writes
  that prompt to a file/stdout for an external generator; generation is intentionally an adapter
  boundary because the Codex built-in image tool is not a distributable Python API.
- Add `inspect` to report measured source/artifact bytes, ratio, savings, profile, and provenance.

Exit gate: an offline fake provider drives image → artifact → generation prompt end to end; HTTP
errors, malformed model output, over-budget output, and overwrite attempts are tested.

## 3. Build the evaluation harness

- Compare source and reconstruction dimensions/aspect ratio, perceptual dHash, RGB histograms,
  edge density, and dominant colors using Pillow.
- Combine those deterministic signals into a clearly named `visual_proxy_score`; never label it a
  learned semantic score.
- Compute critical-text recall from supplied OCR text. For the MVP demo, OCR output can be passed
  as a text file so evaluation stays provider-neutral and deterministic.
- Apply profile thresholds and emit both human-readable output and stable JSON.
- Add synthetic fixtures where expected “same,” “changed color,” and “changed structure” ordering
  is known.

Exit gate: metrics are bounded, ordering tests pass, missing OCR is reported as `not_evaluated`
rather than zero, and acceptance decisions identify every failed threshold.

## 4. Demonstrate the supplied article

- Encode `media/newsArticle.jpg` with the verified local Qwen3-VL endpoint.
- Save the compact artifact and exact generator prompt under `examples/`.
- Generate one reconstruction from only that prompt with Codex image generation—never provide the
  source image to the generator.
- Evaluate it and save the report. Document actual byte counts and avoid claiming success for
  metrics the demo does not meet.

Exit gate: a reviewer can see the source, artifact, reconstruction, prompt, provenance, measured
ratio, and evaluation report in the repository.

## 5. Document, automate, and review

- Write a GitHub-ready `README.md` with the honest semantic-codec framing, quick start, commands,
  architecture, demo results, privacy warning, and limitations.
- Add Ruff formatting/linting, mypy strict checks, pytest with coverage, package build checks, and a
  GitHub Actions workflow across supported Python versions.
- Run all gates locally from a clean project directory.
- Review the final diff for correctness, security/privacy, API ergonomics, test gaps, misleading
  claims, accidental host/path disclosure, and repository cleanliness; fix findings before the
  final commit.

Final gate:

```text
ruff format --check .
ruff check .
mypy src tests
pytest --cov=promptpress --cov-report=term-missing --cov-fail-under=90
python -m build
```

## Definition of done

The MVP is done when the offline suite passes, the real reference artifact has been produced by
the local vision model, a prompt-only Codex reconstruction and honest report are checked in, all
quality gates pass, the worktree is clean, and the conventional commit history tells the build
story in atomic steps.

# llmPEG MVP plan

This plan follows the product contract in `vision.md`. Each phase ends in a small conventional
commit, and the final phase includes a clean-room self-review of the complete diff.

> **Status: all five phases are delivered.** The MVP shipped under the project's original name,
> PromptPress; the package, CLI, and artifact extension are now `llmpeg`. Phase 5's CI workflow
> landed later than the rest and lives in `.github/workflows/ci.yml`.
>
> Work that continues past this plan is tracked in [`survey/EXPANDED.md`](survey/EXPANDED.md):
> the expanded scene benchmark is measured at `n=6` of a planned `n=10`, because image generation
> is a manual adapter step.

## 1. Establish the project and contracts

- Add a Python 3.14+ `src/` package with a `llmpeg` console command.
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
- Render a provider-neutral generation prompt from an artifact. `llmpeg reconstruct` writes
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
mypy src tests scripts prototypeWebUI
pytest --cov=llmpeg --cov-report=term-missing --cov-fail-under=90
python -m build
```

## 6. Measure the measurements, then try to improve them

Added after the MVP shipped. The MVP proved the loop runs; this phase asks whether its numbers
mean anything and whether the encoder can improve itself.

- Time a full cycle against the live vision endpoint and publish the raw data
  (`scripts/benchmark_cycle.py` → `docs/benchmark-cycle.json`).
- Check whether the structural metrics track a human eye, using a vision-model judge as a
  stand-in reviewer (`scripts/perceptual_judge.py` → `docs/metrics.md`).
- Attempt GAN-shaped self-improvement: encoder proposes, critic attacks, misses steer the next
  round (`scripts/adversarial_refine.py` → `docs/adversarial.md`).
- Publish CI status, licence, and coverage badges in the README.

Exit gate: every claim above is backed by a checked-in JSON record that a reader can recompute,
and negative results are published as prominently as positive ones.

**Outcome: two of three answers were negative, and both are documented.** `visual_proxy_score`
correlates −0.47 with perceived similarity, and the adversarial loop failed because the critic
returned a constant verdict. The timing benchmark succeeded and also showed that re-encoding the
same image varies the compression ratio by 28%.

Still open: calibrate the judge against real human ratings; rebuild the critic as a pairwise
forced choice; finish the four ungenerated benchmark cases; trace their Commons URLs.

## Definition of done

The MVP is done when the offline suite passes, the real reference artifact has been produced by
the local vision model, a prompt-only Codex reconstruction and honest report are checked in, all
quality gates pass, the worktree is clean, and the conventional commit history tells the build
story in atomic steps.

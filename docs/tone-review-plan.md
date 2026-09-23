# Tone fix and single review page — status and remaining plan

## Update, later on 2026-09-23

The GPU came back, and steps 1–6 below are done. Findings are in [`tone.md`](tone.md):

- **Step 2, regions:** fixed. All 11 regions are distinct percentage boxes, and none copies the
  example box.
- **Step 4, tone:** **not fixed.** Saturation is unchanged for the keyboard cat (88) and high for
  the grass cat (126 vs. 89), and all renders are darker than their sources. Lowering CFG did not
  help. Hand-picked negative terms did move the numbers, but they are not yet a pipeline rule.
- **Step 5, page:** `survey/qwen.html` now shows one default-pipeline reconstruction per source
  from `survey/qwen/review/`, under a new title so old browser-stored ratings don't carry over.
- **Blocker and push warning:** resolved. The published page is now the new review page.

Encoding used local Ollama at `127.0.0.1:11434`, which has `qwen3.5:4b`; the remote host
doesn't. Steps 7 (release) and 8 (another human rating) remain open.

Started 2026-09-23 from the human survey response for the local Qwen-Image-2.1 page. Work stopped
part-way: the code is committed, but no new reconstructions exist yet because the GPU was down.

## Input: the survey response

Two cases were rated (`llmpeg-survey-response.json`, exported from the published page):

| Case | Subject | Composition | Colour, lighting, style | Overall | Comment |
| --- | ---: | ---: | ---: | ---: | --- |
| `qwen-monochrome-cat` | 5 | 5 | 3 | 5 | "the original is underexposed, the decompressed is too saturated. but else fit" |
| `qwen-keyboard-cat-holdout` | 5 | 5 | 3 | 5 | "the decompressed is too saturaed, the other is overexposed" |

Requests: adjust the prompts and the way composition and style are extracted, fix the
over-exposed look, and publish **one** review page instead of two, built with the Qwen tools.

This is one reviewer rating two cases. Treat it as a direction, not a measurement.

## Diagnosis: measured, not guessed

Pixel statistics on a 512-pixel thumbnail (mean Rec. 601 luminance, luminance standard
deviation, mean HSV saturation, all 0–255). Measured with PIL on the checked-in files:

| Image | Luminance | Contrast (std) | Saturation |
| --- | ---: | ---: | ---: |
| `sources/cat-monochrome.jpg` | 124.9 | 61.4 | 0.0 |
| `qwen/creator-rater/baseline.png` | 86.8 | 70.7 | 17.1 |
| `qwen/creator-rater/challenger-1.png` | 109.5 | 69.5 | 17.6 |
| `sources/cat-on-keyboard.jpg` | 147.9 | 55.2 | 48.1 |
| `qwen/creator-rater-holdout/baseline.png` | 113.3 | 72.7 | 78.5 |
| `qwen/creator-rater-holdout/challenger-1.png` | 122.4 | 73.7 | 88.4 |

- The reconstructions are **not** brighter. Mean luminance is lower in all four.
- They have **more contrast** (std 70–74 vs. 55–61) and **much more saturation**: the keyboard
  cat goes from 48 to 78–88, and the black-and-white source came back tinted (0 → 17).
- The "over-exposed" impression is therefore punchy grading, not brightness. The reviewer's own
  wording ("too saturated") matches the numbers.

Root causes in the pipeline:

1. Nothing in the artifact recorded grading. `style` was free text from a 4B vision model, e.g.
   *"vintage black and white photography with visible film grain and slight vignetting"* and, for
   the keyboard, *"Composition emphasizes intimacy between pet and technology…"*.
2. Composition regions were unusable: `{0:100}, {25:98}` instead of coordinates.
3. The Qwen workflow's negative prompt did nothing about saturation or contrast.

## Done (committed locally, not pushed)

| Commit | Change |
| --- | --- |
| `feat(codec): record pixel-measured tone in format 1.1` | New optional `tone` object (`luminance`, `contrast`, `saturation`, `warmth`), measured from pixels by the encoder. `FORMAT_MINOR` 0 → 1. The prompt gains a `Tone:` line in words plus numbers and a "do not brighten, add contrast, boost saturation, HDR" instruction. Mean saturation below 6 renders as "strictly black-and-white". 1.0 files without tone read and round-trip unchanged; a 1.0 file carrying tone is rejected. `docs/format.md` is updated. |
| `fix(codec): pin composition regions to percentage boxes` | Vision instruction: 3–6 covering regions, each exactly `x A-B%, y C-D%`; style limited to camera and light facts; exposure, contrast, and saturation left to the measurement. |
| `fix(codec): steer qwen away from over-saturated renders` | Workflow negative prompt adds `oversaturated, overexposed, HDR, excessive contrast, glow`. |
| `feat(survey): add single-page qwen review cycle` | `scripts/review_cycle.py`: for each cat source, encode → prompt → Qwen-Image 512 px seed 42 → evaluate, and write `report.json` with source vs. reconstruction tone. Default output `survey/qwen/review/`. |
| `ci(survey): publish only the qwen review page` | Pages deploy removes every other HTML page and publishes `survey/qwen.html` as `index.html`. The README no longer links the historical pages. |
| `docs: update test baseline to 182 tests` | 182 tests, 95.72% branch coverage. |

All five gates passed before committing: ruff format, ruff check, strict mypy, and pytest with
coverage. `python -m build` was **not** re-run in this session.

### Partial live check of the new instruction

One encode of `cat-on-keyboard.jpg` with local `qwen3.5:4b` on CPU took 4 min 56 s (plain
2,905 bytes, 211:1; gzip 1,558 bytes, 393:1). Result:

- Regions came back in the requested `x …%, y …%` form, and style became factual
  (*"close-up photography, slightly high angle … natural indoor lighting coming from above"*).
- **But** two regions copied the instruction's example box `x 0-45%, y 20-100%` verbatim. The
  example is now the placeholder `x A-B%, y C-D%` (in the committed version). The re-encode that
  would verify this was stopped unfinished, so **this fix is untested live**.
- The tone line rendered as intended: *"mid-tone exposure (mean luminance 148/255), moderate
  contrast (spread 55/255), natural, moderate colour with a neutral white balance (mean
  saturation 48/255)…"*.

## Blocker

The NVIDIA GPU was in a failed state: `nvidia-smi` reports "No devices were found", and the
kernel log shows GSP RPC failures with `GPU not in full power`. ComfyUI was not running. This
usually needs a reboot. Nothing below step 1 can run without it.

## Important: do not push the current state as-is

The Pages workflow now publishes only `survey/qwen.html`, but that page is still the **old**
baseline-plus-challenger comparison. Pushing now would remove the historical pages from the site
before the new single-reconstruction page exists. Finish steps 1–5 first, or push them together.

## Remaining plan

1. **Restore the GPU.** Reboot, confirm `nvidia-smi` lists the RTX A2000, and start ComfyUI:
   `cd ~/repos/ComfyUI && venv/bin/python main.py --lowvram --preview-method auto`.
2. **Verify the region-example fix.** Encode one source and check that no region repeats a fixed
   box:
   `uv run llmpeg encode survey/sources/cat-on-keyboard.jpg --profile detailed -o /tmp/k.llmpeg.json.gz`
   then `uv run llmpeg reconstruct /tmp/k.llmpeg.json.gz`.
3. **Run the review cycle** (about 3 × (encode + generate)):
   `uv run python scripts/review_cycle.py`. It writes artifacts, prompts, PNGs, per-case results,
   and `report.json` to `survey/qwen/review/`.
4. **Check the fix with numbers before claiming it.** Compare `source_tone` and
   `reconstruction_tone` in `report.json` with the table above. Success means reconstruction
   saturation close to the source (monochrome ≈ 0, keyboard near 48, not 78–88) and contrast
   near the source's. If saturation is still high, the next levers, in order, are: lower CFG
   from 3.5 (high CFG is a common cause of over-saturation), then a monochrome-specific negative
   prompt (`color, tint, sepia`) chosen by the renderer. Each needs its own measured run.
5. **Rebuild the single review page.** Rewrite `survey/qwen-manifest.json` with one case per
   source: set `reconstruction`, `artifact`, `prompt`, and `result` to the `survey/qwen/review/`
   files and drop `baseline_reconstruction`, `baseline_result`, `baseline_label`, and
   `comparison_label`. Copy `credit` from `survey/manifest.json`. Write each `finding` from the
   measured results only. Change the title so browser-stored ratings from the old page don't
   carry over (the storage key derives from it). Then:
   `uv run llmpeg survey survey/qwen-manifest.json --output survey/qwen.html --overwrite`.
6. **Update the documentation.** Add `survey/qwen/review/README.md` (provenance, settings,
   results). In `survey/qwen/README.md`, mark the creator/rater runs as superseded evidence.
   Update the tests in `tests/test_survey.py` that pin the current qwen manifest cases, and add
   gzip sizes via `scripts/measure_gzip.py` if the new artifacts belong in
   `docs/gzip-measurement.json`.
7. **Release decision (yours).** Format 1.1 is a reader-visible change. It fits a minor version
   bump (0.6.0: `_version.py`, `README.md`, `docs/format.md`). Run all five gates including
   `python -m build`, then commit. You handle the push.
8. **Ask for another human rating** on the new page. One reviewer's two ratings started this
   work; the tone fix is only confirmed once the colour/lighting score moves.

## Open questions

- Whether "one review page, not two" meant *one page on the site* (implemented) or *one
  reconstruction per case instead of baseline plus challenger* (planned in step 5). The plan
  delivers both.
- Whether the historical survey pages should also leave the repository. They are kept as
  evidence; only the site stops publishing them.

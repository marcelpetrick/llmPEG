# Code review

```
Base: v0.6.0 @ 52f4c4f   Head: f0ba51c
Files changed: 182   +8045 / -832 lines (code: 17 files, +1019 / -31)
```

The branch is `master`, so there is no separate integration branch; the base is the last release
before this session's feature work, `v0.6.0`, as requested. Most changed files are evidence and
documentation; the review covers the code under `src/`, `scripts/`, `tests/`, and the workflows.

## Findings

```
#1  HIGH  Code  src/llmpeg/grading.py:63
    match_tone scales HSV saturation until the render's mean equals the recorded mean HSV
    saturation, which overweights dark pixels, so a dark-background source drives the regrade far
    past its real colour (astronaut-crew colourfulness 73.7 -> 114.8) and a threefold boost tints
    near-grey areas (dogs-beach). Scale chroma in an opponent space toward a colourfulness target,
    with a capped gain, instead.

#2  MEDIUM  Architecture  src/llmpeg/encoder.py:132
    Format 1.1 persists mean HSV saturation as the artifact's only colour figure, and both
    corrections consume it (the loop added "vivid colors, saturated colors" to food-table, whose
    colourfulness was unchanged, 37.5 -> 38.0), so every artifact written now locks in a misleading
    contract. Add a colourfulness field in format 1.2, switch grading to it, and keep `saturation`
    for compatibility.

#3  LOW  Code  src/llmpeg/cli.py:209
    The loop's second render gets the full `--timeout` again, so `generate --tone-correction loop`
    can take up to twice the stated timeout without saying so. Share one deadline across both
    renders, or document that the timeout is per render.

#4  LOW  Code  src/llmpeg/cli.py:203
    The regraded PNG is saved without ComfyUI's embedded `prompt` text chunk and carries no record
    that it was regraded, so the file looks like a raw generator render. Copy the original PNG
    text chunks and add one naming the correction.

#5  LOW  Architecture  scripts/tone_rule_holdout.py:49
    The case lists, resolution, and snapshot phrase are re-declared in five tone scripts and have
    already drifted (the snapshot phrase ends with a full stop here and not in
    scripts/tone_prompt_sweep.py:42). Move the shared constants into one module the scripts import.

#6  LOW  Code  tests/test_survey.py:369
    The Pages test counts every "_site/" substring in the workflow, so an unrelated edit (a
    comment, another copy step) breaks it or lets a second page slip through. Assert the set of
    `cp … _site/…` destinations instead.
```

## Outcome

All six findings were fixed on master after this review (release 0.8.0):

| # | Fix |
| --- | --- |
| 1 | `match_tone` scales chroma in YCbCr toward `tone.colourfulness`, total gain capped at 0.5–2× (`src/llmpeg/grading.py`); astronaut-crew's worst overshoot fell from +41 to +1 |
| 2 | Format 1.2 records Hasler–Süsstrunk `tone.colourfulness`; grading steers colour by it and ignores HSV saturation; 1.1 files round-trip unchanged |
| 3 | `generate` computes one deadline; the loop's second render gets the remaining time and fails cleanly when none is left |
| 4 | The regraded PNG keeps the generator's text chunks and adds `llmpeg-tone-correction` |
| 5 | `scripts/tone_cases.py` holds the shared case lists, resolution, and snapshot phrase |
| 6 | The Pages test asserts the exact list of `_site/` copy destinations |

## Verdict

Mergeable for its default path — `--tone-correction` is opt-in and the default render is
unchanged — but #1 makes `--tone-correction match` produce visibly wrong colour, so fix #1 and #2
before recommending `match`, or disable it until then.

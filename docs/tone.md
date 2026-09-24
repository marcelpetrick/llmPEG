# Tone: why telling the generator "don't saturate" doesn't work

One human reviewer rated the first local Qwen-Image-2.1 reconstructions as "too saturated" (two
cases, colour/lighting/style 3 of 5; see [`tone-review-plan.md`](tone-review-plan.md)). This
page records what we tried and what the numbers say. Short version: **writing the tone into the
positive prompt did not bring saturation down, and neither did lowering guidance. Negative-prompt
terms did move it.**

This is three images at one seed. It shows which levers move the numbers; it does not show that
any lever makes a reconstruction look better to a person.

## What "tone" means here

`llmpeg.encoder.measure_tone` reduces an image to four numbers on a 256-pixel thumbnail:
mean Rec. 601 luminance, luminance standard deviation ("contrast"), mean HSV saturation (all
0–255), and warmth (mean red minus mean blue). The encoder stores them in the format 1.1 `tone`
object. Reconstructions are measured with the same function.

## Attempt 1: say it in the prompt

Format 1.1 renders the measured tone as a prompt line, words plus numbers, for example:

> Tone: mid-tone exposure (mean luminance 148/255), moderate contrast (spread 55/255), natural,
> moderate colour with a neutral white balance (mean saturation 48/255). Match this grading
> exactly: do not brighten, add contrast, boost saturation, or apply HDR, glow, or cinematic
> colour grading.

The workflow's negative prompt also gained `oversaturated, overexposed, HDR, excessive contrast,
glow`. Result ([`survey/qwen/review/`](../survey/qwen/review/README.md)):

| Case | Luminance | Contrast | Saturation | Warmth |
| --- | --- | --- | --- | --- |
| `cat-monochrome` | 125 → 67 | 61 → 62 | 0 → 11 | 0 → −1 |
| `cat-on-keyboard` | 148 → 111 | 55 → 46 | 48 → 88 | −5 → 40 |
| `cat-on-grass` | 158 → 124 | 24 → 33 | 89 → 126 | 51 → 47 |

The keyboard cat is as saturated as before the change (78.5–88.4 in the earlier holdout
run). All three renders are darker than their sources, and the keyboard's neutral desk came back
orange (warmth −5 → 40).

## Attempt 2: the sweep

`scripts/tone_sweep.py` keeps each review prompt **byte-for-byte fixed** and changes one generator
setting at a time. 512×512, seed 42, 30 steps, Euler, simple scheduler. Results from
[`survey/qwen/tone-sweep/measurements.json`](../survey/qwen/tone-sweep/measurements.json),
reconstruction values only (sources above):

| Case | Variant | Luminance | Contrast | Saturation | Warmth |
| --- | --- | ---: | ---: | ---: | ---: |
| `cat-monochrome` | default (CFG 3.5) | 67 | 62 | 11 | −1 |
| | CFG 2.5 | 68 | 61 | 11 | −1 |
| | CFG 1.5 | 67 | 61 | 9 | −1 |
| | tone negatives | 74 | 63 | 12 | −1 |
| `cat-on-keyboard` | default (CFG 3.5) | 111 | 46 | 88 | 40 |
| | CFG 2.5 | 110 | 46 | 89 | 40 |
| | CFG 1.5 | 113 | 51 | 91 | 42 |
| | tone negatives | 122 | 46 | **57** | **27** |
| `cat-on-grass` | default (CFG 3.5) | 124 | 33 | 126 | 47 |
| | CFG 2.5 | 123 | 31 | 137 | 49 |
| | CFG 1.5 | 117 | 29 | 154 | 55 |
| | tone negatives | 141 | 33 | **98** | 38 |

The `default` variant is a control: its three renders are pixel-identical to the review run's, so
at a fixed seed the generator is deterministic and the differences above come from the setting
alone.

What it shows:

- **Guidance scale is not the cause.** Lowering CFG from 3.5 to 1.5 leaves the keyboard's
  saturation flat (88 → 91) and makes the grass *more* saturated (126 → 154). High CFG is the
  usual suspect for over-saturation in diffusion models; here it isn't.
- **Negative terms work.** Case-specific negatives cut keyboard saturation from 88 to 57 (source
  48) and grass from 126 to 98 (source 89), cooled both, and brightened all three.
- **Monochrome barely moves.** Saturation 9–12 in every variant, luminance 67–74 against a source
  of 125. The render is a clean, dark studio black-and-white; the source is a faded snapshot.
  Nothing tried here reproduces that fading.

The negatives were **chosen by hand** after looking at the default renders (`orange tint` for the
keyboard, `neon green` for the grass). That is tuning on the test set. They are not yet a rule
the renderer could derive from an artifact, and a derived version needs its own measured run on
other sources before it goes into the pipeline.

## Why the positive prompt fails: a hypothesis, not a finding

The review prompts were never rendered *without* the tone line, so its effect is not isolated: the
earlier runs also used different artifacts. What follows is untested; treat it as a direction for
the next experiment. Qwen-Image-2.1 conditions on a text encoder that reads the prompt as a
description of *content*. Numbers such as "mean saturation 48/255" probably carry no visual meaning
for it, and negated instructions ("do not boost saturation") are a known weak spot of text-to-image
conditioning: the tokens `boost saturation` are still in the prompt. The negative prompt, by
contrast, is the one channel the sampler actively steers away from. The model's prior for "a photo
of a cat" also looks like modern, well-lit stock photography, which is darker, punchier, and more
saturated than these public-domain snapshots.

Two cheap checks would test this: remove the negated sentence and keep only the descriptive words;
and replace the numbers with plain descriptors ("muted, faded, washed-out colours").

## Status (2026-09-23)

Done and committed locally:

- The composition-region fix holds: the 11 regions across the three review artifacts are distinct
  percentage boxes, and none repeats the instruction's former example box.
- The tone fix does not: see the tables above.
- `survey/qwen.html` shows one **default**-pipeline reconstruction per source from
  `survey/qwen/review/`, because that is what `llmpeg` produces today. The hand-tuned negatives are
  evidence only. The page title changed, so ratings stored in a browser for the old page don't carry
  over.
- `generate_comfyui` accepts keyword-only `cfg` and `extra_negative` overrides, and
  `scripts/tone_sweep.py` reproduces the sweep.

Open, in order:

1. **Is tone really not controllable from the positive prompt?** Isolate it: the same artifact with
   the tone line removed, without the negated sentence, with words instead of numbers, and with the
   tone moved to the front of the prompt. Check what the ComfyUI text-encode node does with a long
   prompt, and what others report about Qwen-Image and saturation.
2. If negatives remain the only lever, derive them from the artifact's measured tone with a rule,
   and measure that rule on sources it was not tuned on.
3. Release decision: format 1.1 is reader-visible and fits 0.6.0.
4. Ask for another human rating. Whether any of this reads as better to a person is unmeasured,
   and the colour/lighting score is the test.

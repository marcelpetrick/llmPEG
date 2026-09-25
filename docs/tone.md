# Tone: why telling the generator "don't saturate" barely works

> **Correction (2026-09-24).** The *saturation* figures in attempts 1–6 are mean HSV saturation,
> which overstates colour in dark images: a near-black pixel with a faint tint counts as strongly
> saturated. Checked against perceptual colourfulness, the cats were **not** clearly
> over-saturated, and the first regrade over-coloured one source. Luminance, contrast, and warmth
> findings are unaffected. Format 1.2 now records colourfulness, and attempt 7 repeats the
> corrections with it. See [the correction](#correction-the-saturation-measure) before quoting any
> colour result below.

One human reviewer rated the first local Qwen-Image-2.1 reconstructions as "too saturated" (two
cases, colour/lighting/style 3 of 5; see [`tone-review-plan.md`](tone-review-plan.md)). This
page records what we tried and what the numbers say. Short version: **the positive prompt does
steer tone, but weakly. Against a prompt with no tone at all, writing the measured tone into it
removes about a quarter of the saturation error, and rewriting the prompt in the model's own
register about two fifths. Negative-prompt terms do far more, and they only work because this
workflow runs with CFG above 1, which Qwen's own settings do not.**

The first three attempts use three images at one seed. They show which levers move the numbers;
they do not show that any lever makes a reconstruction look better to a person.

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

## Attempt 3: is the prompt really powerless?

Attempt 1 changed the artifact and the prompt at once, so it never isolated the tone line.
`scripts/tone_prompt_sweep.py` does: it takes the three review artifacts, derives seven prompts
from each **by rule** (nothing is chosen per case), and renders every prompt under two settings,
the bundled workflow (CFG 3.5, 30 steps) and ComfyUI's official Qwen-Image-2.1 template (CFG 1,
25 steps). Evidence: [`survey/qwen/tone-prompts/`](../survey/qwen/tone-prompts/README.md). Its
`control` renders are pixel-identical to the review run's again.

| Prompt variant | What changes |
| --- | --- |
| `control` | the current llmPEG prompt |
| `no-tone` | the `Tone:` line removed |
| `no-negation` | the tone line without its "Match this grading exactly: do not …" sentence |
| `words-only` | as `no-negation`, and the `/255` numbers removed |
| `words-first` | the words-only tone moved to the top: "A photograph with …" |
| `snapshot` | a fixed phrase for every case in front of the tone words: "Casual unedited snapshot in soft natural light, understated and unpolished" |
| `observer` | the artifact rewritten as one observing paragraph in the register of Qwen's prompt rewriter (below): no labels, no hex codes, no canvas size, no instructions, lighting in its own sentence |

Reconstruction luminance / contrast / saturation / warmth. The last two columns add up the absolute
error against the three sources (125/61/0/0, 148/55/48/−5, 158/24/89/51):

| Setting | Variant | Monochrome | Keyboard | Grass | Σ\|Δ sat\| | Σ\|Δ lum\| |
| --- | --- | --- | --- | --- | ---: | ---: |
| CFG 3.5 | `control` | 67/62/11/−1 | 111/46/88/40 | 124/33/126/47 | 88 | 129 |
| | `no-tone` | 73/65/15/−1 | 123/51/95/48 | 106/33/142/39 | 115 | 129 |
| | `no-negation` | 68/61/11/−1 | 114/47/86/40 | 120/32/131/47 | 91 | 129 |
| | `words-only` | 69/62/15/−1 | 122/51/78/37 | 121/35/134/48 | 90 | 119 |
| | `words-first` | 72/62/11/−1 | 125/49/81/42 | 124/35/135/50 | 90 | 110 |
| | `snapshot` | 89/61/9/−2 | 121/47/73/37 | 126/35/120/42 | **65** | **95** |
| | `observer` | 78/59/16/−3 | 117/50/73/34 | 133/35/118/53 | 70 | 103 |
| CFG 1 | `control` | 67/61/8/0 | 116/51/96/45 | 114/28/172/64 | 139 | 134 |
| | `no-tone` | 74/63/8/0 | 125/54/103/52 | 91/27/187/53 | 161 | 141 |
| | `no-negation` | 69/60/7/0 | 118/52/96/45 | 106/27/176/60 | 142 | 138 |
| | `words-only` | 70/62/8/0 | 122/53/93/44 | 110/29/175/62 | 139 | 129 |
| | `words-first` | 68/60/6/0 | 127/57/91/46 | 119/31/172/67 | 132 | 117 |
| | `snapshot` | 86/57/4/0 | 128/51/85/45 | 120/31/157/59 | **109** | **97** |
| | `observer` | 79/59/8/0 | 119/55/83/37 | 129/30/157/70 | 111 | 104 |

For comparison, the hand-picked negatives of attempt 2 reach Σ|Δ sat| = 30 (12 + 9 + 9) at
CFG 3.5.

What it shows:

- **The tone line was never useless, only weak.** Removing it raises saturation in every colour
  case (Σ 88 → 115 at CFG 3.5, 139 → 161 at CFG 1). Attempt 1 could not see this because it had
  no tone-free control.
- **Negation and numbers don't matter much.** Dropping the "do not" sentence or the `/255` numbers
  moves Σ|Δ sat| by 1–3 at CFG 3.5; at CFG 1 moving the words to the front helps a little (139 →
  132). The PromptMaster finding that negation in the positive prompt backfires (below) does not
  show up here as a large effect.
- **Register and look words help most on the positive side.** The `snapshot` phrase and the
  `observer` paragraph cut the saturation error by a fifth to a quarter against `control` (88 →
  65–70) and also brighten (Σ|Δ lum| 129 → 95–103). They do not change the verdict: every colour
  render is still more saturated than its source.
- **The official CFG 1 is worse for tone.** Every variant is more saturated at CFG 1 than at 3.5,
  and the grass cat reaches 157–187 against a source of 89. The bundled CFG 3.5 was never
  justified in the repository (it arrived with the first local-model commit), but it happens to
  help: it is what lets the negative prompt act at all.
- **The monochrome cat stays dark.** 67–89 luminance against 125 in every variant. The model draws
  a crisp, high-contrast studio black-and-white; the source is a faded, over-exposed snapshot.
- **Content words carry colour.** The vision model described the grass as "bright green grass";
  the source's grass is pale and yellowish. A tone line cannot outvote the content description.
- `observer` also changes the grass cat's pose, a reminder that register changes content, not just
  tone.

## What the model expects: sources and code

Why is the positive prompt so weak? Three findings from reading the code and the published
material, none of them measured here beyond the sweep above:

- **The prompt reaches the model whole.** ComfyUI's `TextEncodeQwenImage21` does not truncate
  (`max_length` is effectively unlimited), wraps the prompt in a chat template with the system turn
  "Comprehend and analyze the provided prompt.", drops that system turn, and conditions the DiT on
  the last hidden layer of Qwen3-VL-8B over the user message
  (`comfy/text_encoders/qwen_image21.py` in the local ComfyUI checkout). The tone line is not lost;
  it is outweighed.
- **Qwen's own prompts look nothing like llmPEG's.** The
  [Qwen-Image-2.1 README](https://github.com/QwenLM/Qwen-Image-2.1) recommends running every prompt
  through its rewriting model, and the rewriter's
  [system prompt](https://huggingface.co/Qwen/Qwen-Image-2.1-PE-T2I) asks for "one long English
  paragraph that describes the finished image as if you were looking at it", "the description
  states what is in the frame, never what must be done", "Never write a ratio, a resolution",
  colours "with a modifier, almost never bare … Hex codes only if the user gave them", and a
  lighting sentence of its own. llmPEG's prompt is labelled sections, instructions, a canvas size,
  and hex codes. The `observer` variant approximates the rewriter's register without the rewriter.
- **Official settings disable the negative prompt.** ComfyUI's
  [official template](https://github.com/Comfy-Org/workflow_templates/blob/main/templates/image_qwen_image_2_1_t2i.json)
  samples 25 steps at CFG 1, and a community
  [Qwen-Image-2.1 prompt guide](https://github.com/kjranyone/qwen-image-2.1-prompt-guide) notes
  that "Distillation-style serving at guidance 1 ignores negatives entirely". A
  [PromptMaster article](https://blog.promptmaster.pro/posts/qwen-image-negative-prompts/) reports
  that Qwen-Image negatives failed to exclude *content* ("child") at any CFG, and that "Not a child"
  in the positive prompt produced more children; it does not say which Qwen-Image version it tested.
  Our measurements disagree for *tone*: at CFG 3.5, negatives moved saturation more than anything
  else.

## Attempt 4: a tone rule on sources it was not tuned on

`scripts/tone_rule_holdout.py` turns attempt 2's hand-picked negatives into `tone_negative()`, a
rule that reads only the artifact's measured tone, and renders each of the ten non-cat survey
sources three ways at CFG 3.5, seed 42. Evidence:
[`survey/qwen/tone-holdout/`](../survey/qwen/tone-holdout/README.md) (the run was stopped once and
resumed; `kitchen-table`'s re-render matched its first renders exactly).

Luminance / saturation, source → reconstruction:

| Source | Source | `control` | rule negatives | rule negatives + snapshot |
| --- | --- | --- | --- | --- |
| `amsterdam-market` | 89 / 60 | 62 / 141 | 55 / 134 | 65 / 122 |
| `astronaut-crew` | 59 / 169 | 28 / 138 | 26 / 130 | 20 / 124 |
| `dogs-beach` | 190 / 39 | 212 / 13 | 215 / 9 | 215 / 9 |
| `food-table` | 93 / 70 | 51 / 157 | 53 / 120 | 59 / 105 |
| `kitchen-table` | 100 / 46 | 76 / 123 | 78 / 116 | 81 / 109 |
| `living-room` | 192 / 17 | 215 / 7 | 218 / 4 | 211 / 5 |
| `mountain-hikers` | 138 / 64 | 145 / 42 | 158 / 37 | 163 / 44 |
| `street-bicycles` | 116 / 77 | 77 / 92 | 86 / 85 | 89 / 84 |
| `train-platform` | 56 / 46 | 34 / 47 | 33 / 56 | 40 / 61 |
| `workspace-books` | 168 / 77 | 190 / 49 | 198 / 42 | 192 / 46 |

Summed over the ten sources, rule plus snapshot cuts the saturation error from 378 to 320 and the
luminance error from 259 to 252; the rule's negatives alone make luminance worse (283). Per source
it is a coin toss: the saturation error falls for five (`food-table` 87 → 35, `amsterdam-market`
81 → 62, `kitchen-table` 77 → 63, `street-bicycles` 15 → 7, `mountain-hikers` 22 → 20) and rises
for the other five (`train-platform` 1 → 15, `astronaut-crew` 31 → 45, `dogs-beach` 26 → 30,
`workspace-books` 28 → 31, `living-room` 10 → 12).

The `control` column shows why. **In these ten sources, Qwen pushes exposure away from the
middle**: every source darker than 130 comes back darker (89 → 62, 59 → 28, 93 → 51, 100 → 76,
116 → 77, 56 → 34), and every brighter one comes back brighter (190 → 212, 192 → 215, 138 → 145,
168 → 190). Saturation mostly follows: the dark scenes gain it, the bright ones lose it. The cats do
not fit this pattern: the keyboard (148) and grass (158) cats are bright, yet came back darker (111,
124) and more saturated. So the direction of the miss differs from image to image, and one seed
cannot tell whether a pattern belongs to the scene or to the seed. A fixed rule cannot know in
advance which way a render will miss.

## Attempt 5: measure the render first, then correct

Attempt 4 showed that the direction of Qwen's miss depends on the image. Two corrections avoid
guessing it by measuring the render first; both read only the artifact's recorded tone, never the
source. They now live in `llmpeg.grading` and behind `llmpeg generate --tone-correction`:

- **`loop`**: render, measure the render's tone, and render once more at the same seed with
  negative-prompt terms chosen from the *sign* of each error beyond a margin (for example "dark,
  underexposed, dim" when the render is more than 12 below the recorded luminance).
- **`match`**: regrade the first render toward the recorded tone with global adjustments: one
  affine map on all channels for luminance and spread, an HSV saturation scale, and a red–blue
  shift for warmth.

`scripts/tone_feedback.py` ran all 13 survey sources at seeds 42, 7, and 1234. Evidence:
[`survey/qwen/tone-feedback/`](../survey/qwen/tone-feedback/README.md). Mean absolute error against
the recorded tone over the 39 source-seed pairs (0–255), plus the deterministic proxy scores against
the source:

| Variant | Luminance | Contrast | Saturation | Warmth | Visual proxy | Histogram similarity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `control` | 28.1 | 7.2 | 34.6 | 11.6 | 0.644 | 0.565 |
| `loop` | 22.3 | 6.4 | 24.9 | 8.8 | 0.660 | 0.607 |
| `match` | 0.4 | 0.2 | 1.1 | 0.1 | 0.673 | 0.661 |

- **The loop helps nearly everywhere.** It lowers the combined luminance and saturation error in
  37 of 39 pairs; the two exceptions are single seeds (`astronaut-crew` seed 7, 43 → 60;
  `dogs-beach` seed 1234, 39 → 40). The gain is about the same at every seed: mean saturation
  error 35.8 → 25.7, 33.0 → 24.5, and 34.8 → 24.5 at seeds 42, 7, and 1234. It costs a second
  render.
- **The miss belongs to the scene, not the seed.** For all 13 sources the `control` render misses
  luminance in the same direction at all three seeds. That is why a loop works where a fixed rule
  did not.
- **`match` hits the numbers by construction, so those four columns prove nothing.** The
  independent check is histogram similarity against the source, which `match` raises in 30 of 39
  pairs (the loop in 32). The contact sheet shows the catch: where the regrade has to add a lot of
  saturation or warmth it adds a visible cast, such as the keyboard cat turning bluish and the
  near-grey beach dogs turning orange.
- Proxy scores rise for both, but whether they track a human eye is unresolved
  ([`metrics.md`](metrics.md)).

## Attempt 6: ask the encoder not to intensify colours

The vision model called pale, yellowish grass "bright green grass". `scripts/tone_wording.py`
re-encoded all 13 sources with one extra instruction line, "Name each colour as it looks … never
intensify it with bright, vivid, lush, or rich unless that is unmistakable", and rendered each at
seed 42. Evidence: [`survey/qwen/tone-wording/`](../survey/qwen/tone-wording/README.md).

The intensifying words were rare to begin with: 3 across the 13 earlier artifacts (`bright`,
`vivid`, `lush`, `vibrant`, `brilliant`, `rich`, `saturated`), 2 after. Yet the renders moved a
lot, in both directions: mean saturation error 35.8 → 30.5 and luminance error 29.8 → 22.1, better
for 9 of 13 sources, but `astronaut-crew` went from 138 to 226 against a source of 169 and
`living-room` from 7 to 24 against 17. The mechanism the line targets barely changed, so the shift
comes from the whole description being rewritten, which moves content and tone together. One
seed of one re-encode cannot separate that from chance. **Not adopted**: the instruction is
unchanged.

## Correction: the saturation measure

`measure_tone` records saturation as mean HSV saturation, `(max − min) / max` per pixel. The
denominator is the pixel's brightness, so a dark pixel with a faint tint scores as strongly
saturated even though it looks nearly black. Qwen's renders are often darker than their sources,
so they *measure* more saturated than they look. `scripts/colourfulness_check.py` sets the
recorded figure beside the Hasler–Süsstrunk colourfulness metric (Hasler and Süsstrunk, 2003),
which works on opponent colour channels and does not divide by brightness. Seed 42, the seven
review-page sources ([`colourfulness-check.json`](colourfulness-check.json)):

| Source | HSV saturation: source → current | Colourfulness: source → current → loop → regraded | Near-black pixels, current |
| --- | --- | --- | ---: |
| `cat-monochrome` | 0 → 11 | 0.0 → 1.3 → 1.4 → 0.0 | 35.7% |
| `cat-on-keyboard` | 48 → 88 | 32.2 → 30.6 → 22.0 → 26.6 | 2.8% |
| `cat-on-grass` | 89 → 126 | 41.2 → 42.8 → 40.2 → 35.1 | 1.4% |
| `amsterdam-market` | 60 → 141 | 43.4 → 60.5 → 62.4 → 40.7 | 34.0% |
| `astronaut-crew` | 169 → 138 | 73.7 → 49.9 → 59.6 → **114.8** | 47.9% |
| `dogs-beach` | 39 → 13 | 30.1 → 11.4 → 13.5 → 32.2 | 1.1% |
| `food-table` | 70 → 157 | 37.5 → 38.0 → 36.1 → 34.4 | 42.9% |

What changes:

- **The cats were not clearly over-saturated.** By colourfulness the three current renders sit
  within 2 of their sources (the keyboard 32.2 → 30.6, the grass 41.2 → 42.8). The reviewer's "too
  saturated" is more likely the warm orange desk (warmth −5 → 40) and the darker, harder look.
  That is a hypothesis, not a measurement.
- **`food-table` was never over-saturated** (37.5 → 38.0), although HSV said 70 → 157: 42.9% of
  its current render is near-black. The loop added "vivid colors, saturated colors" to its
  negatives on a false reading.
- **Two sources really differ in colour:** `amsterdam-market` is more colourful (43.4 → 60.5) and
  `dogs-beach` far less (30.1 → 11.4). HSV saw the direction right for both.
- **The regrade over-coloured `astronaut-crew`** (73.7 → 114.8). A dark background (27.2% near-black
  pixels) lifts the source's HSV figure to 169, so matching it drove the render far past the
  source's real colour. For `dogs-beach` the overall figure matches (32.2 against 30.1), but a
  threefold saturation boost gives the near-grey sand and dogs a hue that was mostly noise.
- **Still sound:** everything about luminance, contrast, and warmth, and the scene-not-seed
  direction of the exposure miss. The loop's luminance gain (28.1 → 22.3) does not use saturation.

The fix — recording colourfulness in the artifact (format 1.2), steering the loop's colour terms
by it, and regrading chroma rather than HSV saturation — shipped in 0.8.0; attempt 7 measures it.

## Attempt 7: the corrections, judged by colourfulness

The 13 artifacts were upgraded to format 1.2 by re-measuring tone from their verified sources
(`scripts/upgrade_tone.py`), which leaves every prompt byte-identical, and attempt 5 was repeated
at seeds 42, 7, and 1234. Evidence:
[`survey/qwen/tone-feedback-v2/`](../survey/qwen/tone-feedback-v2/README.md). Mean absolute error
against the recorded tone over the 39 source-seed pairs:

| Variant | Luminance | Contrast | Colourfulness | Warmth | Visual proxy | Histogram similarity |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| `control` | 28.1 | 7.2 | 8.4 | 11.6 | 0.644 | 0.565 |
| `loop` | 21.3 | 6.3 | 8.2 | 9.5 | 0.659 | 0.611 |
| `match` | 0.9 | 0.1 | 1.6 | 0.0 | 0.666 | 0.637 |

- **Qwen's colour was never far off.** The current pipeline sits a mean 8.4 from its sources in
  colourfulness, where steps between Hasler and Süsstrunk's named categories are about 12. Its real
  miss is exposure, 28.1 on average.
- **The loop still helps.** It lowers the combined luminance-plus-colourfulness error in 35 of 39
  pairs, ties in 3, and is worse in 1; the luminance gain is about the same at every seed (29.8 →
  22.8, 25.8 → 19.2, 28.7 → 21.9 at seeds 42, 7, 1234). It no longer adds "vivid colors, saturated
  colors" on a false reading: food-table and the keyboard cat now get only exposure, contrast, and
  warmth terms.
- **The regrade no longer over-colours.** Its largest colourfulness overshoot is now 1 (it was
  +41 on `astronaut-crew`). The 2× chroma cap stops the beach dogs at 16 against a source of 30
  rather than tinting the sand. Its global warmth shift still gives the keyboard cat and the food a
  cool cast, which matches the sources' measured warmth but is visible.
- Histogram similarity for `match` fell from 0.661 to 0.637 because it no longer over-boosts
  colour; neither figure is a perception score.


## Attempt 8: describe colourfulness in the prompt (rejected)

The `Tone:` line still quotes mean HSV saturation. One change was tested: for format 1.2 artifacts,
name colour with Hasler and Süsstrunk's category words and the colourfulness figure instead. Across
the 13 upgraded artifacts at seeds 42 and 7, the `control` render's mean colourfulness error went
from 7.9 to 8.2 — better for 6 of 26 pairs, worse for 12 — and luminance did not move (27.8 →
28.1). Not adopted. Evidence:
[`survey/qwen/tone-colour-words/`](../survey/qwen/tone-colour-words/README.md). This fits attempt 3:
the positive prompt's tone words barely steer Qwen either way.

## Attempt 9: Qwen's own register, with the loop

Attempt 3 found the `observer` prompt, written in the register of Qwen's prompt rewriter, the best
positive-prompt lever at one seed. Repeated on all 13 format 1.2 artifacts at seeds 42 and 7, and
combined with the loop (evidence:
[`survey/qwen/tone-observer/`](../survey/qwen/tone-observer/README.md)); pipeline-prompt figures are
the same seeds from attempt 7:

| Prompt | Variant | Luminance | Contrast | Colourfulness | Warmth | Visual proxy |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| pipeline | `control` | 27.8 | 7.2 | 7.9 | 11.6 | 0.646 |
| observer | `control` | 20.7 | 8.2 | 8.2 | 9.5 | 0.670 |
| pipeline | `loop` | 21.0 | 6.1 | 7.9 | 9.6 | 0.659 |
| observer | `loop` | **14.9** | 6.8 | **7.3** | **8.0** | **0.687** |

- **The register matters more than any tone wording.** The observer prompt alone lowers the
  luminance error as much as the loop does (27.8 → 20.7), and it beats the pipeline prompt on the
  combined luminance-plus-colourfulness error in 21 of 26 pairs.
- **The two levers add up.** Observer plus loop is the best result on this page: luminance error
  14.9, about half the pipeline's 27.8, and better than pipeline plus loop in 20 of 26 pairs.
- **Content held up by eye**, and on one case improved: the astronaut crew came back as six people,
  as in the source, where the pipeline prompt drew three. The grass cat's pose changed, and some of
  the workspace desk's labels were lost — expected, because the observer prompt leaves out the
  critical-text list.
- **Not adopted yet.** Before it replaces the pipeline prompt it needs a variant that keeps
  critical text (and a text-recall check on the expanded benchmark), and a human rating.

## Attempt 10: keep the text, then ship the register as an opt-in

The observer prompt leaves out the critical-text list. `observer-text` adds one sentence quoting it
the way Qwen's rewriter copies visible text (`The visible text reads "…", "…".`), skipping
multi-line or over-long entries. Rendered at seeds 42 and 7 on the 13 artifacts, its tone matches
the plain observer prompt (with the loop: luminance error 14.9, colourfulness 7.3). Text survival
was read from the `control` renders by the local vision model — a model-read measure, not OCR,
applied identically to all three prompts (evidence:
[`survey/qwen/tone-observer-text/`](../survey/qwen/tone-observer-text/README.md)):

| Prompt | Critical strings found (8 sources × 2 seeds) |
| --- | ---: |
| pipeline | 27 / 78 |
| observer | 13 / 78 |
| observer-text | 25 / 78 |

Leaving the text out halves what survives; quoting it restores nearly all of it. On these numbers
`observer-text` keeps the pipeline's text and halves its exposure miss with the loop, so it ships
in 0.9.0 as `llmpeg reconstruct|generate --prompt-style observer` (`render_observer_prompt`, which
renders byte-identical prompts to the measured script for all 13 artifacts). It is opt-in: the
default stays the pipeline prompt until a person has rated the difference.

A first run of the text check scored almost nothing for every prompt because 36 of 48 replies were
empty: this Qwen build answered in `message.thinking`. That run was discarded, the reader fixed,
and empty replies now stop the script instead of being scored as lost text.

## Status (2026-09-24)

- `llmpeg generate --tone-correction loop|match` is an **opt-in** since 0.7.0; 0.8.0 steers its
  colour by colourfulness. `--prompt-style observer` (0.9.0) is the other opt-in; together they
  gave the best result measured here. The default render is unchanged.
- `survey/qwen.html` (the site index) is the one review page: original, current pipeline, and the
  v2 `loop`, for seven sources at seed 42, with each artifact's JSON and stored gzip bytes. It
  exists for human ratings; nothing on this page says a correction *looks* closer.
- The remaining plan is in [`plan.md`](plan.md#11-tone-work).

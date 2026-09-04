# Expanded scene benchmark

This benchmark asks a harder question than the cat survey: what survives when a scene contains
**many objects, several people, and readable text**?

Ten complex sources were encoded with the `detailed` profile, reconstructed from their rendered
prompts alone, and evaluated. **The study is complete at `n = 10`.** Every generator run received
only the text in `prompts/<case>-expanded.txt` — never the source image.

Open [`expanded.html`](expanded.html) for the visual pairs, exact prompts, machine metrics, and
per-case licensing.

## Measured results (`n = 10`, `detailed` profile)

| Case | Source bytes | Artifact bytes | Ratio | Visual proxy | Layout | Palette dist. | Text recall | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| astronaut-crew | 640,005 | 3,276 | 195:1 | 0.732 | 0.770 | 0.054 | 0.50 | **fail** |
| food-table | 379,957 | 2,028 | 187:1 | 0.639 | 0.681 | 0.162 | 1.00 | pass |
| amsterdam-market | 742,058 | 2,920 | 254:1 | 0.718 | 0.661 | 0.069 | 1.00 | pass |
| train-platform | 333,386 | 3,721 | 90:1 | 0.715 | 0.755 | 0.049 | 1.00 | pass |
| workspace-books | 541,310 | 2,980 | 182:1 | 0.952 | 0.982 | 0.028 | 1.00 | pass |
| dogs-beach | 533,079 | 2,752 | 194:1 | 0.693 | 0.661 | 0.058 | 1.00 | pass |
| mountain-hikers | 800,010 | 2,399 | 333:1 | 0.764 | 0.763 | 0.099 | 1.00 | pass |
| street-bicycles | 1,299,141 | 3,964 | 328:1 | 0.706 | 0.731 | 0.064 | 1.00 | pass |
| kitchen-table | 548,012 | 3,014 | 182:1 | 0.751 | 0.766 | 0.067 | 1.00 | pass |
| living-room | 251,650 | 3,439 | 73:1 | 0.700 | 0.692 | 0.043 | 1.00 | pass |

| Aggregate | Value |
| --- | ---: |
| Cases measured | 10 of 10 |
| Passing all thresholds | 9 |
| Failing a threshold | 1 (astronaut-crew, critical-text recall) |
| Mean visual proxy | 0.737 |
| Mean layout score | 0.746 |
| Mean palette distance | 0.069 |
| Mean dHash similarity | 0.553 |
| Mean critical-text recall | 0.950 |

## What this shows

**Text survives far better than expected.** Nine of ten cases recalled every critical string.
The `train-platform` reconstruction rendered `1`, `山手線`, `Yamanote Line`, `東京・上野・駒込方面`
and `for Tokyo Ueno & Komagome` correctly, including the Japanese. `kitchen-table` reproduced
`MASON` embossed on a jar; `living-room` reproduced a full book title and subtitle.

**Identity still does not survive.** The one failure is the one that depends on *who* is in the
picture: `astronaut-crew` recalled half its critical text and invented the rest, turning six
specific people into six plausible ones. That is the same result the `n = 6` checkpoint found, and
it did not improve with the four new cases.

**Object inventory and broad layout survive.** `workspace-books` — a static desk, no people, no
small lettering — scores 0.952 visual proxy, still the best result anywhere in this repository.

**Difficulty tracks scene busyness, not file size.** `living-room` has the smallest source
(251 KB) and the worst ratio (73:1); `mountain-hikers` has the largest (800 KB) and the best
(333:1). A near-empty corner needs more words per byte of source than a mountain does.

## Two caveats about the text-recall figure

**Recall does not punish invention.** `critical_text_recall` measures how many expected strings
appear; nothing penalises text the generator made up. `street-bicycles` scores 1.00 while also
displaying an invented bike number (`22894`) next to the real ones, and `workspace-books` scores
1.00 while adding an LG logo that is not in the source. A precision measure would score both
lower.

**Duplicate expected strings inflate it.** `street-bicycles` lists `22624` five times in its
critical text; because matching is a substring test, one rendered `22624` satisfies all five. The
metric would read the same if four of the five bicycles were unnumbered.

Transcripts were produced by reading each reconstruction by eye, the same method the README
documents for the article demo — llmPEG consumes OCR text but ships no OCR engine.

## Sources and licensing

Every benchmark image is freely licensed media from Wikimedia Commons. Attribution below was read
from each file's own Commons record, not assumed.

| Case | Author | License | Commons record |
| --- | --- | --- | --- |
| astronaut-crew | Robert Markowitz | Public domain (NASA) | [Expedition 53 crew portrait](https://commons.wikimedia.org/wiki/File:Expedition_53_crew_portrait.jpg) |
| food-table | www.Pixel.la Free Stock Photos | CC0 1.0 | [Table with food](https://commons.wikimedia.org/wiki/File:Table_with_food.jpg) |
| amsterdam-market | Fons Heijnsbroek | CC0 1.0 | [Albert Cuyp market stall](https://commons.wikimedia.org/wiki/File:2023_Amsterdam_-_a_fruit_market_stall_at_the_Albert_Cuyp_market_in_the_sunlight_with_a_lot_of_city_people_walking_and_shopping_-_free_download_photo_in_Dutch_street_photography_by_Fons_Heijnsbroek,_Netherlands.tif) |
| train-platform | Redd Angelo | CC0 1.0 | [People waiting for the train](https://commons.wikimedia.org/wiki/File:People_waiting_for_the_train_(Unsplash).jpg) |
| workspace-books | Aleks Dorohovich | CC0 1.0 | [Books, pencils, laptop and iphone on a desk](https://commons.wikimedia.org/wiki/File:Books,_pencils,_laptop,_and_iphone_on_a_desk_(Unsplash).jpg) |
| dogs-beach | Mark Galer | CC0 1.0 | [Two dogs playing on the beach](https://commons.wikimedia.org/wiki/File:Two_dogs_playing_on_the_beach_(Unsplash).jpg) |
| mountain-hikers | Galen Crout | CC0 1.0 | [Adventurous Mountain Hikes](https://commons.wikimedia.org/wiki/File:Adventurous_Mountain_Hikes_(Unsplash).jpg) |
| street-bicycles | Retired electrician | CC0 1.0 | [Moscow, Nizhnyaya Krasnokholmskaya Street bicycles](https://commons.wikimedia.org/wiki/File:Moscow,_Nizhnyaya_Krasnokholmskaya_Street_bicycles_May_2023_01.jpg) |
| kitchen-table | **unknown** | **not verified** | not yet traced |
| living-room | **unknown** | **not verified** | not yet traced |

### How the last two attributions were recovered, and why two are still missing

The Commons URLs for four sources were never recorded when they were downloaded. Rather than guess,
they were searched for on Commons and each candidate was **verified by perceptual hash** against
the local copy — a match only counts at a dHash similarity of 1.000, meaning the same photograph.

Two were recovered that way: `mountain-hikers` and `street-bicycles`, both exact matches.

Three search passes failed to find `kitchen-table` and `living-room`; the best candidates scored
0.56–0.64, which is noise. They are labelled **unverified** in the gallery rather than being
quietly credited or quietly removed, because the honest failure is more useful than either. They
must be traced before this benchmark is published anywhere that asserts licensing, and the
[`AGENTS.md`](../AGENTS.md) media rule stands: no further image enters this repository without
recorded provenance.

Benchmark copies were resized to at most 1920 pixels on the longest edge for tractable local
processing. Sources are otherwise unmodified, and their SHA-256 hashes are embedded in the
corresponding `.llmpeg.json` artifacts.

## Reproducing

```bash
uv run llmpeg evaluate survey/sources/<case>.jpg survey/reconstructions/<case>-expanded.png \
  --artifact survey/artifacts/<case>-expanded.llmpeg.json \
  --ocr-text survey/results/<case>-expanded.ocr.txt \
  --output survey/results/<case>-expanded.json --overwrite
uv run llmpeg survey survey/expanded-manifest.json --output survey/expanded.html --overwrite
```

Reconstructions were generated with `codex exec` driving its built-in image tool, from a directory
containing only the prompt file, so the generator could not see the source image.

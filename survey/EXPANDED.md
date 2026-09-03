# Expanded scene benchmark

This benchmark asks a harder question than the cat survey: what survives when a scene contains
**many objects, several people, and readable text**?

Ten complex sources were encoded with the `detailed` profile. **Six have been reconstructed and
measured. Four are encoded but not yet generated**, so this is an evidence checkpoint, not a
finished ten-case study. The aggregates below are `n=6` and are reported as such.

Open [`expanded.html`](expanded.html) for the visual pairs, exact prompts, machine metrics, and
per-case licensing.

## Measured results (`n=6`, `detailed` profile)

| Case | Source bytes | Artifact bytes | Ratio | Visual proxy | Layout | Palette dist. | Text recall | Verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| astronaut-crew | 640,005 | 3,276 | 195:1 | 0.732 | 0.770 | 0.054 | 0.50 | **fail** |
| food-table | 379,957 | 2,028 | 187:1 | 0.639 | 0.681 | 0.162 | 1.00 | pass |
| amsterdam-market | 742,058 | 2,920 | 254:1 | 0.718 | 0.661 | 0.069 | 1.00 | pass |
| train-platform | 333,386 | 3,721 | 90:1 | 0.715 | 0.755 | 0.049 | n/a | incomplete |
| workspace-books | 541,310 | 2,980 | 182:1 | 0.952 | 0.982 | 0.028 | n/a | incomplete |
| dogs-beach | 533,079 | 2,752 | 194:1 | 0.693 | 0.661 | 0.058 | 1.00 | pass |

| Aggregate | Value |
| --- | ---: |
| Cases measured | 6 of 10 planned |
| Passing all thresholds | 3 |
| Failing a threshold | 1 (astronaut-crew, critical-text recall) |
| Incomplete (no OCR transcript supplied) | 2 |
| Mean visual proxy | 0.741 |
| Mean layout score | 0.752 |
| Mean palette distance | 0.070 |
| Mean dHash similarity | 0.557 |

`incomplete` is not a pass. The `detailed` profile requires critical-text recall, and
`train-platform` and `workspace-books` have no transcript checked in, so that check reports
`not_evaluated` and the case cannot be called a pass.

## What this shows

**Object inventory and broad layout survive.** The mean layout score (0.752) is the strongest
signal in the set, and `workspace-books` — a static desk scene with no people and no small
lettering — scores 0.952 visual proxy, the best result anywhere in this repository.

**Identity, counts, and small text do not survive.** `astronaut-crew` fails on exactly the axis
that matters for a crew portrait: it recalls half the critical text (0.50), inventing names and
mission numbers rather than reproducing them. Six specific people become six plausible people.

**Difficulty tracks scene busyness, not file size.** `train-platform` has the smallest source
(333 KB) and the worst ratio (90:1), because a platform full of people and signage needs more
description per byte of source than a desk does.

The next codec optimization targets follow from this: human identity, small text, logos, object
counts, and fine geometry.

## Remaining work

Four sources are encoded, have rendered prompts, and are waiting on image generation:
`kitchen-table`, `living-room`, `mountain-hikers`, and `street-bicycles`. Generation is a manual
adapter step — llmPEG deliberately ships no image generator — so completing them needs an
operator to run each `prompts/<case>-expanded.txt` through a generator and save the PNG to
`reconstructions/<case>-expanded.png`.

After that:

```bash
uv run llmpeg evaluate survey/sources/<case>.jpg survey/reconstructions/<case>-expanded.png \
  --artifact survey/artifacts/<case>-expanded.llmpeg.json \
  --output survey/results/<case>-expanded.json
uv run llmpeg survey survey/expanded-manifest.json --output survey/expanded.html --overwrite
```

Add the new case to `expanded-manifest.json` with its Commons credit block, and update the
aggregates above. Supplying an OCR transcript as `results/<case>-expanded.ocr.txt` and passing
`--ocr-text` promotes an `incomplete` verdict to a real pass or fail.

## Sources and licensing

Every benchmark image is freely licensed media from Wikimedia Commons. Attribution below was
read from each file's Commons record, not assumed.

| Case | Author | License | Commons record |
| --- | --- | --- | --- |
| astronaut-crew | Robert Markowitz | Public domain (NASA) | [Expedition 53 crew portrait](https://commons.wikimedia.org/wiki/File:Expedition_53_crew_portrait.jpg) |
| food-table | www.Pixel.la Free Stock Photos | CC0 1.0 | [Table with food](https://commons.wikimedia.org/wiki/File:Table_with_food.jpg) |
| amsterdam-market | Fons Heijnsbroek | CC0 1.0 | [Albert Cuyp market stall](https://commons.wikimedia.org/wiki/File:2023_Amsterdam_-_a_fruit_market_stall_at_the_Albert_Cuyp_market_in_the_sunlight_with_a_lot_of_city_people_walking_and_shopping_-_free_download_photo_in_Dutch_street_photography_by_Fons_Heijnsbroek,_Netherlands.tif) |
| train-platform | Redd Angelo | CC0 1.0 | [People waiting for the train](https://commons.wikimedia.org/wiki/File:People_waiting_for_the_train_(Unsplash).jpg) |
| workspace-books | Aleks Dorohovich | CC0 1.0 | [Books, pencils, laptop and iphone on a desk](https://commons.wikimedia.org/wiki/File:Books,_pencils,_laptop,_and_iphone_on_a_desk_(Unsplash).jpg) |
| dogs-beach | Mark Galer | CC0 1.0 | [Two dogs playing on the beach](https://commons.wikimedia.org/wiki/File:Two_dogs_playing_on_the_beach_(Unsplash).jpg) |

The four not-yet-generated sources (`kitchen-table`, `living-room`, `mountain-hikers`,
`street-bicycles`) also came from Wikimedia Commons records marked CC0 or public domain, but their
individual Commons URLs were not recorded when they were downloaded. **Those URLs must be restored
before those cases are published**, so that every image in this repository carries verifiable
provenance.

Benchmark copies were resized to at most 1920 pixels on the longest edge for tractable local
processing. Sources are otherwise unmodified, and their SHA-256 hashes are embedded in the
corresponding `.llmpeg.json` artifacts.

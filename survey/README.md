# Cat reconstruction survey

This is a reproducible, exploratory `n=3` llmPEG quality survey. Open `index.html` directly in
a browser. Human ratings are stored only in that browser's `localStorage` until the reviewer uses
**Export my ratings**.

## Sources and licenses

All three source photographs are hosted by Wikimedia Commons and were released into the public
domain by their copyright holders:

| Local file | Work | Creator | Commons record |
| --- | --- | --- | --- |
| `cat-on-grass.jpg` | *Cat full length.jpg* | Clavecin | [source and license](https://commons.wikimedia.org/wiki/File:Cat_full_length.jpg) |
| `cat-on-keyboard.jpg` | *Wikipedians cat.jpg* | Remedios44 | [source and license](https://commons.wikimedia.org/wiki/File:Wikipedians_cat.jpg) |
| `cat-monochrome.jpg` | *Cat bw-photo.jpg* | Barmanru | [source and license](https://commons.wikimedia.org/wiki/File:Cat_bw-photo.jpg) |

`manifest.json` is the machine-readable provenance record. Source files are preserved unmodified;
their SHA-256 hashes are also embedded in the corresponding `.llmpeg.json` artifacts.

## Method

1. Encode each source with `qwen3-vl:32b-ctx49k`, seed 42, temperature 0, and the `balanced`
   fidelity profile.
2. Render its canonical artifact into a generator-neutral prompt.
3. Normalize the rendered fields into the production prompt saved as `*.imagegen.txt`, then
   generate one reconstruction with Codex's built-in image generation from that exact text only.
   The source images were not supplied to the generator as references.
4. Evaluate aspect ratio, dHash, RGB histogram, edge density, layout proxy, and symmetric dominant
   palette distance.
5. Generate `index.html` from the manifest, artifacts, prompts, and evaluation JSON.

The refined run uses the `detailed` profile and identity-oriented extraction instructions. It
records normalized subject geometry, distinctive markings, pose landmarks, camera treatment, and
specific drift constraints. It is versioned alongside the baseline instead of replacing it.

| Case | Balanced visual proxy | Detailed visual proxy | Change |
| --- | ---: | ---: | ---: |
| Grass | 0.595 | 0.579 | -0.016 |
| Keyboard | 0.699 | 0.751 | +0.051 |
| Monochrome | 0.706 | 0.725 | +0.019 |

The detailed run improves two of three structural scores, but only the keyboard result changes
materially. Its text check fails because exact keyboard legends were not reproduced. Treat the
HTML's human identity rating as the deciding signal; the deterministic proxies mostly measure
layout, tone, and texture rather than whether this is recognizably the same cat.

Run step 5 with:

```bash
uv run llmpeg survey survey/manifest.json --output survey/index.html --overwrite
uv run llmpeg survey survey/detailed-manifest.json --output survey/detailed.html --overwrite
```

The checked-in outputs are evidence for this run. Regeneration may differ because the image model
is non-deterministic and model versions can change.

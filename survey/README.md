# Cat reconstruction survey

This is a reproducible, exploratory `n=3` PromptPress quality survey. Open `index.html` directly in
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
their SHA-256 hashes are also embedded in the corresponding `.ppress.json` artifacts.

## Method

1. Encode each source with `qwen3-vl:32b-ctx49k`, seed 42, temperature 0, and the `balanced`
   fidelity profile.
2. Render its canonical artifact into a generator-neutral prompt.
3. Generate one reconstruction with Codex's built-in image generation from that prompt only. The
   source images were not supplied to the generator as references.
4. Evaluate aspect ratio, dHash, RGB histogram, edge density, layout proxy, and symmetric dominant
   palette distance.
5. Generate `index.html` from the manifest, artifacts, prompts, and evaluation JSON.

Run step 5 with:

```bash
uv run promptpress survey survey/manifest.json --output survey/index.html --overwrite
```

The checked-in outputs are evidence for this run. Regeneration may differ because the image model
is non-deterministic and model versions can change.

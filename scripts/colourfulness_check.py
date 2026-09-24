"""Check the recorded saturation figure against a perceptual colourfulness measure.

`llmpeg.encoder.measure_tone` records saturation as mean HSV saturation, `(max - min) / max` per
pixel. That ratio grows large for dark pixels with a faint tint, so darker images measure as more
saturated than they look. This script sets it beside the Hasler-Süsstrunk colourfulness metric
(Hasler and Süsstrunk, "Measuring colourfulness in natural images", 2003), which works on the
opponent channels rg = R - G and yb = (R + G)/2 - B and does not divide by brightness.

It covers the seven sources on the review page: each source, its current-pipeline render, and the
seed-42 closed-loop and regraded renders. Output: `docs/colourfulness-check.json`.
"""

from __future__ import annotations

import json
import math
import statistics
from pathlib import Path
from typing import Any, cast

from PIL import Image, ImageStat

REPO = Path(__file__).resolve().parent.parent
SAMPLE_PIXELS = 256  # the same thumbnail size measure_tone uses
DARK = 40  # a pixel whose brightest channel is below this counts as near-black
CASES = {
    "cat-monochrome": "survey/qwen/review/cat-monochrome.png",
    "cat-on-keyboard": "survey/qwen/review/cat-on-keyboard.png",
    "cat-on-grass": "survey/qwen/review/cat-on-grass.png",
    "amsterdam-market": "survey/qwen/tone-holdout/amsterdam-market-control.png",
    "astronaut-crew": "survey/qwen/tone-holdout/astronaut-crew-control.png",
    "dogs-beach": "survey/qwen/tone-holdout/dogs-beach-control.png",
    "food-table": "survey/qwen/tone-holdout/food-table-control.png",
}


def measure(path: Path) -> dict[str, float]:
    with Image.open(path) as opened:
        image = opened.convert("RGB")
    image.thumbnail((SAMPLE_PIXELS, SAMPLE_PIXELS))
    pixels = cast(list[tuple[int, int, int]], list(image.get_flattened_data()))
    rg = [r - g for r, g, _ in pixels]
    yb = [(r + g) / 2 - b for r, g, b in pixels]
    colourfulness = math.hypot(statistics.pstdev(rg), statistics.pstdev(yb)) + 0.3 * math.hypot(
        statistics.fmean(rg), statistics.fmean(yb)
    )
    dark = sum(max(pixel) < DARK for pixel in pixels) / len(pixels)
    saturation = ImageStat.Stat(image.convert("HSV").getchannel("S")).mean[0]
    return {
        "hsv_saturation": round(saturation, 1),
        "colourfulness": round(colourfulness, 1),
        "near_black_percent": round(dark * 100, 1),
    }


def main() -> None:
    rows: list[dict[str, Any]] = []
    for case, current in CASES.items():
        images = {
            "source": f"survey/sources/{case}.jpg",
            "current": current,
            "loop": f"survey/qwen/tone-feedback/{case}-s42-loop.png",
            "regraded": f"survey/qwen/tone-feedback/{case}-s42-matched.png",
        }
        for variant, path in images.items():
            rows.append({"case": case, "variant": variant, "image": path, **measure(REPO / path)})
            print(case, variant, rows[-1])
    result = {
        "method": "Hasler-Suesstrunk colourfulness vs mean HSV saturation, 256 px thumbnail",
        "near_black_threshold": DARK,
        "rows": rows,
    }
    (REPO / "docs/colourfulness-check.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

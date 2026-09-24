"""Tone corrections for reconstructions, driven by the artifact's recorded tone.

Qwen-Image-2.1 misses a source's exposure and colour in a direction that depends on the scene, not
the seed, so neither correction guesses the direction; both measure the render first
(`docs/tone.md`, attempt 5). Neither reads the source image: the target is the `tone` object the
encoder stored in the artifact.

Colour is steered by `tone.colourfulness` (format 1.2), never by `tone.saturation`: mean HSV
saturation divides by brightness and reads dark pixels as vividly coloured (`docs/tone.md`,
correction). An artifact without colourfulness gets no colour correction at all.
"""

from __future__ import annotations

from PIL import Image

from llmpeg.artifact import Tone
from llmpeg.encoder import MONOCHROME_SATURATION, measure_tone

# An error inside these margins is left alone. Luminance, contrast, and warmth are on a 0-255
# scale; colourfulness steps of about 12 separate Hasler and Suesstrunk's named categories.
FEEDBACK_MARGIN = {"luminance": 12, "contrast": 8, "colourfulness": 8, "warmth": 12}
# Negative-prompt terms for a render that is too high (first) or too low (second) on each measure.
FEEDBACK_TERMS = {
    "luminance": ("overexposed, too bright", "dark, underexposed, dim"),
    "contrast": ("harsh contrast, deep black shadows", "flat, hazy, low contrast"),
    "colourfulness": (
        "vivid colors, saturated colors",
        "dull colors, desaturated, grey, washed out",
    ),
    "warmth": ("warm color cast, orange tint, yellow tint", "cool color cast, blue tint"),
}
MONOCHROME_TERMS = "color, colour, tint, sepia"
MATCH_ROUNDS = 6
# The regrade never scales chroma beyond these bounds in total: a large boost turns a near-grey
# area's noise into a visible hue, and a large cut drains a scene the generator got right.
MAX_CHROMA_GAIN = 2.0
MIN_CHROMA_GAIN = 0.5


def _is_monochrome(tone: Tone) -> bool:
    # A grayscale source measures exactly 0 HSV saturation, so this test stays reliable.
    return tone.saturation < MONOCHROME_SATURATION


def feedback_negative(target: Tone, rendered: Tone) -> str:
    """Negative terms that push each measure of a render back toward the recorded tone."""
    monochrome = _is_monochrome(target)
    terms: list[str] = []
    if monochrome and not _is_monochrome(rendered):
        terms.append(MONOCHROME_TERMS)
    for name, (too_high, too_low) in FEEDBACK_TERMS.items():
        if monochrome and name in {"colourfulness", "warmth"}:
            continue
        wanted, measured = getattr(target, name), getattr(rendered, name)
        if wanted is None or measured is None:
            continue
        error = measured - wanted
        if error > FEEDBACK_MARGIN[name]:
            terms.append(too_high)
        elif error < -FEEDBACK_MARGIN[name]:
            terms.append(too_low)
    return ", ".join(terms)


def match_tone(image: Image.Image, target: Tone) -> Image.Image:
    """Regrade an image toward a recorded tone with global, deterministic adjustments.

    Each round applies one affine map to all three channels (which sets mean luminance and its
    spread exactly, before clipping), scales chroma around neutral grey in YCbCr (which scales
    colourfulness proportionally and leaves brightness alone), and shifts red against blue for
    warmth. Clipping makes one round inexact, so it repeats. Chroma gain is capped overall.
    """
    graded = image.convert("RGB")
    chroma_gain = 1.0
    for _ in range(MATCH_ROUNDS):
        now = measure_tone(graded)
        gain = target.contrast / max(now.contrast, 1)
        offset = target.luminance - now.luminance * gain
        graded = graded.point(lambda value, g=gain, o=offset: round(value * g + o))
        if _is_monochrome(target):
            graded = graded.convert("L").convert("RGB")
            continue
        if target.colourfulness is not None:
            current = measure_tone(graded).colourfulness or 0
            wanted = target.colourfulness / max(current, 1) if current else 1.0
            step = min(MAX_CHROMA_GAIN / chroma_gain, max(MIN_CHROMA_GAIN / chroma_gain, wanted))
            chroma_gain *= step
            luma, blue_diff, red_diff = graded.convert("YCbCr").split()
            blue_diff = blue_diff.point(lambda level, k=step: round(128 + (level - 128) * k))
            red_diff = red_diff.point(lambda level, k=step: round(128 + (level - 128) * k))
            graded = Image.merge("YCbCr", (luma, blue_diff, red_diff)).convert("RGB")
        shift = (target.warmth - measure_tone(graded).warmth) / 2
        red, green, blue = graded.split()
        red = red.point(lambda level, d=shift: round(level + d))
        blue = blue.point(lambda level, d=shift: round(level - d))
        graded = Image.merge("RGB", (red, green, blue))
    return graded

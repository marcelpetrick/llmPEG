"""Tone corrections for reconstructions, driven by the artifact's recorded tone.

Qwen-Image-2.1 misses a source's exposure and colour in a direction that depends on the scene, not
the seed, so neither correction guesses the direction; both measure the render first
(`docs/tone.md`, attempt 5). Neither reads the source image: the target is the `tone` object the
encoder stored in the artifact.
"""

from __future__ import annotations

from PIL import Image

from llmpeg.artifact import Tone
from llmpeg.encoder import MONOCHROME_SATURATION, measure_tone

# An error inside these margins (0-255 scale) is left alone.
FEEDBACK_MARGIN = {"luminance": 12, "contrast": 8, "saturation": 12, "warmth": 12}
# Negative-prompt terms for a render that is too high (first) or too low (second) on each measure.
FEEDBACK_TERMS = {
    "luminance": ("overexposed, too bright", "dark, underexposed, dim"),
    "contrast": ("harsh contrast, deep black shadows", "flat, hazy, low contrast"),
    "saturation": ("vivid colors, saturated colors", "dull colors, desaturated, grey, washed out"),
    "warmth": ("warm color cast, orange tint, yellow tint", "cool color cast, blue tint"),
}
MONOCHROME_TERMS = "color, colour, tint, sepia"
MATCH_ROUNDS = 6


def feedback_negative(target: Tone, rendered: Tone) -> str:
    """Negative terms that push each measure of a render back toward the recorded tone."""
    monochrome = target.saturation < MONOCHROME_SATURATION
    terms: list[str] = []
    if monochrome and rendered.saturation >= MONOCHROME_SATURATION:
        terms.append(MONOCHROME_TERMS)
    for name, (too_high, too_low) in FEEDBACK_TERMS.items():
        if monochrome and name in {"saturation", "warmth"}:
            continue
        error = getattr(rendered, name) - getattr(target, name)
        if error > FEEDBACK_MARGIN[name]:
            terms.append(too_high)
        elif error < -FEEDBACK_MARGIN[name]:
            terms.append(too_low)
    return ", ".join(terms)


def match_tone(image: Image.Image, target: Tone) -> Image.Image:
    """Regrade an image toward a recorded tone with global, deterministic adjustments.

    Each round applies one affine map to all three channels (which sets mean luminance and its
    spread exactly, before clipping), scales HSV saturation, and shifts red against blue for
    warmth. Clipping makes one round inexact, so it repeats. A strong saturation or warmth change
    can add a visible colour cast that the four numbers do not show.
    """
    graded = image.convert("RGB")
    for _ in range(MATCH_ROUNDS):
        now = measure_tone(graded)
        gain = target.contrast / max(now.contrast, 1)
        offset = target.luminance - now.luminance * gain
        graded = graded.point(lambda value, g=gain, o=offset: round(value * g + o))
        if target.saturation < MONOCHROME_SATURATION:
            graded = graded.convert("L").convert("RGB")
            continue
        scale = target.saturation / max(measure_tone(graded).saturation, 1)
        hue, saturation, value = graded.convert("HSV").split()
        saturation = saturation.point(lambda level, k=scale: round(level * k))
        graded = Image.merge("HSV", (hue, saturation, value)).convert("RGB")
        shift = (target.warmth - measure_tone(graded).warmth) / 2
        red, green, blue = graded.split()
        red = red.point(lambda level, d=shift: round(level + d))
        blue = blue.point(lambda level, d=shift: round(level - d))
        graded = Image.merge("RGB", (red, green, blue))
    return graded

from __future__ import annotations

from dataclasses import replace

from PIL import Image

from llmpeg.artifact import Tone
from llmpeg.encoder import measure_tone
from llmpeg.grading import FEEDBACK_TERMS, MONOCHROME_TERMS, feedback_negative, match_tone

TARGET = Tone(luminance=120, contrast=40, saturation=60, warmth=0, colourfulness=40)


def gradient(colour: tuple[int, int, int]) -> Image.Image:
    """A horizontal ramp from black to the colour, so it has spread and saturation to adjust."""
    image = Image.new("RGB", (64, 32))
    for x in range(64):
        shade = tuple(round(channel * x / 63) for channel in colour)
        for y in range(32):
            image.putpixel((x, y), shade)
    return image


def test_feedback_is_silent_inside_the_margins() -> None:
    assert feedback_negative(TARGET, replace(TARGET, luminance=131, saturation=49)) == ""


def test_feedback_pushes_each_measure_back_toward_the_target() -> None:
    high = feedback_negative(TARGET, Tone(160, 60, 100, 30, colourfulness=60))
    low = feedback_negative(TARGET, Tone(80, 20, 20, -30, colourfulness=20))

    assert high == ", ".join(terms[0] for terms in FEEDBACK_TERMS.values())
    assert low == ", ".join(terms[1] for terms in FEEDBACK_TERMS.values())


def test_feedback_for_a_monochrome_target_names_colour_not_saturation() -> None:
    target = Tone(luminance=120, contrast=40, saturation=0, warmth=0)
    rendered = Tone(luminance=120, contrast=40, saturation=30, warmth=25)

    assert feedback_negative(target, rendered) == MONOCHROME_TERMS
    assert feedback_negative(target, replace(rendered, saturation=3)) == ""


def test_match_tone_lands_on_the_recorded_tone() -> None:
    graded = match_tone(gradient((250, 120, 40)), TARGET)
    tone = measure_tone(graded)

    assert abs(tone.luminance - TARGET.luminance) <= 2
    assert abs(tone.contrast - TARGET.contrast) <= 2
    assert tone.colourfulness is not None
    assert abs(tone.colourfulness - 40) <= 3
    assert abs(tone.warmth - TARGET.warmth) <= 2


def test_feedback_ignores_saturation_and_needs_colourfulness_on_both_sides() -> None:
    no_colourfulness = replace(TARGET, colourfulness=None)
    rendered = Tone(120, 40, 200, 0, colourfulness=90)

    assert feedback_negative(no_colourfulness, rendered) == ""
    assert feedback_negative(TARGET, replace(rendered, colourfulness=None)) == ""
    assert feedback_negative(TARGET, replace(rendered, colourfulness=44)) == ""


def test_match_tone_caps_the_chroma_boost() -> None:
    image = gradient((140, 120, 110))
    before = measure_tone(image).colourfulness
    graded = measure_tone(match_tone(image, replace(TARGET, colourfulness=200)))

    assert before is not None and graded.colourfulness is not None
    assert graded.colourfulness <= 2 * before + 2


def test_match_tone_without_colourfulness_leaves_chroma_alone() -> None:
    image = gradient((250, 120, 40))
    own = measure_tone(image)
    graded = measure_tone(match_tone(image, replace(own, colourfulness=None)))

    assert own.colourfulness is not None and graded.colourfulness is not None
    assert abs(graded.colourfulness - own.colourfulness) <= 1

from __future__ import annotations

from dataclasses import replace

from PIL import Image

from llmpeg.artifact import Tone
from llmpeg.encoder import measure_tone
from llmpeg.grading import FEEDBACK_TERMS, MONOCHROME_TERMS, feedback_negative, match_tone

TARGET = Tone(luminance=120, contrast=40, saturation=60, warmth=0)


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
    high = feedback_negative(TARGET, Tone(luminance=160, contrast=60, saturation=100, warmth=30))
    low = feedback_negative(TARGET, Tone(luminance=80, contrast=20, saturation=20, warmth=-30))

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
    assert abs(tone.saturation - TARGET.saturation) <= 3
    assert abs(tone.warmth - TARGET.warmth) <= 2


def test_match_tone_renders_a_monochrome_target_without_colour() -> None:
    target = Tone(luminance=100, contrast=50, saturation=0, warmth=0)
    graded = match_tone(gradient((40, 200, 90)), target)

    assert measure_tone(graded).saturation == 0
    assert abs(measure_tone(graded).luminance - target.luminance) <= 2


def test_match_tone_does_not_modify_its_input() -> None:
    image = gradient((250, 120, 40))
    before = image.tobytes()
    match_tone(image, TARGET)
    assert image.tobytes() == before

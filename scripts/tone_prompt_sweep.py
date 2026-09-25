"""Isolate whether the positive prompt can steer Qwen-Image-2.1's tone at all.

`tone_sweep.py` varied generator settings with the prompt fixed. This sweep does the opposite: it
derives prompt variants from each review artifact by rule (never per case), and renders every
variant under two settings, the workflow's own and ComfyUI's official Qwen-Image-2.1 template
(CFG 1, 25 steps; at CFG 1 the negative prompt has no effect). Each render's tone is measured with
the encoder's own function.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import re
from collections.abc import Callable
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from PIL import Image
from tone_cases import CATS, RESOLUTION, SNAPSHOT_PHRASE

from llmpeg import __version__
from llmpeg.artifact import Artifact
from llmpeg.encoder import measure_tone, render_generation_prompt
from llmpeg.generators import DEFAULT_COMFYUI_HOST, DEFAULT_QWEN_SEED, generate_comfyui

REPO = Path(__file__).resolve().parent.parent
CASES = CATS
SETTINGS: dict[str, dict[str, Any]] = {
    "workflow": {"cfg": None, "steps": None},
    "official": {"cfg": 1.0, "steps": 25},
}
TONE_LINE = re.compile(r"^Tone: .*\n", re.MULTILINE)
NEGATED = re.compile(r" Match this grading exactly:.*$")
NUMBERS = re.compile(r" \([^()]*\d+/255\)")
PREAMBLE = "Create a new image from this semantic description.\n\n"
SNAPSHOT = SNAPSHOT_PHRASE


def _tone_words(prompt: str) -> str:
    match = TONE_LINE.search(prompt)
    if match is None:
        raise SystemExit("review prompt has no Tone: line")
    line = match.group(0).removeprefix("Tone: ").rstrip("\n")
    return NUMBERS.sub("", NEGATED.sub("", line)).rstrip(".")


def _no_tone(artifact: Artifact) -> str:
    return render_generation_prompt(replace(artifact, tone=None))


def _no_negation(artifact: Artifact) -> str:
    prompt = render_generation_prompt(artifact)
    return TONE_LINE.sub(lambda m: NEGATED.sub("", m.group(0).rstrip("\n")) + "\n", prompt)


def _words_only(artifact: Artifact) -> str:
    prompt = render_generation_prompt(artifact)
    return TONE_LINE.sub(f"Tone: {_tone_words(prompt)}\n", prompt)


def _words_first(artifact: Artifact) -> str:
    prompt = render_generation_prompt(artifact)
    body = TONE_LINE.sub("", prompt).removeprefix(PREAMBLE)
    return f"{PREAMBLE}A photograph with {_tone_words(prompt)}.\n{body}"


def _snapshot(artifact: Artifact) -> str:
    prompt = render_generation_prompt(artifact)
    body = TONE_LINE.sub("", prompt).removeprefix(PREAMBLE)
    return f"{PREAMBLE}{SNAPSHOT}; {_tone_words(prompt)}.\n{body}"


def _observer(artifact: Artifact) -> str:
    """Rewrite the artifact in the register of Qwen's own prompt-rewriting model.

    Its system prompt asks for one paragraph that observes the finished image rather than
    instructs a renderer, names no resolution or ratio, uses hex codes only when a user gave
    them, and gives the lighting its own sentence. Critical text is left out: this variant tests
    tone, and the keyboard artifact's text list is malformed.
    """
    words = _tone_words(render_generation_prompt(artifact))
    summary = artifact.summary.rstrip(".")
    summary = summary[0].lower() + summary[1:] if summary[:2].lower() == "a " else summary
    regions = " ".join(region.description.rstrip(".") + "." for region in artifact.composition)
    return (
        f"The image is a square realistic photograph: {summary}. "
        f"{artifact.generation_prompt.strip()} {regions} "
        f"The lighting is {artifact.style.rstrip('.')}. "
        f"The photograph has {words}."
    )


# Longer or multi-line entries are malformed lists the vision model wrote, not visible text.
MAX_TEXT = 60


def _observer_text(artifact: Artifact) -> str:
    """The observer paragraph plus the critical text, quoted the way the rewriter does."""
    texts = []
    for entry in artifact.critical_text:
        text = entry.strip().strip('"').strip()
        if text and "\n" not in text and len(text) <= MAX_TEXT:
            texts.append(f'"{text}"')
    base = _observer(artifact)
    return f"{base} The visible text reads {', '.join(texts)}." if texts else base


PROMPTS: dict[str, Callable[[Artifact], str]] = {
    "control": render_generation_prompt,
    "no-tone": _no_tone,
    "no-negation": _no_negation,
    "words-only": _words_only,
    "words-first": _words_first,
    "snapshot": _snapshot,
    "observer": _observer,
    "observer-text": _observer_text,
}


def run(args: argparse.Namespace) -> dict[str, Any]:
    review_dir = args.review_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, Any]] = []
    for setting in args.settings:
        options = SETTINGS[setting]
        for variant in args.prompts:
            for case in CASES:
                artifact = Artifact.from_file_bytes(
                    (review_dir / f"{case}.llmpeg.json.gz").read_bytes()
                )
                prompt = PROMPTS[variant](artifact)
                stem = f"{case}-{setting}-{variant}"
                _write(output_dir / f"{stem}.prompt.txt", prompt.encode(), args.overwrite)
                image = generate_comfyui(
                    prompt,
                    RESOLUTION,
                    args.seed,
                    args.comfyui_host,
                    cfg=options["cfg"],
                    steps=options["steps"],
                )
                _write(output_dir / f"{stem}.png", image, args.overwrite)
                with Image.open(io.BytesIO(image)) as rendered:
                    tone = asdict(measure_tone(rendered))
                source = asdict(artifact.tone) if artifact.tone else None
                rows.append(
                    {
                        "case": case,
                        "setting": setting,
                        "prompt_variant": variant,
                        "prompt": f"{stem}.prompt.txt",
                        "image": f"{stem}.png",
                        "source_tone": source,
                        "reconstruction_tone": tone,
                    }
                )
                print(f"{stem}: {source} -> {tone}", flush=True)

    result = {
        "llmpeg_version": __version__,
        "generator": "local ComfyUI/Qwen-Image-2.1",
        "artifacts": str(review_dir.relative_to(REPO)),
        "resolution": RESOLUTION,
        "seed": args.seed,
        "settings": {
            name: {k: v for k, v in options.items() if v is not None}
            for name, options in SETTINGS.items()
        },
        "snapshot_phrase": SNAPSHOT,
        "rows": rows,
    }
    _write(
        output_dir / "measurements.json",
        (json.dumps(result, indent=2, sort_keys=True) + "\n").encode(),
        args.overwrite,
    )
    return result


def _write(path: Path, content: bytes, overwrite: bool) -> None:
    with path.open("wb" if overwrite else "xb") as stream:
        stream.write(content)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-dir", type=Path, default=REPO / "survey/qwen/review")
    parser.add_argument("--output-dir", type=Path, default=REPO / "survey/qwen/tone-prompts")
    parser.add_argument("--settings", nargs="+", default=list(SETTINGS), choices=list(SETTINGS))
    parser.add_argument("--prompts", nargs="+", default=list(PROMPTS), choices=list(PROMPTS))
    parser.add_argument(
        "--comfyui-host", default=os.environ.get("LLMPEG_COMFYUI_HOST", DEFAULT_COMFYUI_HOST)
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_QWEN_SEED)
    parser.add_argument("--overwrite", action="store_true")
    run(parser.parse_args())


if __name__ == "__main__":
    main()

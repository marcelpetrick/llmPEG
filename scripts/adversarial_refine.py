"""Improve extraction with a GAN-shaped loop: an encoder proposes, a critic attacks.

This is not a GAN. There are no gradients and no trained discriminator. It borrows the
*shape* of adversarial training, which is the part that transfers to a prompt-based codec:

    generator  = the extraction instruction (what the vision model is told to capture)
    critic     = a vision model that sees the ORIGINAL image plus only the rendered
                 generation prompt, and reports what a generator would get wrong
    signal     = the critic's misses, aggregated into an extra focus instruction
    next round = re-encode with that focus, then attack again

The loop optimises **artifact sufficiency** — how much of what the critic says matters is
actually captured in the text — because llmPEG ships no image generator and cannot close the
loop on pixels. That is a proxy objective, and it is reported as one.

Every round is written to the output JSON: the focus instruction used, the artifact size, the
critic's score and its individual misses. Nothing is summarised away, so a reader can audit
whether a round genuinely improved anything or merely spent bytes.

Usage:
    uv run python scripts/adversarial_refine.py --rounds 3 --output docs/adversarial-rounds.json
"""

from __future__ import annotations

import argparse
import base64
import collections
import io
import json
import os
import statistics
import sys
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

from llmpeg.artifact import FidelityProfile
from llmpeg.encoder import encode_image, render_generation_prompt
from llmpeg.providers import OllamaVisionProvider

REPO = Path(__file__).resolve().parent.parent
MAX_EDGE = 1024

CASES: tuple[tuple[str, str], ...] = (
    ("cat-on-grass", "survey/sources/cat-on-grass.jpg"),
    ("astronaut-crew", "survey/sources/astronaut-crew.jpg"),
    ("train-platform", "survey/sources/train-platform.jpg"),
)

CRITIC_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "reconstructability": {"type": "integer", "minimum": 1, "maximum": 5},
        "misses": {
            "type": "array",
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "aspect": {
                        "type": "string",
                        "enum": [
                            "subject_identity",
                            "person_count",
                            "object_count",
                            "spatial_layout",
                            "readable_text",
                            "colour_or_lighting",
                            "camera_geometry",
                            "fine_detail",
                        ],
                    },
                    "severity": {"type": "integer", "minimum": 1, "maximum": 5},
                    "detail": {"type": "string", "maxLength": 200},
                },
                "required": ["aspect", "severity", "detail"],
            },
        },
    },
    "required": ["reconstructability", "misses"],
}

CRITIC_INSTRUCTION = """/no_think
You are the adversary for a lossy semantic image codec. The attached image is the ORIGINAL.
Below is the ENTIRE text an image generator will receive. The generator will never see the
original image.

Your job is to find where the description is insufficient. For each problem, name the aspect,
rate how badly it would damage the reconstruction (severity 1-5), and say concretely what is
missing or wrong. Then rate reconstructability 1-5: how faithfully could a competent generator
reproduce this specific image from this text alone?

Be adversarial and specific. "Could be more detailed" is useless; "the description says 'people
waiting' but there are exactly four, two of them children" is useful.

Report AT MOST 6 misses, worst first. Keep every "detail" under 200 characters. Reply with
JSON only and nothing else.

--- GENERATION PROMPT BEGINS ---
{prompt}
--- GENERATION PROMPT ENDS ---"""


def _encoded(path: Path) -> str:
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((MAX_EDGE, MAX_EDGE))
        buffer = io.BytesIO()
        rgb.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def critique(host: str, model: str, timeout: float, source: Path, prompt: str) -> Any:
    """Attack one rendered prompt with the original image in view."""
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": CRITIC_SCHEMA,
        "keep_alive": "30m",
        "options": {"temperature": 0.0, "seed": 42, "num_predict": 8192},
        "messages": [
            {
                "role": "user",
                "content": CRITIC_INSTRUCTION.format(prompt=prompt),
                "images": [_encoded(source)],
            }
        ],
    }
    request = urllib.request.Request(
        host.rstrip("/") + "/api/chat",
        json.dumps(payload).encode("utf-8"),
        {"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        raw = json.load(response)
    message = raw.get("message") or {}
    content = (message.get("content") or "").strip() or (message.get("thinking") or "").strip()
    if content.startswith("```"):
        lines = content.splitlines()
        if lines[-1].strip() == "```":
            content = "\n".join(lines[1:-1]).removeprefix("json").lstrip()
    try:
        return json.loads(content)
    except json.JSONDecodeError as error:
        # A truncated critique is unusable: fail loudly rather than scoring a partial verdict.
        raise SystemExit(
            f"critic returned invalid JSON ({error}); done_reason="
            f"{raw.get('done_reason', 'unknown')}, {len(content)} chars received"
        ) from error


ASPECT_DIRECTIVE = {
    "subject_identity": (
        "State what makes each subject individually identifiable: proportions, markings and their "
        "boundaries, clothing, and anything that separates this subject from others of its kind."
    ),
    "person_count": "State the exact number of people and each one's position, age band and pose.",
    "object_count": "State exact counts for every repeated object group, not vague quantities.",
    "spatial_layout": "Give each major element an approximate x/y position and relative size.",
    "readable_text": (
        "Transcribe every legible string verbatim, with its location and relative size."
    ),
    "colour_or_lighting": (
        "Name the light direction, hardness, colour temperature and shadow shape."
    ),
    "camera_geometry": "State camera height, angle, distance and apparent focal length.",
    "fine_detail": "Describe surface texture and material for the largest visible areas.",
}


def build_focus(misses: list[dict[str, Any]], top: int = 3) -> str:
    """Turn the critic's aggregated misses into a deterministic focus instruction."""
    weighted: collections.Counter[str] = collections.Counter()
    for miss in misses:
        weighted[str(miss["aspect"])] += int(miss["severity"])
    chosen = [aspect for aspect, _ in weighted.most_common(top) if aspect in ASPECT_DIRECTIVE]
    if not chosen:
        return ""
    lines = [f"- {ASPECT_DIRECTIVE[aspect]}" for aspect in chosen]
    return (
        "A critic found these the most damaging omissions in previous runs. Prioritise them, "
        "staying inside the byte budget:\n" + "\n".join(lines)
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rounds", type=int, default=3)
    parser.add_argument(
        "--profile", choices=list(FidelityProfile), default=FidelityProfile.DETAILED
    )
    parser.add_argument("--model", default="qwen3-vl:32b-ctx49k")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    host = os.environ.get("OLLAMA_VISION_HOST")
    if not host:
        print("OLLAMA_VISION_HOST is not set; the loop needs a reachable endpoint.")
        return 2

    profile = FidelityProfile(args.profile)
    focus = ""
    rounds: list[dict[str, Any]] = []

    for round_index in range(args.rounds):
        provider = OllamaVisionProvider(host, args.model, args.timeout, extra_instruction=focus)
        cases: list[dict[str, Any]] = []
        all_misses: list[dict[str, Any]] = []
        for name, relative in CASES:
            print(f"round {round_index}: {name} ...", flush=True)
            source = REPO / relative
            artifact = encode_image(source, provider, profile)
            prompt = render_generation_prompt(artifact)
            verdict = critique(host, args.model, args.timeout, source, prompt)
            misses = list(verdict.get("misses", []))
            all_misses.extend(misses)
            cases.append(
                {
                    "case": name,
                    "artifact_bytes": len(artifact.to_bytes()),
                    "source_bytes": source.stat().st_size,
                    "reconstructability": verdict["reconstructability"],
                    "miss_count": len(misses),
                    "severe_miss_count": sum(1 for m in misses if int(m["severity"]) >= 4),
                    "misses": misses,
                }
            )

        rounds.append(
            {
                "round": round_index,
                "focus_instruction": focus,
                "cases": cases,
                "mean_reconstructability": round(
                    statistics.fmean(float(c["reconstructability"]) for c in cases), 3
                ),
                "mean_artifact_bytes": round(
                    statistics.fmean(float(c["artifact_bytes"]) for c in cases), 1
                ),
                "total_severe_misses": sum(int(c["severe_miss_count"]) for c in cases),
            }
        )
        focus = build_focus(all_misses)

    report = {
        "model": args.model,
        "profile": profile.value,
        "objective": (
            "artifact sufficiency judged by an adversarial critic, not reconstructed-image "
            "quality: llmPEG ships no generator, so the loop cannot be closed on pixels"
        ),
        "rounds": rounds,
    }
    text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {args.output}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())

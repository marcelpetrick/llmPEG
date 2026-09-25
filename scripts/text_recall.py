"""Measure how much of each artifact's critical text survives in renders from different prompts.

No OCR engine is installed, so the local Ollama vision model transcribes each render's legible
text at temperature 0 and seed 42. That makes this a model-read measurement, not ground truth: a
string the model misreads counts as lost. Every prompt variant is read the same way, so the
comparison between variants is fair even where the absolute figures are not.

Recall uses llmPEG's own rule (a case-insensitive substring match) against the same cleaned list
of expected strings for every variant: the artifact's `critical_text` without wrapping quotes, and
without multi-line or over-long entries, which are malformed lists rather than visible text.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import urllib.request
from pathlib import Path
from typing import Any

from tone_cases import CATS, HOLDOUT
from tone_prompt_sweep import MAX_TEXT

from llmpeg.artifact import Artifact
from llmpeg.providers import DEFAULT_OLLAMA_VISION_HOST, DEFAULT_VISION_MODEL

REPO = Path(__file__).resolve().parent.parent
INSTRUCTION = (
    "/no_think\nTranscribe every piece of legible text visible in this image exactly as written, "
    "one item per line. Do not describe the image. If there is no legible text, reply NONE."
)


def expected_text(artifact: Artifact) -> list[str]:
    texts = []
    for entry in artifact.critical_text:
        text = entry.strip().strip('"').strip()
        if text and "\n" not in text and len(text) <= MAX_TEXT:
            texts.append(text)
    return texts


def transcribe(image: Path, host: str, model: str, timeout: float) -> str:
    body = {
        "model": model,
        "stream": False,
        "keep_alive": 0,
        "options": {"temperature": 0, "seed": 42},
        "messages": [
            {
                "role": "user",
                "content": INSTRUCTION,
                "images": [base64.b64encode(image.read_bytes()).decode("ascii")],
            }
        ],
    }
    request = urllib.request.Request(
        host.rstrip("/") + "/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        reply = json.loads(response.read())
    return str(reply["message"]["content"]).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--variant",
        action="append",
        required=True,
        metavar="NAME=DIR",
        help="a prompt variant and the directory holding its <case>-s<seed>-control.png renders",
    )
    parser.add_argument("--artifacts-dir", type=Path, required=True)
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 7])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--host", default=os.environ.get("OLLAMA_VISION_HOST", DEFAULT_OLLAMA_VISION_HOST)
    )
    parser.add_argument("--model", default=os.environ.get("LLMPEG_MODEL", DEFAULT_VISION_MODEL))
    parser.add_argument("--timeout", type=float, default=300.0)
    args = parser.parse_args()

    variants = dict(item.split("=", 1) for item in args.variant)
    rows: list[dict[str, Any]] = []
    for case in (*CATS, *HOLDOUT):
        artifact = Artifact.from_file_bytes(
            (args.artifacts_dir / f"{case}.llmpeg.json.gz").read_bytes()
        )
        expected = expected_text(artifact)
        if not expected:
            continue
        for seed in args.seeds:
            for name, folder in variants.items():
                image = Path(folder) / f"{case}-s{seed}-control.png"
                transcript = transcribe(image, args.host, args.model, args.timeout)
                folded = transcript.casefold()
                found = [text for text in expected if text.casefold() in folded]
                rows.append(
                    {
                        "case": case,
                        "seed": seed,
                        "variant": name,
                        "expected": expected,
                        "found": found,
                        "recall": round(len(found) / len(expected), 3),
                        "transcript": transcript,
                    }
                )
                print(f"{case} s{seed} {name}: {len(found)}/{len(expected)}", flush=True)
    result = {
        # Model name only: the endpoint host is never recorded.
        "reader": f"ollama/{args.model}",
        "instruction": INSTRUCTION,
        "rows": rows,
    }
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", "utf-8")


if __name__ == "__main__":
    main()

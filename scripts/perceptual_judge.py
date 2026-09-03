"""Score reconstruction pairs with a vision-model judge standing in for a human reviewer.

llmPEG's `visual_proxy_score` is a blend of cheap structural signals (dHash, histogram,
edge density, aspect). Nothing in the repository establishes that those signals track what
a person actually notices. This script provides an independent second opinion: it shows a
vision model the source and the reconstruction side by side and asks it to rate them the
way a reviewer would, then reports how well each machine metric agrees.

It is a proxy for a human, not a human. Treat the output as a second opinion that can be
audited case by case, never as ground truth.

Usage:
    uv run python scripts/perceptual_judge.py --output docs/perceptual-judge.json
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import statistics
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from PIL import Image

REPO = Path(__file__).resolve().parent.parent
MAX_EDGE = 1024

JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "same_scene": {"type": "integer", "minimum": 1, "maximum": 5},
        "same_identity": {"type": "integer", "minimum": 1, "maximum": 5},
        "same_composition": {"type": "integer", "minimum": 1, "maximum": 5},
        "same_mood": {"type": "integer", "minimum": 1, "maximum": 5},
        "overall_human_similarity": {"type": "integer", "minimum": 1, "maximum": 5},
        "differences": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "same_scene",
        "same_identity",
        "same_composition",
        "same_mood",
        "overall_human_similarity",
        "differences",
    ],
}

INSTRUCTION = """/no_think
You are reviewing a lossy image codec. The FIRST image is the original photograph. The SECOND
image was regenerated from a short text description of the first; the generator never saw the
original.

Rate the pair the way a careful human reviewer would, on a 1-5 scale where 1 means "completely
different" and 5 means "indistinguishable":

- same_scene: is it the same kind of scene, subject and action?
- same_identity: is it recognisably the SAME individual subject, not merely the same category?
- same_composition: are the objects arranged in the same places?
- same_mood: same lighting, palette and atmosphere?
- overall_human_similarity: would a person shown both say the second is a faithful stand-in
  for the first?

Also list the concrete visible differences a person would notice first, most important first.
Be strict: plausible-but-invented detail is a difference, not a match. Reply with JSON only."""


def _encoded(path: Path) -> str:
    """Downscale for tractable inference and return base64 PNG bytes."""
    with Image.open(path) as image:
        rgb = image.convert("RGB")
        rgb.thumbnail((MAX_EDGE, MAX_EDGE))
        buffer = io.BytesIO()
        rgb.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def judge_pair(host: str, model: str, timeout: float, source: Path, reconstruction: Path) -> Any:
    """Ask the vision model to compare one source/reconstruction pair."""
    payload = {
        "model": model,
        "stream": False,
        "think": False,
        "format": JUDGE_SCHEMA,
        "keep_alive": "30m",
        "options": {"temperature": 0.0, "seed": 42, "num_predict": 1024},
        "messages": [
            {
                "role": "user",
                "content": INSTRUCTION,
                "images": [_encoded(source), _encoded(reconstruction)],
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
    return json.loads(content)


def _spearman(left: list[float], right: list[float]) -> float:
    """Rank correlation, adequate for the small n this benchmark produces."""

    def ranks(values: list[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        result = [0.0] * len(values)
        index = 0
        while index < len(order):
            stop = index
            while stop + 1 < len(order) and values[order[stop + 1]] == values[order[index]]:
                stop += 1
            shared = (index + stop) / 2 + 1
            for position in range(index, stop + 1):
                result[order[position]] = shared
            index = stop + 1
        return result

    left_ranks, right_ranks = ranks(left), ranks(right)
    mean_left, mean_right = statistics.fmean(left_ranks), statistics.fmean(right_ranks)
    covariance = sum(
        (a - mean_left) * (b - mean_right) for a, b in zip(left_ranks, right_ranks, strict=True)
    )
    left_spread = math.sqrt(sum((a - mean_left) ** 2 for a in left_ranks))
    right_spread = math.sqrt(sum((b - mean_right) ** 2 for b in right_ranks))
    if left_spread == 0.0 or right_spread == 0.0:
        return 0.0
    return float(covariance) / (left_spread * right_spread)


def discover_cases() -> list[dict[str, str]]:
    """Pair every checked-in evaluation result with its source and reconstruction."""
    cases: list[dict[str, str]] = []
    for result in sorted((REPO / "survey/results").glob("*.json")):
        name = result.stem
        base = name.removesuffix("-expanded").removesuffix("-detailed")
        source = REPO / f"survey/sources/{base}.jpg"
        reconstruction = REPO / f"survey/reconstructions/{name}.png"
        if source.exists() and reconstruction.exists():
            cases.append(
                {
                    "id": name,
                    "source": str(source.relative_to(REPO)),
                    "reconstruction": str(reconstruction.relative_to(REPO)),
                    "result": str(result.relative_to(REPO)),
                }
            )
    return cases


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="qwen3-vl:32b-ctx49k")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    host = os.environ.get("OLLAMA_VISION_HOST")
    if not host:
        print("OLLAMA_VISION_HOST is not set; the judge needs a reachable endpoint.")
        return 2

    records: list[dict[str, Any]] = []
    for case in discover_cases():
        print(f"judging {case['id']} ...", flush=True)
        verdict = judge_pair(
            host, args.model, args.timeout, REPO / case["source"], REPO / case["reconstruction"]
        )
        metrics = json.loads((REPO / case["result"]).read_text(encoding="utf-8"))["metrics"]
        records.append({**case, "judge": verdict, "metrics": metrics})

    metric_names = [
        "visual_proxy_score",
        "layout_score",
        "dhash_similarity",
        "histogram_similarity",
        "edge_similarity",
        "aspect_similarity",
        "palette_distance",
    ]
    human = [float(r["judge"]["overall_human_similarity"]) for r in records]
    agreement = {}
    for metric in metric_names:
        values = [float(r["metrics"][metric]) for r in records]
        # palette_distance is a distance: invert it so higher always means "more similar".
        if metric == "palette_distance":
            values = [-value for value in values]
        agreement[metric] = round(_spearman(values, human), 3)

    report = {
        "model": args.model,
        "judge_scale": "1-5, 5 = indistinguishable",
        "cases": len(records),
        "caveat": (
            "The judge is a vision model standing in for a human reviewer, not a human. "
            f"n={len(records)} is small, so rank correlations are indicative only."
        ),
        "spearman_vs_overall_human_similarity": dict(
            sorted(agreement.items(), key=lambda item: item[1], reverse=True)
        ),
        "records": records,
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

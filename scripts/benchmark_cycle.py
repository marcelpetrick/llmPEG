"""Measure wall-clock time for a full llmPEG compress/reconstruct/evaluate cycle.

Encoding needs a reachable Ollama vision endpoint (``OLLAMA_VISION_HOST``); the other
stages are offline. Image generation is deliberately excluded: llmPEG ships no
generator, so that stage's cost belongs to whichever external tool the operator uses.

The endpoint host is never recorded — only the model name — so results stay publishable.

Usage:
    uv run python scripts/benchmark_cycle.py --repeats 2 --output docs/benchmark-cycle.json
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from tempfile import TemporaryDirectory

from llmpeg.artifact import Artifact, FidelityProfile
from llmpeg.encoder import encode_image, render_generation_prompt
from llmpeg.evaluation import evaluate_with_artifact
from llmpeg.providers import OllamaVisionProvider

REPO = Path(__file__).resolve().parent.parent

CASES: tuple[tuple[str, str, str], ...] = (
    ("cat-on-grass", "survey/sources/cat-on-grass.jpg", "survey/reconstructions/cat-on-grass.png"),
    (
        "workspace-books",
        "survey/sources/workspace-books.jpg",
        "survey/reconstructions/workspace-books-expanded.png",
    ),
    (
        "amsterdam-market",
        "survey/sources/amsterdam-market.jpg",
        "survey/reconstructions/amsterdam-market-expanded.png",
    ),
)


@dataclass
class Stage:
    """Timings collected for one pipeline stage."""

    samples: list[float] = field(default_factory=list)

    def add(self, seconds: float) -> None:
        self.samples.append(seconds)

    def summary(self) -> dict[str, float]:
        return {
            "runs": len(self.samples),
            "mean_seconds": round(statistics.fmean(self.samples), 4),
            "min_seconds": round(min(self.samples), 4),
            "max_seconds": round(max(self.samples), 4),
        }


def run_case(
    name: str,
    source: Path,
    reconstruction: Path,
    profile: FidelityProfile,
    repeats: int,
    model: str,
    host: str,
    timeout: float,
    workdir: Path,
) -> dict[str, object]:
    """Time encode, prompt render, and evaluation for one image."""
    encode_stage, render_stage, evaluate_stage = Stage(), Stage(), Stage()
    artifact: Artifact | None = None

    for attempt in range(repeats):
        provider = OllamaVisionProvider(host, model, timeout)
        started = time.perf_counter()
        artifact = encode_image(source, provider, profile)
        encode_stage.add(time.perf_counter() - started)

        target = workdir / f"{name}-{attempt}.llmpeg.json"
        artifact.write(target)

        started = time.perf_counter()
        render_generation_prompt(artifact)
        render_stage.add(time.perf_counter() - started)

        started = time.perf_counter()
        evaluate_with_artifact(source, reconstruction, artifact)
        evaluate_stage.add(time.perf_counter() - started)

    assert artifact is not None
    artifact_bytes = len(artifact.to_bytes())
    source_bytes = source.stat().st_size
    return {
        "case": name,
        "profile": profile.value,
        "source_bytes": source_bytes,
        "artifact_bytes": artifact_bytes,
        "ratio": round(source_bytes / artifact_bytes, 1),
        "encode": encode_stage.summary(),
        "render_prompt": render_stage.summary(),
        "evaluate": evaluate_stage.summary(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repeats", type=int, default=2)
    parser.add_argument(
        "--profile", choices=list(FidelityProfile), default=FidelityProfile.BALANCED
    )
    parser.add_argument("--model", default="qwen3-vl:32b-ctx49k")
    parser.add_argument("--timeout", type=float, default=600.0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    host = os.environ.get("OLLAMA_VISION_HOST")
    if not host:
        print("OLLAMA_VISION_HOST is not set; encoding needs a reachable endpoint.")
        return 2

    results: list[dict[str, object]] = []
    with TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        for name, source, reconstruction in CASES:
            print(f"benchmarking {name} ...", flush=True)
            results.append(
                run_case(
                    name,
                    REPO / source,
                    REPO / reconstruction,
                    FidelityProfile(args.profile),
                    args.repeats,
                    args.model,
                    host,
                    args.timeout,
                    workdir,
                )
            )

    report = {
        "model": args.model,
        "profile": FidelityProfile(args.profile).value,
        "repeats": args.repeats,
        "note": (
            "Image generation is excluded: llmPEG ships no generator, so that stage's cost "
            "depends on the external tool the operator chooses."
        ),
        "cases": results,
        "aggregate": {
            "mean_encode_seconds": round(
                statistics.fmean(float(r["encode"]["mean_seconds"]) for r in results),  # type: ignore[index]
                4,
            ),
            "mean_render_prompt_seconds": round(
                statistics.fmean(float(r["render_prompt"]["mean_seconds"]) for r in results),  # type: ignore[index]
                4,
            ),
            "mean_evaluate_seconds": round(
                statistics.fmean(float(r["evaluate"]["mean_seconds"]) for r in results),  # type: ignore[index]
                4,
            ),
        },
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

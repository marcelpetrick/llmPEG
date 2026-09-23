# Creator-versus-rater evidence

These files are the first live run of `scripts/creator_rater.py`, not a benchmark or a claim of
human-perceived improvement. The source is `survey/sources/cat-monochrome.jpg`; its author,
public-domain dedication, licence URL, and source URL are copied into `report.json` from the
checked-in survey manifest.

Both rounds used local Ollama `qwen3.5:4b` for detailed encoding and rating, local
ComfyUI/Qwen-Image-2.1 for 512×512 generation, seed 42, and three rating trials. Clean-room review
found that the original A/B judge also saw candidate prompts, so that verdict was discarded. A
pixels-only rerun preferred whichever candidate appeared second; order reversal therefore made
the logical result inconsistent and rejected the challenger. The automatic semantic median fell
from 85 to 80 while the deterministic proxy rose from 0.632194 to 0.700023, another reason not to
collapse these signals into an "improved quality" claim.

The sibling holdout at [`../creator-rater-holdout/`](../creator-rater-holdout/) showed the same
second-position bias and also rejected its challenger. The loop has not established an improvement
gradient and remains uncalibrated against people.

Files:

- `baseline.llmpeg.json.gz`, `baseline.prompt.txt`, `baseline.png`: initial round;
- `challenger-1.llmpeg.json.gz`, `challenger-1.prompt.txt`, `challenger-1.png`: feedback-focused
  round;
- `report.json`: exact settings, sizes, elapsed times, source credit, repeated ratings,
  deterministic metrics, prompt feedback, pairwise order, reasons, guards, and acceptance.

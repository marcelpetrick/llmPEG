# Held-out tone rule evidence

Output of `scripts/tone_rule_holdout.py` (2026-09-24), all ten non-cat survey sources, 30 renders.
The first run was stopped by request after 14 renders and resumed later for the remaining six
sources; `kitchen-table` was re-rendered in full and its two earlier renders matched exactly.

Each source was encoded once by local Ollama `qwen3.5:4b` (`detailed`, format 1.1) and rendered by
local ComfyUI/Qwen-Image-2.1 at 512×512, seed 42, CFG 3.5, three ways: `control` (the current
pipeline), `rule-negatives` (negatives from `tone_negative()`, which reads measured tone only), and
`rule-negatives-snapshot` (the same negatives plus a fixed snapshot phrase at the top of the
prompt). None of these sources informed the rule.

The script writes `measurements.json` only when it finishes, so the stopped run's rows were rebuilt
from its console log, row for row, with the same fields, and merged with the resumed run's own
file; its `status` says which rows came from where. The
`*.prompt.txt` and `*-result.json` files for the four complete sources were written afterwards for
the review page (`survey/qwen-tone.html`), from the checked-in artifacts with the script's own
expressions.

The write-up is in [`docs/tone.md`](../../../docs/tone.md).

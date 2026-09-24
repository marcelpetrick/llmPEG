"""Constants shared by the tone measurement scripts, so their runs stay comparable."""

from __future__ import annotations

# The three public-domain cat sources credited in survey/manifest.json.
CATS = ("cat-monochrome", "cat-on-keyboard", "cat-on-grass")
# Every non-cat survey source; none of them informed the tone rules.
HOLDOUT = (
    "amsterdam-market",
    "astronaut-crew",
    "dogs-beach",
    "food-table",
    "kitchen-table",
    "living-room",
    "mountain-hikers",
    "street-bicycles",
    "train-platform",
    "workspace-books",
)
# Matches the earlier creator/rater runs so reconstructions stay comparable with them.
RESOLUTION = 512
# One uniform phrase for every case: the opposite of a text-to-image model's polished default.
# It names no colour, so a black-and-white case is steered by its tone words alone.
SNAPSHOT_PHRASE = "Casual unedited snapshot in soft natural light, understated and unpolished"

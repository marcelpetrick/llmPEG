# Do the metrics match a human eye?

llmPEG scores reconstructions with `visual_proxy_score`, a blend of cheap structural signals:
perceptual hash (dHash), RGB histogram intersection, edge density, and aspect ratio. Those signals
are deterministic, offline and fast. Nothing established that they track what a person actually
notices.

This document reports the first attempt to check. **The answer is that they do not**, and on the
current sample the headline metric points the wrong way.

## Method

[`scripts/perceptual_judge.py`](../scripts/perceptual_judge.py) shows a vision model
(`qwen3-vl:32b-ctx49k`, temperature 0, seed 42) the source and the reconstruction together and
asks it to rate the pair the way a careful reviewer would, on five 1–5 axes: scene, identity,
composition, mood, and an overall "is this a faithful stand-in?". Every checked-in reconstruction
pair was judged: **n = 12** (6 cat-survey pairs, 6 expanded-scene pairs).

Raw output, including the judge's per-case list of visible differences, is in
[`perceptual-judge.json`](perceptual-judge.json).

The judge is a model, not a person. It is a second opinion that can be audited case by case, not
ground truth. `n = 12`, one model, one run.

## Result: the proxy is anti-correlated with perceived similarity

Spearman rank correlation against the judge's `overall_human_similarity`:

| Metric | ρ vs judge | Reading |
| --- | ---: | --- |
| `aspect_similarity` | +0.532 | degenerate — range is 0.987–1.000, σ = 0.005 |
| `dhash_similarity` | −0.160 | no useful signal |
| `layout_score` | −0.070 | no useful signal |
| `histogram_similarity` | −0.377 | wrong direction |
| `edge_similarity` | −0.392 | wrong direction |
| **`visual_proxy_score`** | **−0.468** | **wrong direction** |
| `palette_distance` (inverted) | −0.725 | wrong direction |

Not one metric is usefully positive. The only positive number, `aspect_similarity`, varies by less
than half a percent across the whole set, so its correlation is noise on a near-constant.

## Why: the proxy measures busyness, not fidelity

The sample splits cleanly:

| Group | n | Mean judge score | Mean `visual_proxy_score` |
| --- | ---: | ---: | ---: |
| Cat survey (simple scenes) | 6 | 4.17 | 0.676 |
| Expanded benchmark (busy scenes) | 6 | 2.67 | 0.741 |

The busy scenes score **higher** on the machine proxy and **lower** with the judge. A crowded
market or a station platform gives dHash and edge density plenty of structure to agree about,
while the reconstruction quietly replaces every person in it. A cat on grass has little structure
to match, so the proxy scores it poorly even when the result is an excellent stand-in.

The starkest cases:

| Case | `visual_proxy_score` | Judge | What happened |
| --- | ---: | ---: | --- |
| `cat-on-grass` | 0.595 (lowest) | **5** | different cat, but a faithful stand-in |
| `astronaut-crew-expanded` | 0.732 | **1** | six real people replaced by six invented ones |
| `train-platform-expanded` | 0.715 | **1** | right scene, entirely different travellers |
| `amsterdam-market-expanded` | 0.718 | **1** | scene rated 5, identity rated 1 |

## What humans actually judge: identity

The judge's `same_identity` axis predicts its overall verdict almost perfectly. The two agree
exactly on ten of twelve cases, and never differ by more than one point — the two exceptions are
`cat-monochrome-detailed` (identity 2, overall 3) and `workspace-books-expanded` (identity 5,
overall 4):

```
(identity, overall): (1,1) (1,1) (2,3) (2,2) (5,5) (5,5) (5,5) (5,5) (4,4) (5,5) (1,1) (5,4)
```

That is the finding in one line: **a reviewer's verdict is identity preservation.** Everything the
structural proxies measure — edges, histograms, hashes — is blind to it. `amsterdam-market` scoring
`same_scene: 5` and `same_identity: 1` is the whole problem in one case.

## What this changes

**`visual_proxy_score` is not renamed or reweighted.** Two reasons. Re-tuning weights on twelve
points would be curve-fitting, and no reweighting of edge density and colour histograms can
recover subject identity — the information is not in those signals. Changing the formula would
also silently invalidate every checked-in evaluation report.

Instead:

1. **`visual_proxy_score` is documented as a structural sanity check, not a quality score.** It
   answers "is this the same kind of picture, roughly arranged the same way?" It does not answer
   "would a person accept this?" The name was already honest; the surrounding claims were not
   careful enough.
2. **Identity gets its own axis**, measured by an explicitly labelled model judge and stored
   separately, never folded into the deterministic score. A slow, non-deterministic, clearly
   marked judgement beats a fast deterministic number that points the wrong way.
3. **Acceptance for identity-critical images should read `same_identity`**, not
   `visual_proxy_score`. The astronaut crew portrait passed three structural thresholds and failed
   the only one that mattered.

## Honest limits

- `n = 12`, one judge model, one run per pair, no repeat-stability measurement yet.
- The judge has never been calibrated against real human ratings. The survey pages collect 1–5
  human ratings and export them; none are checked in yet. Comparing judge scores to real ratings
  is the obvious next step and would either validate this document or overturn it.
- Simple-versus-busy scene type is confounded with survey group here. A sample that varies scene
  complexity within each group would separate those effects.
- Rank correlations on twelve points have wide error bars. The direction is consistent across five
  of seven metrics, which is why it is reported at all, but no single ρ here should be quoted as
  precise.

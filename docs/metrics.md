# Do the metrics match a human eye? We still cannot say.

llmPEG scores reconstructions with `visual_proxy_score`, a blend of cheap structural signals:
perceptual hash (dHash), RGB histogram intersection, edge density, and aspect ratio. Nothing
established that those signals track what a person actually notices.

To find out, [`scripts/perceptual_judge.py`](../scripts/perceptual_judge.py) shows a vision model
both images and asks it to rate the pair the way a careful reviewer would, on five 1–5 axes.

**An earlier version of this document reported that `visual_proxy_score` correlates −0.468 with
that judge — that the headline metric pointed the wrong way. That conclusion is withdrawn.** It
did not survive a second run.

## What happened

Run 1 judged the 12 reconstruction pairs that existed at the time. Run 2 judged all 16 that exist
now, after the expanded benchmark was completed. Between the two runs the judge's *instruction*
changed cosmetically: a cap of "at most 6 differences, each under 200 characters" was added,
because run 1 had been overflowing its token limit and truncating its own JSON.

Nothing else changed. Same model, same temperature `0`, same seed `42`, same images.

On the 12 pairs common to both runs:

| | Result |
| --- | ---: |
| Pairs re-judged | 12 |
| Pairs whose overall verdict changed | **11** |
| Mean absolute change, on a 1–5 scale | **1.67** |
| Largest single change | 3 points (`cat-on-grass-detailed`, `cat-on-keyboard-detailed`) |

`cat-on-grass` went from 5/5 to 3/5. `train-platform` went from 1/5 to 3/5. `amsterdam-market`
went from 1/5 to 3/5.

The headline correlation moved with them:

| Metric | ρ, run 1 (n=12) | ρ, run 2 (n=16) |
| --- | ---: | ---: |
| **`visual_proxy_score`** | **−0.468** | **+0.007** |
| `palette_distance` (inverted) | −0.725 | +0.287 |
| `edge_similarity` | −0.392 | +0.389 |
| `histogram_similarity` | −0.377 | +0.123 |
| `dhash_similarity` | −0.160 | +0.007 |
| `layout_score` | −0.070 | +0.048 |
| `aspect_similarity` | +0.532 | −0.234 |

Every correlation flipped sign or collapsed. `edge_similarity` went from −0.392 to +0.389 —
almost exactly the same magnitude, opposite direction.

## The finding

**The judge is not a stable instrument.** A formatting instruction that should not have changed
any verdict changed eleven of twelve, by 1.67 points on average. Correlations computed on top of
it are therefore not measuring the metrics; they are measuring one particular prompt.

So the honest state of the question is:

- **Not established** that `visual_proxy_score` tracks human perception.
- **Not established** that it points the wrong way, which is what run 1 appeared to show.
- **Established** that a single-run vision-model judge cannot settle either, and that the earlier
  confident answer was an artifact.

Both runs are checked in — [`perceptual-judge-run1.json`](perceptual-judge-run1.json) and
[`perceptual-judge.json`](perceptual-judge.json) — so anyone can recompute this rather than take
it on trust.

## What survives from run 1

Two observations are robust across both runs:

**`aspect_similarity` is degenerate.** Its range is 0.987–1.000 with σ ≈ 0.004 in both runs.
Whatever correlation it shows is noise on a near-constant, in either direction.

**Identity matters more than structure.** In run 1 the judge's `same_identity` axis matched its
overall verdict exactly on 10 of 12 cases; in run 2 that fell to 5 of 16, but the two still never
differ by more than one point except once. The structural metrics remain blind to subject
identity, which is the thing a reviewer looks at first. This is an argument from the metrics'
construction — edges and histograms cannot encode *who* is in a photograph — not from the
correlations, which is why it survives their collapse.

## What would actually answer the question

1. **Repeat-stability first.** Run the judge three times on identical input with an unchanged
   prompt before trusting a single number from it. That check should have come before the
   correlations, not after.
2. **Real human ratings.** The survey pages already collect 1–5 ratings and export them; none are
   checked in. A dozen human ratings would outrank any amount of model judging.
3. **Forced pairwise choice.** Absolute 1–5 scores from a vision model are what proved unstable
   here, and the same collapse-to-the-middle showed up in
   [the adversarial loop](adversarial.md). Asking which of two reconstructions is better is a
   easier question and a more robust instrument.

## Honest limits

`n` is 12 and 16. One model. One run per configuration. No human ground truth anywhere in this
document. The instability reported above is itself measured from two runs, which is enough to
show a problem exists but not enough to characterise its size.

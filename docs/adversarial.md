# GAN-shaped refinement: a negative result

llmPEG's encoder is a prompt. Prompts can be iterated, so the obvious question is whether the
extraction instruction can be improved automatically instead of by hand.

[`scripts/adversarial_refine.py`](../scripts/adversarial_refine.py) borrows the *shape* of
adversarial training — not a GAN, no gradients, no trained discriminator, just the part of the
idea that transfers to a text codec:

```
generator  = the extraction instruction (what the vision model is told to capture)
critic     = a vision model shown the ORIGINAL image and ONLY the rendered generation prompt,
             asked what a generator would get wrong
signal     = the critic's misses, weighted by severity, aggregated into a focus instruction
next round = re-encode with that focus, then attack again
```

The objective is **artifact sufficiency**, not reconstructed-image quality. llmPEG ships no
generator, so the loop cannot be closed on pixels. That is a proxy, and it is reported as one.

## What happened

Three rounds, three sources (`cat-on-grass`, `astronaut-crew`, `train-platform`), `detailed`
profile, `qwen3-vl:32b-ctx49k` at temperature 0 and seed 42. Full per-round record, including
every individual miss, in [`adversarial-rounds.json`](adversarial-rounds.json).

| Round | Focus | Mean reconstructability | Severe misses | Mean artifact bytes |
| ---: | --- | ---: | ---: | ---: |
| 0 | none (baseline) | 3.00 | 6 | 2,767 |
| 1 | counts, layout, object counts | 3.00 | **10** | 2,408 |
| 2 | counts, layout, object counts | 3.00 | **10** | 2,418 |

**The loop failed.** Severe misses went up by two thirds, artifact size went down, and the
critic's score did not move at all.

## Why it failed, and the part worth keeping

**1. The critic has no dynamic range.** It returned `reconstructability: 3` for every case in
every round — nine identical verdicts out of nine. A discriminator that outputs a constant offers
no gradient, so nothing downstream could have worked regardless of how good the focus instruction
was. This is the whole result in one line, and it was invisible until the rounds were logged
individually.

**2. The loop hit a fixed point immediately.** Rounds 1 and 2 derived the *same* three focus
aspects, so round 2 was a re-run of round 1 with a different random draw. Artifact sizes differ by
about 10 bytes between them, which is noise. Any further rounds would have been wasted compute.

**3. The directive traded the wrong thing.** Told to prioritise exact counts and positions, the
encoder spent its budget there and produced *smaller* artifacts with *more* severe misses. On
`cat-on-grass`, severe misses rose from 2 to 6 while the artifact shrank from 2,021 to 1,894
bytes. Focus instructions compete for a fixed byte budget: telling the encoder what to add is
implicitly telling it what to drop, and nothing in this loop decided what was safe to lose.

## What to do differently

- **Make the critic compare, not score.** Absolute 1–5 judgements from a vision model collapse to
  the middle. Showing it two candidate prompts for the same image and asking which reconstructs
  better is a forced choice, which is both easier for the model and closer to how an actual
  discriminator works. This is the single change most likely to make the loop function.
- **Hold artifact bytes constant.** Improvement only means something at a fixed budget; otherwise
  the loop can trade size for score in either direction and call it progress.
- **Keep per-round records.** The aggregate table alone would have shown "3.00, 3.00, 3.00" and
  invited a shrug. The per-case log is what revealed the constant-verdict bug.
- **Validate the critic before trusting it.** Feed it a deliberately gutted prompt and a good one.
  If it cannot separate those, it cannot rank two real candidates.

## Honest limits

Three sources, three rounds, one model, one run each. This does not show that adversarial
refinement cannot work for a prompt codec — it shows that *this* implementation did not, and
names the specific defect (a constant-output critic) that has to be fixed before the question can
be asked properly. The script is checked in so the next attempt starts from a known failure rather
than from scratch.

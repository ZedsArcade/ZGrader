# Real card photographs

Drop actual photos of actual cards here. The drift harness picks up anything in
this directory automatically:

```
python scripts/fixture_drift.py
```

They are measured and printed, but **never given a baseline entry**, and no
test asserts anything about them. That is deliberate — see below.

## Why these exist at all

The synthetic fixtures have exact ground truth: a fixture built at a 65/35
offset *is* 65/35, so a test can assert the pipeline says so. No photograph can
support that, because nobody knows the true centering of a real card to a
decimal place.

What synthetics cannot do is look real. They have no paper fibre, no genuine
holo interference, no actual corner wear, and none of the lighting behaviour of
a hand-held phone. A pipeline tuned only against them will get very good at
measuring synthetic cards.

So the two do different jobs:

- **Synthetics carry the assertions.** Exact ground truth, deterministic, free.
- **Real photos catch overfitting.** Their numbers are for a human to look at
  and say "that card is obviously off-centre and the pipeline scored it 9.8".

Baselining them would be worse than useless: their metrics *should* move as the
pipeline improves, and a test demanding they stay fixed would punish exactly the
work it was meant to protect.

## What to shoot

Roughly 15–20, covering what the synthetics can only approximate:

- a bordered card in good condition, and the same card visibly off-centre
- a full-art / borderless card — the case centering genuinely cannot measure
- a foil or holo card, ideally photographed so the holo actually flares
- a white-bordered card with corner wear, which is the hardest whitening case
- a card with real edge chipping and one with a genuine crease
- deliberately bad captures: soft focus, tilted off-square, flash glare, and
  one taken deliberately too far away

Front and back of a few of them is more useful than more singletons, since
front/back combination is weighted 70/30 and nothing else exercises that on
real input.

## Naming

The stem becomes the label in the harness output, so name them for what they
demonstrate, not what the card is: `fullart_holo_glare.jpg` is useful,
`charizard.jpg` is not.

Standard 63×88mm stock is assumed for the physical scale. Anything else needs
handling in `scripts/fixture_drift.py` — see `_DEFAULT_CARD_MM`.

## Before committing any

These are binaries, so they go through git-LFS (see `.gitattributes` at the
repo root). **Confirm LFS works on the deployment path first** — the Unraid
host and whatever clones the repo there both need it, and a repo that only
half-clones is a worse problem than not having the photos.

Also worth remembering these are photographs of cards you own. Don't put a
customer's uploaded scan in here; user uploads are not retained, and this
directory is version-controlled and public to anyone with repo access.

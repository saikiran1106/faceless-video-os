---
name: reference-image-beats-more-words
description: When an image model keeps drawing a detail wrong, the fix is a correct reference image — strengthening the prompt wording does not work
metadata:
  type: feedback
---

Dhritarashtra kept coming back with blank white eyeballs across three rounds. Each
round I strengthened the wording — first negatives ("no blindfold, no white eyes"),
then positive cues ("dark irises, unfocused, aimed past the speaker, head turned
toward sound"). Frames generated under the strongest wording (KF127, KF147, KF174)
still failed.

The actual cause: the attached character sheet **CS03 has his eyes drawn wrongly**
— the bible even says so — and the prompt said "match the attached sheet exactly".
The model was obeying. Same story for the pachikalu: every frame that got the dice
authority attached drew them correctly; every frame that did not got cowrie shells
or cubic dice.

**Why:** an attached reference outranks any amount of prose. Prose cannot overrule
a picture the model is told to copy.

**How to apply:** when a detail keeps failing, check first whether a reference is
attached at all, and whether the attached reference itself is correct. If no
correct reference exists, **crop one out of a frame that came back right** and make
it an authority image. Only then adjust wording. Widen attachment rules
aggressively — "the board is visible in this shot" is true far more often than a
beat-keyword test suggests.

Related: [[character-design-research-rule]], [[dyuta-sabha-status]].

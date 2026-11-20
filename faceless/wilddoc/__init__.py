"""Wild-doc: script + narration audio -> finished fast-cut natural-history documentary.

Built from a 7-iteration client production (a prehistoric-wildlife survival long-form): 2.5D depth-parallax AI plates,
graded real stock footage, real-photo evidence cards, English motion graphics, a cut every <= 3.3 s,
word-locked camera kicks and SFX, chapter score ~11.5 dB under the voice, verified chunked renders.
Entry point: `faceless wild-doc ...` (see faceless/wilddoc/cli.py and docs/18-wild-doc-style.md).
"""


class WildDocError(ValueError):
    """A wild-doc step cannot run; the message says what to do next."""

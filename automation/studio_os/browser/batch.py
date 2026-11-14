"""Batched keyframe generation.

One message carries N numbered prompts and asks for N separate images. That is
roughly an order of magnitude less wall-clock than one message per frame,
because the per-message overhead (upload, submit, first-token latency) is paid
once instead of N times.

Two failure modes are documented in this repo's own history and are guarded
here rather than discovered again:

  * **A batch can return N variants of entry 1** instead of N distinct images.
    Guarded by hashing every image and rejecting duplicates, and by requiring
    the returned count to match before anything is filed.
  * **A bulk drop carries no frame identity.** Filenames and arrival order are
    NOT proof of which beat an image belongs to. So a batch result is filed as
    `qa_pending` bound to its declared keyframe_id by POSITION, and must be
    confirmed by looking at the pixels before it can pass. A short or
    duplicated batch fails the whole batch rather than filing a guess.

ORDERING IS NOT RELIABLE — MEASURED 2026-09-20.
A 9-item character-sheet batch, explicitly numbered "IMAGE 1 of 9 ... IMAGE 9 of 9"
and asked for in order, came back with **every single item in a different slot**:

    requested  CS01 CS02 CS03 CS04 CS05 CS07 CS08 CS09 CS10
    delivered  CS09 CS01 CS08 CS10 CS03 CS05 CS02 CS07 CS04

Zero of nine matched. So position binding is a GUESS, not evidence.

Consequence for keyframes: binding by position would put most frames on the wrong
beat, which is the exact failure the Keyframe-Beat Binding Law was written for
(an earlier re-mapping layer put 86% of shots on the wrong beat and caused all 49
defects in that episode).

RULE:
  * Reference sheets MAY be batched - they are visually distinct, so a human or
    agent can identify each one by content and file it correctly.
  * NARRATIVE KEYFRAMES MUST NOT be batched and bound by position. Generate one
    per message, where identity is unambiguous, or verify every single frame by
    content before filing.
Batching trades wall-clock for identity. Only spend that trade where identity can
be recovered by looking.
"""
from __future__ import annotations

from typing import Dict, List

BATCH_HEADER = """Generate exactly {n} SEPARATE images in this reply.

Rules:
- Exactly {n} images, one image for each numbered item.
- Generate them in the same order: Image 1 through Image {n}.
- Every item must be a separate standalone {aspect} image.
- Do not combine items into one image.
- No grid, collage, contact sheet, split-screen or variants.
- Do not skip, repeat or reorder any item.
- No text, captions, logos, signatures or watermarks inside the images.
- Use the attached references for identity, style and location continuity.
{subject_rules}
Produce Image 1 through Image {n} now, in order.
"""

# Subject-specific rules are added only when a batch depicts that subject, so a
# Ganesha rule never leaks into (say) a tech-reel batch.
SUBJECT_RULES = {
    "ganesha": (
        "- Use the attached real-world references for festival accuracy.\n"
        "- STRICT ICONOGRAPHY: In every depiction of Lord Ganesha, he MUST be Ekadanta (ఒంటి దంతం). "
        "His anatomical right tusk is completely whole, unbroken, and intact. His anatomical left tusk "
        "is distinctly broken.\n"
    ),
}

ITEM = """
=== IMAGE {idx} of {n} — {keyframe_id} ===
{prompt}
"""


def build_batch_prompt(jobs: List[Dict], aspect: str = "9:16 vertical") -> str:
    """One message body carrying every job in the batch, explicitly numbered."""
    n = len(jobs)
    text = " ".join(j["prompt"] for j in jobs).lower()
    subject_rules = "".join(rule for key, rule in SUBJECT_RULES.items() if key in text)
    parts = [BATCH_HEADER.format(n=n, aspect=aspect, subject_rules=subject_rules)]
    for i, j in enumerate(jobs, 1):
        parts.append(ITEM.format(idx=i, n=n, keyframe_id=j["keyframe_id"],
                                 prompt=j["prompt"].strip()))
    return "\n".join(parts)


def batch_references(jobs: List[Dict]) -> List[str]:
    """The union of every reference the batch declares, order-stable.

    A batch shares one attachment set, so each frame sees every reference in the
    batch. That is acceptable for continuity (they are all this episode's
    approved sheets) but it is why batches are grouped by location below - it
    keeps the attachment set small and on-topic.
    """
    seen, out = set(), []
    for j in jobs:
        for r in j.get("reference_paths") or []:
            if r not in seen:
                seen.add(r)
                out.append(r)
    return out


def plan_batches(jobs: List[Dict], size: int, max_refs: int = 8) -> List[List[Dict]]:
    """Group consecutive jobs into batches.

    Consecutive-only: neighbouring beats share a location and cast, so their
    reference union stays small and the batch reads as one coherent scene.
    A batch is cut short when adding the next job would push the attachment set
    past `max_refs`, because a large attachment set dilutes identity.
    """
    batches: List[List[Dict]] = []
    cur: List[Dict] = []
    for j in jobs:
        candidate = cur + [j]
        if cur and (len(candidate) > size or len(batch_references(candidate)) > max_refs):
            batches.append(cur)
            cur = [j]
        else:
            cur = candidate
    if cur:
        batches.append(cur)
    return batches


# A real 9:16 generation takes tens of seconds. Anything that "completes"
# faster than this was not generated by our submission - it is pre-existing
# artwork the page happened to load. Verified live: a 5-frame batch returned in
# 15s holding five images from an unrelated project.
MIN_PLAUSIBLE_S_PER_IMAGE = 12.0


class ImplausiblySoon(RuntimeError):
    """The batch "finished" too fast to have been generated by us."""

    def __init__(self, elapsed: float, want: int):
        self.elapsed, self.want = elapsed, want
        super().__init__(
            f"batch of {want} returned after {elapsed:.1f}s, under the "
            f"{MIN_PLAUSIBLE_S_PER_IMAGE * want:.0f}s floor - these are almost "
            "certainly pre-existing images, not this submission's output")


class BatchMismatch(RuntimeError):
    """The reply did not contain exactly one distinct image per item."""

    def __init__(self, want: int, got: int, duplicates: int = 0):
        self.want, self.got, self.duplicates = want, got, duplicates
        super().__init__(
            f"batch returned {got} distinct images for {want} items"
            + (f" ({duplicates} duplicate(s))" if duplicates else "")
        )


def verify_batch(images, jobs, elapsed_s: float = None) -> None:
    """Refuse to file anything unless the reply really is this batch's output.

    Three independent checks, because each has failed in practice:
      1. exactly one image per item (a batch can return variants of item 1);
      2. all distinct (same reason);
      3. it took long enough to have actually been generated (otherwise we are
         looking at images the project page loaded on its own).
    """
    shas = [i.sha256 for i in images]
    dupes = len(shas) - len(set(shas))
    if len(set(shas)) != len(jobs):
        raise BatchMismatch(len(jobs), len(set(shas)), dupes)
    if elapsed_s is not None and elapsed_s < MIN_PLAUSIBLE_S_PER_IMAGE * len(jobs):
        raise ImplausiblySoon(elapsed_s, len(jobs))

---
name: chatgpt-batch-drops-entries
description: A pasted JSON batch can silently return N variants of entry 1 instead of N distinct images — always count and diff before accepting
metadata:
  type: feedback
---

When a JSON array of distinct image prompts is pasted into one ChatGPT chat, it sometimes
renders the FIRST entry repeatedly at different camera angles instead of one image per
entry. On one production, LOC_BATCH_01 returned 7 framings of a single `chamber_night` location
and zero of the other nine locations — the batch looked "mostly delivered" by file count.

**Why:** the failure is invisible from filenames and file count alone. Downloads are just
`ChatGPT Image ... (1..7).png`, so a batch that lost 90% of its content still looks like a
partial success.

**How to apply:** on every batch ingest, (1) assert received count == expected entry count,
and (2) compute pairwise mean pixel difference across the group — values in a narrow band
(~30–43) mean one location shot from several angles, not distinct subjects. Confirm with a
labelled contact sheet before renaming anything. Re-run the batch with an explicit
"generate these N as N SEPARATE, DISTINCT images, one per entry, do not repeat" note.
Related: [[chatgpt-bulk-image-generation]], .

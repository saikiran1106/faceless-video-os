---
name: chatgpt-drop-never-map-by-filename
description: A bulk ChatGPT image download carries no frame identity — map images to shots by picture content, never by download order or filename
metadata:
  type: feedback
---

A ChatGPT bulk image download arrives as `ChatGPT Image <date> (n).png` with **no
prompt, no id, and no usable metadata** (C2PA only). The `(n)` grouping looks like
one group per batch — it is not reliable.

On the Dyuta Sabha 09-09 drop, 131 files grouped into 13×10 + 1, exactly matching
"batches 02–15". That reading was wrong. The drop was **one continuous stream in
frame order starting at KF013, with 10 frames missing**, so the offset grew from
+1 to +10 across the first 30 images. Mapping by download order would have
mislabelled the entire film.

**Why:** every gap (a prompt ChatGPT silently skipped) shifts everything after it.
Counts can match by coincidence — 131 images happened to equal batches 02–15.

**How to apply:**
- Establish the mapping from **picture content** against the shot beats, pinned on
  unmistakable frames (the only daylight shot, an isolated portrait, the final
  empty room), and check anchors at BOTH ends plus the middle.
- Anchors at one end only are not proof; a gap early in the stream leaves the tail
  correct while the head is wrong.
- Prevent it at the source: have the user drop each batch into its own folder, or
  end every batch prompt with "list every SAVE AS name you produced, in order".
- Never ingest before the mapping is content-verified. Quarantine, don't delete,
  if an ingest turns out wrong.

Related: [[chatgpt-batch-drops-entries]], [[dyuta-sabha-status]],
[[chatgpt-bulk-image-generation]].

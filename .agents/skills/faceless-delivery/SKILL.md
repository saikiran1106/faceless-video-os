---
name: faceless-delivery
description: Deliver and publish: upload to R2/S3 with checksum verification, presign forced-download links, email a client from a signed-in Gmail profile with a receipt, and follow the publishing gates (CP1/CP2, no unasked posts, credits, release lock). Use whenever a file or link must leave the machine.
---

# Faceless Delivery

Read `docs/learnings/10-delivery-and-publishing.md`. Code: `automation/tools/storage/r2.py`, `automation/tools/publishers/`.

## Procedure
1. Verify the local file first (sha256 vs recorded, decode check). Upload with `r2.put_file`; compare the returned sha256/bytes.
2. `presign_get(key, ttl=604800, download_name=...)` → forced attachment; `curl -r 0-0` must return 206.
3. Mail (when asked): Gmail via the signed-in Playwright profile, assert the account in the page title, keep compose + sent screenshots, wait for "Message sent".
4. Publishing: only on request and only after CP2. Credits for Creative-Commons assets in the description. Caption keywords in line 1, ≤ 5 hashtags, cover text centred, AI label on.

## Hard rules
- Links expire: state the date and ask the recipient to keep a copy.
- A client email only after the creator approves the cut. Never post, upload or send externally unasked. Never click Share twice.

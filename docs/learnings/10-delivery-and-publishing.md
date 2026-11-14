# 10. Delivery and publishing

## Object storage (Cloudflare R2 / any S3-compatible)

`automation/tools/storage/r2.py`: `put_file`, `object_exists`, `presign_get`, `list_prefix`, `sync_dir` (+ CLI). Credentials come from `.env` (`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`, `R2_BUCKET`).
- **Presign with `ResponseContentDisposition=attachment` and a clear filename**, so the link downloads (works on a phone) instead of streaming in a tab.
- **Verify the object:** compare the returned sha256/bytes, then `curl -r 0-0` (a 206) to prove the signed link works. Re-download and sha-check an upload you are about to build on.
- Links expire (7 days is the S3 maximum); say the date in the message and ask the recipient to keep a copy. Use one key prefix per campaign/project.
- Bigger than ~5 GB needs multipart (boto3's `upload_file` does this automatically).
- Boto3 lives in the venv; system Python usually lacks it.

## Emailing a client from a signed-in Gmail profile

Playwright persistent profile (`channel="chrome"`, the libsecret flag from [1](01-browser-automation-and-logins.md)) → open `mail.google.com/mail/u/0/?view=cm&fs=1&to=…&su=…` → click the body → `insert_text` the body →
screenshot → Send → wait for "Message sent". Assert the page title contains the expected account so a wrong profile can never send. Keep the compose and sent screenshots as the receipt.
The message should contain: the links with their expiry date, what changed, what is in the package, the honest limits, the video facts, and the packaging text (titles, description with chapters and credits, tags).

## Publishing rules

- **Three human moments only:** CP1 approve the story/script, CP2 approve the final cut, publishing. Never upload, post or email externally without being asked (and a client email only after the creator approves the cut).
- Attribution: stock/fossil/reference photos under Creative Commons need credits in the description; keep a machine-readable credits file next to the assets.
- YouTube: one promise across title, thumbnail, first 25 seconds and story spine; title as one curiosity question; broad keyword in title, first two description lines and tags (verify volume with a keyword tool when connected);
  chapters from the final timeline; Shorts: append the thumbnail as a ~2 s final segment *after* the CTA.
- Instagram: turn on the AI label; caption keywords in line 1, ≤ 5 hashtags; cover text centred.
- Wait ~48 h before judging analytics; gate on retention at 15 s and first-minute drop-off, not on keyword-score widgets (those are hygiene only).
- Release lock: no long-form upload without recorded script, voice, visuals, edit and final-delivery locks, a real package-checker result, and final title/thumbnail/date/description/end-screen verification.

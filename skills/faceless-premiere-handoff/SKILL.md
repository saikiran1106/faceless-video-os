---
name: faceless-premiere-handoff
description: Package a finished film as an editable Premiere Pro project for a client: picture cut per shot, separate voice/music/ambience/SFX stems, FCP7-XML sequence + EDL + shot list, source library, README, zip, R2 links and the client email - with the honest limits (baked graphics, XML not .prproj, not opened in Premiere). Use when a client or editor wants to import and edit the project.
---

# Faceless Premiere Handoff

Read `docs/learnings/09-premiere-and-editor-handoff.md` and `10-delivery-and-publishing.md`. Tool: `automation/video_tools/premiere_export.py`.

## Procedure
1. Picture = the verified master with audio stripped (`ffmpeg -map 0:v -c copy`), re-sealed. Stems = the mix re-run at final level (`stem x G`, lag-aligned), validated to sum to the master mix.
2. `python automation/video_tools/premiere_export.py <project_dir> <Name>` → `<Name>_Premiere.xml`, `.edl`, `_ShotList.csv`. Validate: clips contiguous to the last frame, every file exists, durations match.
3. Library (originals used, plates + depth, references, SFX/music, fonts, credits), `README_START_HERE.txt`, `Fix_Paths.py`.
4. Zip with `ZIP_STORED` + zip64; test CRCs; decode-check every media file; upload to R2 and compare sha256; presign forced-download links (7 days).
5. Email the client (links + expiry, what changed, how to import, what is editable, honest limits). Send only when asked.

## Be honest
- A native `.prproj` can't be generated without Premiere; XML is the standard handover. Say it was validated by script, not opened in Premiere.
- Graphics/motion composited at render time are baked into the picture; offer a layered render as a separate (long) job.
- Tell the editor to put a limiter on the master bus.

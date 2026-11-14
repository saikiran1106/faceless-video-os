# 9. Handing a finished film to a Premiere Pro editor

Goal: a client downloads one folder, imports one file, and can re-cut and re-mix. Tool: [`automation/video_tools/premiere_export.py`](../../automation/video_tools/premiere_export.py).

## What is possible (and what is not)

- A native `.prproj` cannot be generated without Premiere itself (it is Adobe's proprietary gzip-XML). The standard handover is a **Final Cut Pro 7 XML (xmeml v4)** sequence that Premiere imports with
  *File ▸ Import*. We validated the generated XML by script (contiguity, in/out consistency, every file reference resolves, every media duration matches); **not** by opening it in Premiere. Say so.
- **Baked graphics:** if text cards, motion graphics and 2.5D camera moves were composited by Remotion/HyperFrames, they are part of the picture. The editor can re-cut, reorder, trim and re-mix, but not edit a text
  card's wording. Layered/alpha renders of the graphics would need another full render pass; offer it instead of promising it.

## Package layout

```
Project/
  README_START_HERE.txt            open steps, track map, what is/isn't editable
  <Name>_Premiere.xml              the sequence (relative media paths)
  <Name>_cuts.edl  <Name>_ShotList.csv   fallback cut list; per-shot timecode, source file, narration line
  Fix_Paths.py                     writes <Name>_Premiere_ABSOLUTE.xml if Premiere reports media offline
  Media/Video/<Name>_Picture.mp4   finished picture (no audio), cut into one clip per shot on V1
  Media/Audio/                     Voice (mono), Music_Score, Ambience_Beds, SFX stems (see 07)
  Library/                         original stock clips, AI plates + depth maps, reference photos, every SFX/music cue, fonts, thumbnail, docs/credits
```
Sequence: V1 = picture clips; A1 voice (mono); A2–3 music, A4–5 beds, A6–7 SFX (stereo = two tracks each); chapters as sequence markers.

## Gotchas

- Stereo files in xmeml = two `track` elements with `sourcetrack/trackindex` 1 and 2 and `premiereTrackType="Stereo"`; a mono file = one `Mono` track.
- Durations in xmeml are in **sequence frames** even for audio files.
- Relative `pathurl`s keep the zip portable. If Premiere asks to relink: Link Media ▸ Locate the first file and the rest follow.
- Build the zip with `ZIP_STORED` and zip64 (media is already compressed); expect ~3–4 GB for a 8-minute film with originals.
- Run `media_guard`/decode checks on **every media file inside the package** and test the zip CRCs before upload.
- Premiere automation through an MCP bridge (inspect timeline, cut lists, markers, frame grabs, effects) is a separate, experimental route; use it only on a duplicate sequence of a saved project.
- Put a limiter on the master bus before export: the SFX stem is loud and the sum of stems can exceed 0 dBFS without it.

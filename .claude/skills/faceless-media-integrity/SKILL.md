---
name: faceless-media-integrity
description: Protect renders, downloads and masters from silent corruption on unstable hardware: seal/check media, chunked guarded renders, verified assembly with frame-count checks, sha256 re-verification before reuse, retries with sanity assertions around ffmpeg/NumPy, software GL, and git object repair. Use before assembling or uploading any media, after a segfault/odd ffmpeg result, or when a file that decoded clean now fails.
---

# Faceless Media Integrity

Read `docs/learnings/08-media-integrity-and-flaky-hardware.md`. Tools: `automation/tools/media/media_guard.py`, `automation/video_tools/`.

## Procedure
- `python3 -I automation/tools/media/media_guard.py seal FILE` after every render/download; `check FILE` before assembly and upload.
- Chunked renders only (per chapter), 2-3 workers, `nice`, one heavy job at a time, `TMPDIR` on disk, software GL.
- `automation/video_tools/assemble_verified.py` for the final master: per-chapter encode, decode-check output **and** input, **frame count == plan**, retry ≤ 4, stream-copy concat.
- Before reusing any master: compare its sha256 with the recorded one. Mismatch = bit rot: restore from the verified object-storage copy.
- Wrap numeric/ffmpeg steps in retries and assertions (peak < 2, gain in range, stems sum to the verified mix); prefer re-deriving from a verified file.

## Reminders
- A seal "clean" result does not prove frame count. A corrupt or short chunk is re-rendered, never patched.
- Hardware to-dos if it recurs: memtest86+, cooling, BIOS, SSD SMART.

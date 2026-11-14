# 8. Media integrity on flaky hardware

Symptom: videos that decode clean when rendered and fail later, random encoder errors, an ffmpeg `loudnorm` pass that suddenly measures +750 dB, NumPy results that differ between runs.
Cause (measured): a laptop running at ~90 °C and throttling, **RAM bit flips under sustained load**, and PCIe errors on the SSD. It is hardware, not software. Treat every long job as untrusted.

## Rules

1. **Seal and check every media file** (`automation/tools/media/media_guard.py seal FILE` / `check FILE`): records sha256, bytes and a full decode check. `check` before assembly and before upload.
2. **Seal is not a frame-count check.** A chunk once sealed "clean" while one frame short with decode errors near its end. The verifying assembler also compares **frame counts**
   to the plan; on mismatch **re-render** the chunk, never patch it.
3. **Render in chunks** (per chapter), 2–3 workers, `nice`; **one heavy job at a time** (two at once caused an out-of-memory kill).
   `video_tools/render_queue_guarded.sh` renders each chunk to a temp file, seals it, and re-renders on a corrupt result.
4. **Assemble with `video_tools/assemble_verified.py`:** per-chapter encode (chunk + its patches), decode-verify the output *and* the input, retry up to 4×, then stream-copy concat and mux the mastered audio.
5. **Verify checksums before reuse.** A sealed master later **bit-rotted at rest** (its sha256 changed, decode errors at ~85 % of the film) while the object-storage copy stayed intact.
   Compare against the recorded sha256, and keep the verified copy somewhere else (object storage) before relying on a local file.
6. **Wrap numeric/ffmpeg steps in retries with sanity assertions.** Examples that caught real corruption: assert `max |mix| < 2`; assert the fitted gain is within 0.8–1.25; assert stems sum to the verified mix;
   re-run when `ffmpeg` segfaults or `loudnorm` reports an absurd measured value. Prefer *re-deriving from a verified file* over recomputing from scratch.
7. Run audio scripts with the same Python each time (a venv with a different NumPy produced a different mix).

## Software GL for renders

- Remotion: `--gl=swangle` (an Intel iGPU hung the whole laptop with `i915 GPU HANG`), `--concurrency 2–3`, keep `TMPDIR` on disk (a tmpfs `/tmp` of ~5 GB fills with multi-GB scratch).
- HyperFrames: `--no-browser-gpu --workers 4` avoided the hang (~113 min for a long film); never wait with `while pgrep -f <pattern>` (it matches itself).
- Bake colour grades with ffmpeg beforehand (CSS filters/blend modes cost ~2 s/frame in software).

## Repairing a corrupt git object (same hardware problem)

1. `git fsck --full --no-dangling` names the object; `git rev-list --objects --all | grep <sha>` names the file.
2. Fetch the blob from the remote: `gh api -H 'Accept: application/vnd.github.raw' repos/<owner>/<repo>/git/blobs/<sha> > blob`; confirm `git hash-object blob` equals the sha.
3. `git repack` fails while the bad copy is packed. Rebuild the pack without it: `git show-index < pack.idx | awk '{print $2}' | grep -v <sha> | git pack-objects .git/objects/pack/pack`, move the old
   pack/idx/rev aside, then `git hash-object -w blob` (in that order, because git skips the write while the object "exists" in the old pack).
4. `git fsck` until it exits 0; delete leftover `tmp_pack_*`.

Hardware to-dos when it recurs: memtest86+, cooling/thermal paste, BIOS update, SSD SMART check.

---
name: laptop-media-corruption-guard
description: Laptop silently corrupts renders under sustained heat (90C, RAM bit flips): every render/encode must be sealed with tools/media/media_guard.py and re-checked before assembly/upload
metadata:
  type: feedback
  updated: 2026-11-05T16:10:37
---

Diagnosed 2026-11-05 (the owner asked: find why corruption happens and make sure it never reaches output again). Evidence: (1) playwright node binary matched its pip RECORD hash on disk, yet crashed 4x at the SAME instruction (ip 27bd22c) 14:23-14:24 and later ran fine = corrupted copy in RAM/page cache; (2) a long-form ch1_cold.mp4 corrupt identically via cached and O_DIRECT reads = bits flipped in RAM during encode, before write; (3) chrome-headless segfault 14:04; (4) CPU package 90C, throttled to 1.09 GHz during renders; (5) Optane H10 (8086:0975) logs correctable PCIe RxErr at 04:00.0. Userspace RAM test 2 GiB x3 = 0 errors (inconclusive; full memtest86+ needs a reboot). Root cause class: hardware instability under sustained thermal load (RAM/CPU), not software. Rules: (a) seal every rendered/encoded/downloaded media file immediately: python3 -I tools/media/media_guard.py seal FILE (decode check + sha256 sidecar); (b) re-check before assembly/upload: media_guard.py check FILE (detects later changes); (c) render in chunks so one flip costs one chunk; guarded queues: ice-age 08-compose/render_queue_guarded.sh, yama 07-motion/film/tools/render_guarded.sh; (d) fewer workers (2) + nice to lower heat; never run two heavy renders at once; (e) the owner's hardware to-do: overnight memtest86+, clean fans/cooling pad, BIOS update, SSD health (sudo nvme smart-log), optional pcie_aspm=off.

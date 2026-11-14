"""Read Google Flow project data from its own backend responses: no tile clicking.

One page load makes Flow call its batchexecute RPCs. We listen and decode:
  * Zzl0ze - the project's media list
      section 1: [s1_id, _, _, [filename_or_title, ts, _, _, media_id, ...], project]
      section 2: [media_id, project, s1_id, _, _, [ts, prompt, _, _, _, url, spec, ...]]
                 spec[1][0][0] = model key (e.g. "abra_i2v_4s", "omni_flash_i2v_6s_first_last")
                 spec[1][1]    = input frames [(_, role 1=start|2=end, media_id, crop), ...]
  * nzlxg  - credits: payload[0] is the remaining Flow credit balance
Verified against the live Flow UI (October 2026); the RPC shapes can change, so re-check with `flow doctor`.
"""
from __future__ import annotations

import json
from pathlib import Path

from .config import FlowConfig
from .session import flow_session

# The media URL is an lh3 fife URL: bare it returns the JPEG thumbnail; "=m22" returns the 720p MP4
# ("=m18" a 360p MP4). Verified 2026-10-01.
VIDEO_SUFFIX = "=m22"


def _rpc_payloads(body: str):
    for line in body.splitlines():
        if line.startswith('[["wrb.fr"'):
            for e in json.loads(line):
                if e and e[0] == "wrb.fr" and len(e) > 2 and e[2]:
                    yield e[1], json.loads(e[2])


def capture(page, project_url: str, settle_ms: int = 12000) -> dict:
    """Load the project once and return the decoded RPC payloads we care about."""
    got: dict = {}

    def on_resp(r):
        if "batchexecute" not in r.url:
            return
        try:
            body = r.text()
        except Exception:  # noqa: BLE001
            return
        for rpc, payload in _rpc_payloads(body):
            if rpc in ("Zzl0ze", "nzlxg"):
                got[rpc] = payload

    page.on("response", on_resp)
    page.goto(project_url, wait_until="domcontentloaded")
    page.wait_for_timeout(settle_ms)
    for attempt in range(3):                        # some accounts' pages re-navigate right after load, which drops the
        waited = 0                                  # media-list body; wait for it, and if it never decoded, reload once settled
        while "Zzl0ze" not in got and waited < 30000:
            page.wait_for_timeout(2000); waited += 2000
        if "Zzl0ze" in got:
            break
        page.reload(wait_until="domcontentloaded")
        page.wait_for_timeout(settle_ms)
    page.remove_listener("response", on_resp)
    return got


def parse_media(payload) -> dict:
    names = {}                                        # media_id -> filename / title
    for it in payload[1] or []:
        try:
            names[it[3][4]] = it[3][0]
        except (IndexError, TypeError):
            pass
    videos = []
    for rec in payload[2] or []:
        try:
            body = rec[5]
            spec = body[6]
            model = spec[1][0][0]
            # Text-to-video has no frame inputs; keep those records visible for
            # prompt-based reconciliation instead of silently discarding them.
            inputs = spec[1][1] if len(spec[1]) > 1 else []
            frames = {f[1]: f[2] for f in (inputs or [])}
        except (IndexError, TypeError):
            continue                                  # an image record, not a generated video
        videos.append({"media_id": rec[0], "model": model, "url": body[5], "prompt": body[1],
                       "title": names.get(rec[0]),
                       "start": names.get(frames.get(1)), "end": names.get(frames.get(2)),
                       "created": body[0][0] if body and body[0] else None})
    return {"videos": videos, "names": names}


def project_state(cfg: FlowConfig | None = None, page=None) -> dict:
    cfg = (cfg or FlowConfig()).ensure_dirs()

    def run(pg):
        got = capture(pg, cfg.project_url)
        media = parse_media(got["Zzl0ze"]) if "Zzl0ze" in got else {"videos": [], "names": {}}
        credits = got.get("nzlxg", [None])[0]
        return {"credits": credits, **media}

    if page is not None:
        return run(page)
    with flow_session(cfg) as (_, pg):
        return run(pg)


def download_by_start_frame(project: Path, cfg: FlowConfig | None = None, beats: list[str] | None = None,
                            overwrite: bool = False) -> dict:
    """Download each video whose START frame is `<beat>.png` to 06-video/clips/<beat>_v1.mp4.
    Binding is exact: Flow records which uploaded file each video was generated from."""
    project = Path(project)
    cfg = (cfg or FlowConfig()).ensure_dirs()
    plan = json.loads((project / "05-visuals/shot_plan.json").read_text())
    cfg.project_url = plan.get("flow_project_url", cfg.project_url)
    clips = project / "06-video/clips"
    clips.mkdir(parents=True, exist_ok=True)
    report = {"saved": [], "skipped": [], "missing": []}
    with flow_session(cfg) as (_, page):
        st = project_state(cfg, page)
        report["credits"] = st["credits"]
        by_start: dict = {}
        for v in sorted(st["videos"], key=lambda v: v["created"] or 0):
            if v["start"]:
                by_start[Path(v["start"]).stem] = v          # newest take per start frame wins
        want = beats or [b["id"] for b in plan["beats"]]
        for beat in want:
            v = by_start.get(beat)
            out = clips / f"{beat}_v1.mp4"
            if not v:
                report["missing"].append(beat)
                continue
            if out.exists() and not overwrite:
                report["skipped"].append(beat)
                continue
            try:
                r = page.request.get(v["url"] + VIDEO_SUFFIX, timeout=180000)
            except Exception as e:  # noqa: BLE001
                report["missing"].append(f"{beat} (download error {str(e)[:60]})")
                continue
            if r.status != 200 or "video" not in (r.headers.get("content-type") or ""):
                report["missing"].append(f"{beat} (HTTP {r.status} {r.headers.get('content-type')})")
                continue
            out.write_bytes(r.body())
            report["saved"].append({"beat": beat, "model": v["model"], "start": v["start"], "end": v["end"],
                                    "bytes": len(r.body())})
    return report

"""Read ChatGPT conversation data from inside the signed-in page (the same calls the web app makes)."""
from __future__ import annotations

import base64
import random
import time

MIN_GAP_S = 4.0                 # minimum spacing between ANY two backend calls from this process (all tabs)
_last_call = [0.0]
_paused_until = [0.0]


def _throttle() -> None:
    now = time.time()
    wait = max(_last_call[0] + MIN_GAP_S - now, _paused_until[0] - now, 0.0)
    if wait > 0:
        time.sleep(wait + random.uniform(0, 0.8))
    _last_call[0] = time.time()


def pause_all(seconds: float) -> None:
    """A 429 on one tab pauses every tab: they share one account's quota."""
    _paused_until[0] = max(_paused_until[0], time.time() + seconds)

CONV_JS = r"""async (conv) => {
  const __tok = async () => {
    if (window.__cgTok && window.__cgTokExp > Date.now()) return window.__cgTok;
    const r = await fetch('/api/auth/session');
    if (!r.ok) return null;
    const s = await r.json();
    window.__cgTok = s.accessToken; window.__cgTokExp = Date.now() + 10 * 60 * 1000;
    return window.__cgTok;
  };
  const tk = await __tok();
  if (!tk) return {status: 429, retry_after: 120, where: 'session'};
  const r = await fetch('/backend-api/conversation/' + conv, {headers: {Authorization: 'Bearer ' + tk}});
  if (r.status === 401) window.__cgTok = null;
  if (!r.ok) return {status: r.status, retry_after: Number(r.headers.get('retry-after')) || null};
  const j = await r.json();
  const nodes = {};
  for (const [id, n] of Object.entries(j.mapping || {})) {
    const m = n.message;
    const imgs = [];
    let text = '';
    if (m && m.content) {
      for (const p of (m.content.parts || [])) {
        if (typeof p === 'string') text += p;
        else if (p && p.content_type === 'image_asset_pointer') imgs.push({ptr: p.asset_pointer, w: p.width, h: p.height});
      }
    }
    nodes[id] = {parent: n.parent, children: n.children || [], role: m ? m.author.role : null,
                 t: m ? m.create_time : null, text: text.slice(0, 400), imgs,
                 status: m ? m.status : null};
  }
  return {status: 200, title: j.title, current: j.current_node, nodes};
}"""

FILE_JS = r"""async ([fid, conv]) => {
  const __tok = async () => {
    if (window.__cgTok && window.__cgTokExp > Date.now()) return window.__cgTok;
    const r = await fetch('/api/auth/session');
    if (!r.ok) return null;
    const s = await r.json();
    window.__cgTok = s.accessToken; window.__cgTokExp = Date.now() + 10 * 60 * 1000;
    return window.__cgTok;
  };
  const tk = await __tok();
  if (!tk) return {status: 429, retry_after: 120, where: 'session'};
  const h = {Authorization: 'Bearer ' + tk};
  const mr = await fetch('/backend-api/files/download/' + fid + '?conversation_id=' + conv + '&inline=false', {headers: h});
  if (mr.status === 429) return {error: 'HTTP 429', status: 429, retry_after: Number(mr.headers.get('retry-after')) || null};
  const meta = await mr.json();
  if (!meta.download_url) return {error: JSON.stringify(meta).slice(0, 300)};
  const b = await (await fetch(meta.download_url, {headers: h})).blob();
  const data = await new Promise(res => { const f = new FileReader(); f.onload = () => res(f.result.split(',')[1]); f.readAsDataURL(b); });
  return {type: b.type, data};
}"""


RECENT_JS = r"""async (gizmo) => {
  const __tok = async () => {
    if (window.__cgTok && window.__cgTokExp > Date.now()) return window.__cgTok;
    const r = await fetch('/api/auth/session');
    if (!r.ok) return null;
    const s = await r.json();
    window.__cgTok = s.accessToken; window.__cgTokExp = Date.now() + 10 * 60 * 1000;
    return window.__cgTok;
  };
  const tk = await __tok();
  if (!tk) return [];
  const h = {Authorization: 'Bearer ' + tk};
  const urls = [];
  if (gizmo) urls.push('/backend-api/gizmos/' + gizmo + '/conversations?cursor=0');
  urls.push('/backend-api/conversations?offset=0&limit=10&order=updated');
  for (const u of urls) {
    const r = await fetch(u, {headers: h});
    if (!r.ok) continue;
    const j = await r.json();
    const items = (j.items || []).map(c => ({id: c.id, title: c.title, update_time: c.update_time, create_time: c.create_time}));
    if (items.length) return items;
  }
  return [];
}"""


def resolve_conv_id(page, url_id: str | None, gizmo: str | None, after_t: float) -> str | None:
    """New chats can carry a temporary 'local-...' id in the URL; map it to the real server id by taking the
    newest conversation (in the project when known) created after the submission."""
    if url_id and not url_id.startswith("local-"):
        return url_id
    _throttle()
    items = page.evaluate(RECENT_JS, gizmo)
    def ts(v):
        if isinstance(v, (int, float)): return float(v)
        try:
            from datetime import datetime
            return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0
    fresh = [c for c in items if ts(c.get("create_time")) >= after_t - 30]
    return max(fresh, key=lambda c: ts(c.get("create_time")))["id"] if fresh else None


def conversation(page, conv_id: str) -> dict:
    _throttle()
    r = page.evaluate(CONV_JS, conv_id)
    if r.get("status") == 429:
        pause_all(r.get("retry_after") or 90)
    return r


def conv_id_from_url(url: str) -> str | None:
    return url.rstrip("/").split("/c/")[-1] if "/c/" in url else None


def replies_to(conv: dict, user_text_head: str, after_t: float) -> list[dict]:
    """Generated images in the subtree under the user message that starts with `user_text_head`
    and was created after `after_t`. Exact binding: an image belongs to the message it answers."""
    nodes = conv.get("nodes", {})
    norm = lambda t: " ".join((t or "").split())[:120]
    head = norm(user_text_head)
    users = [(nid, n) for nid, n in nodes.items()
             if n["role"] == "user" and (n["t"] or 0) >= after_t - 5 and norm(n["text"]) == head]
    if not users:
        return []
    uid = max(users, key=lambda x: x[1]["t"] or 0)[0]
    out, stack = [], list(nodes[uid]["children"])
    while stack:
        nid = stack.pop()
        n = nodes.get(nid)
        if not n:
            continue
        if n["role"] != "user":
            for im in n["imgs"]:
                out.append({"node": nid, "ptr": im["ptr"], "w": im["w"], "h": im["h"], "t": n["t"],
                            "status": n["status"]})
            stack.extend(n["children"])
    return sorted(out, key=lambda x: x["t"] or 0)


def text_replies_to(conv: dict, user_text_head: str, after_t: float) -> list[str]:
    """Finished assistant text in the subtree under the matching user message (used to spot a reply
    that answered with words instead of an image, e.g. asking for a missing reference)."""
    nodes = conv.get("nodes", {})
    norm = lambda t: " ".join((t or "").split())[:120]
    head = norm(user_text_head)
    users = [(nid, n) for nid, n in nodes.items()
             if n["role"] == "user" and (n["t"] or 0) >= after_t - 5 and norm(n["text"]) == head]
    if not users:
        return []
    uid = max(users, key=lambda x: x[1]["t"] or 0)[0]
    out, stack = [], list(nodes[uid]["children"])
    while stack:
        n = nodes.get(stack.pop())
        if not n or n["role"] == "user":
            continue
        if n["role"] == "tool" or n["imgs"]:
            return []                    # an image tool step exists: the image is coming, not a text-only answer
        if n["role"] == "assistant" and (n["text"] or "").strip() and n["status"] in (None, "finished_successfully"):
            out.append((n["t"] or 0, n["text"].strip()))
        stack.extend(n["children"])
    return [t for _, t in sorted(out)]


def download(page, ptr: str, conv_id: str) -> tuple[bytes, str]:
    fid = ptr.split("://")[-1]
    for attempt in range(4):                      # 429 on a download: back off and retry instead of failing
        _throttle()
        r = page.evaluate(FILE_JS, [fid, conv_id])
        if r.get("status") != 429:
            break
        wait = r.get("retry_after") or 60 * (2 ** attempt)
        pause_all(wait)
    if "error" in r:
        raise RuntimeError(f"download failed for {fid}: {r['error']}")
    return base64.b64decode(r["data"]), r["type"]

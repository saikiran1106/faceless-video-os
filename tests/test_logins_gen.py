"""`faceless login` / `faceless gen` plumbing that runs without a browser, a network or a real Codex."""
from __future__ import annotations

import json
import os
import stat

import pytest

from faceless import gen, logins


@pytest.fixture()
def home(tmp_path, monkeypatch):
    monkeypatch.setattr(logins, "HOME", tmp_path / ".faceless")
    monkeypatch.setattr(logins, "CONFIG", tmp_path / ".faceless" / "media.json")
    monkeypatch.setattr(logins, "PROFILES", tmp_path / ".faceless" / "browser-profiles")
    monkeypatch.setattr(logins, "ACCOUNTS", tmp_path / "accounts.json")
    return tmp_path


def test_save_mirrors_profiles_into_accounts_json(home):
    cfg = {"images": {"via": "browser", "profiles": [{"name": "chatgpt-1", "dir": "/x/chatgpt-1", "signed_in": True}]},
           "flow": {"profiles": [{"name": "flow-1", "dir": "/x/flow-1", "project_url": "https://flow.google.com/project/abc"}]}}
    (home / "accounts.json").write_text(json.dumps({"profiles": {"keep-me": {"dir": "/y"}}}))
    logins.save(cfg)
    acc = json.loads((home / "accounts.json").read_text())["profiles"]
    assert set(acc) == {"keep-me", "chatgpt-1", "flow-1"}
    assert acc["flow-1"]["channel"] == "chrome" and acc["chatgpt-1"]["services"]["chatgpt"]["check"] == "chatgpt"
    assert logins.load()["images"]["via"] == "browser"


def test_profile_dirs_are_private(home):
    d = logins._profile_dir("flow-2")
    assert d.is_dir() and stat.S_IMODE(os.stat(d).st_mode) == 0o700


def test_set_project_url(home):
    logins.save({"images": {}, "flow": {"profiles": [{"name": "flow-1", "dir": "/x"}]}})
    logins.set_project_url("flow-1", "https://flow.google.com/project/123")
    assert logins.load()["flow"]["profiles"][0]["project_url"].endswith("/123")
    with pytest.raises(SystemExit):
        logins.set_project_url("flow-9", "u")


def test_codex_status_when_missing(monkeypatch):
    monkeypatch.setattr(logins, "_codex_bin", lambda: None)
    assert logins.codex_status() == {"installed": False, "signed_in": False}


def test_codex_image_bound_by_session_id(tmp_path, monkeypatch):
    """The image is taken from ~/.codex/generated_images/<session id>/ announced in the --json stream."""
    images = tmp_path / "generated_images"
    (images / "sess-1").mkdir(parents=True)
    (images / "sess-1" / "img.png").write_bytes(b"\x89PNG fake")
    (images / "other").mkdir()
    (images / "other" / "newer.png").write_bytes(b"\x89PNG other")
    monkeypatch.setattr(gen, "CODEX_IMAGES", images)

    class R:
        returncode = 0
        stdout = '{"type":"thread.started","thread_id":"sess-1"}\n{"type":"turn.completed"}\n'
        stderr = ""

    seen = {}

    def fake_run(cmd, **kw):
        seen["cmd"], seen["input"] = cmd, kw["input"]
        return R()

    monkeypatch.setattr(gen.subprocess, "run", fake_run)
    out = tmp_path / "out" / "P01.png"
    out.parent.mkdir()
    r = gen._codex_one("codex", {"id": "P01", "prompt": "a wolf", "aspect": "16:9"}, out, 60)
    assert r["ok"] and r["bound_by"] == "codex session sess-1" and out.read_bytes() == b"\x89PNG fake"
    assert "--json" in seen["cmd"] and "16:9" in seen["input"] and "exactly ONE image" in seen["input"]


def test_gen_images_requires_a_connected_generator(home, tmp_path):
    with pytest.raises(SystemExit, match="faceless login images"):
        gen.images([{"id": "a", "prompt": "p"}], tmp_path / "o")


def test_gen_images_skips_existing(home, tmp_path):
    (tmp_path / "o").mkdir()
    (tmp_path / "o" / "a.png").write_bytes(b"x")
    r = gen.images([{"id": "a", "prompt": "p"}], tmp_path / "o", via="codex")
    assert r["done"] == 0

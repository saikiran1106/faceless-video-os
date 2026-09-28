import shutil

import pytest

from faceless import config


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_demo_pipeline_reaches_compose_without_keys(tmp_path, monkeypatch):
    """Every stage up to compose passes its gate with no API keys."""
    monkeypatch.setattr(config, "repo_root", lambda start=None: tmp_path)
    import faceless.demo as demo

    monkeypatch.setattr(demo, "repo_root", lambda start=None: tmp_path)
    result = demo.run_demo("short", render=False)
    assert result["next"]["stage"] == "compose"

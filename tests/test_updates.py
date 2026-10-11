from __future__ import annotations

from core import updates


class _FakeResp:
    def __init__(self, payload: bytes):
        self._payload = payload
        self._pos = 0

    def read(self, n: int = -1) -> bytes:
        # shutil.copyfileobj chama read(bufsize) até EOF (b"").
        if self._pos >= len(self._payload):
            return b""
        if n is None or n < 0:
            chunk = self._payload[self._pos :]
            self._pos = len(self._payload)
            return chunk
        chunk = self._payload[self._pos : self._pos + n]
        self._pos += len(chunk)
        return chunk

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


def test_cached_http_get_uses_mem_cache(monkeypatch):
    updates._MEM_CACHE.clear()
    calls = {"n": 0}

    def _fake_urlopen(req, timeout=0):  # nosec
        calls["n"] += 1
        return _FakeResp(b'{"ok": true}')

    monkeypatch.setattr(updates.urllib.request, "urlopen", _fake_urlopen)
    url = "https://api.github.com/repos/LNH-team/pico-launcher/releases/latest"
    first = updates._cached_http_get(url)
    second = updates._cached_http_get(url)
    assert first == second
    assert calls["n"] == 1


def test_install_latest_rejects_missing_digest(monkeypatch, fake_sd):
    def _fake_latest(_repo):
        return {
            "tag_name": "v9.9.9",
            "assets": [
                {
                    "name": "Pico_Launcher.zip",
                    "browser_download_url": "https://github.com/LNH-team/pico-launcher/releases/download/v9.9.9/Pico_Launcher.zip",
                }
            ],
        }

    monkeypatch.setattr(updates, "_github_latest_release", _fake_latest)
    out = updates.install_dspico_component(
        str(fake_sd), "pico-launcher", "latest"
    )
    assert out["success"] is False
    assert "digest" in out["error"].lower()


def test_download_asset_digest_mismatch(monkeypatch, tmp_path):
    monkeypatch.setattr(updates, "CACHE_DIR", str(tmp_path / "cache"))

    asset = {
        "name": "mass-storage.nds",
        "browser_download_url": "https://github.com/LNH-team/dspico-usb-examples/releases/download/v1.2.0/mass-storage.nds",
        "digest": "sha256:" + ("a" * 64),
    }

    def _fake_urlopen(req, timeout=0):  # nosec
        return _FakeResp(b"not-the-same")

    monkeypatch.setattr(updates.urllib.request, "urlopen", _fake_urlopen)
    try:
        updates._download_asset_verified(asset, lambda _msg: None)
        assert False, "era esperado falhar por digest"
    except RuntimeError as e:
        assert "digest" in str(e).lower()

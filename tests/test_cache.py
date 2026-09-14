import hashlib
import os

import pytest

from core import cache


def test_reject_html_and_small(fake_cache, monkeypatch):
    target = os.path.join(str(fake_cache), "dumptool.nds")
    with open(target, "w") as f:
        f.write("<html>not a rom</html>")
    assert cache._is_valid_cached("dumptool", target) is False


def test_pin_mismatch_rejected(fake_cache, monkeypatch):
    target = os.path.join(str(fake_cache), "dumptool.nds")
    data = b"x" * 4096
    with open(target, "wb") as f:
        f.write(data)
    # sidecar com hash errado / pin diferente
    assert cache._is_valid_cached("dumptool", target) is False


def test_valid_pin_accepted(fake_cache, monkeypatch):
    key = "dumptool"
    target = os.path.join(str(fake_cache), cache.FILENAMES[key])
    # Escreve bytes cujo hash == pin (impossível facilmente) — mock do pin
    data = b"A" * 4096
    digest = hashlib.sha256(data).hexdigest()
    monkeypatch.setitem(cache.PINNED_SHA256, key, digest)
    with open(target, "wb") as f:
        f.write(data)
    assert cache._is_valid_cached(key, target) is True


def test_download_rejects_non_https(fake_cache):
    with pytest.raises(ValueError, match="HTTPS"):
        cache.download_url("http://example.com/x", os.path.join(str(fake_cache), "x.bin"))


def test_ensure_cached_requires_pin(fake_cache, monkeypatch):
    monkeypatch.delitem(cache.PINNED_SHA256, "dumptool", raising=False)
    with pytest.raises(ValueError, match="pin"):
        cache.ensure_cached("dumptool")


def test_urls_for_and_ensure_cached_tries_mirrors(fake_cache, monkeypatch):
    key = "dumptool"
    data = b"MIRROR-OK" + b"\x00" * 2048
    digest = hashlib.sha256(data).hexdigest()
    monkeypatch.setitem(cache.PINNED_SHA256, key, digest)
    monkeypatch.setitem(
        cache.URLS,
        key,
        [
            "https://example.invalid/missing.nds",
            "https://example.com/good.nds",
        ],
    )

    calls = []

    def fake_download(url, target_path, log_callback=None):
        calls.append(url)
        if "missing" in url:
            raise OSError("offline")
        with open(target_path, "wb") as f:
            f.write(data)

    monkeypatch.setattr(cache, "download_url", fake_download)
    path = cache.ensure_cached(key)
    assert os.path.isfile(path)
    assert len(calls) == 2
    assert calls[0].endswith("missing.nds")
    assert cache.urls_for(key) == [
        "https://example.invalid/missing.nds",
        "https://example.com/good.nds",
    ]

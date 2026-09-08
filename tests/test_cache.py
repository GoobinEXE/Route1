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

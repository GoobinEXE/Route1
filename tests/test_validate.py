from core import validate
from tests.conftest import make_nds


def test_nds_header_crc(tmp_path):
    p = tmp_path / "a.nds"
    make_nds(p)
    ok, msg = validate.validate_nds_header(str(p))
    assert ok, msg


def test_nds_header_bad_crc(tmp_path):
    p = tmp_path / "b.nds"
    make_nds(p)
    data = bytearray(p.read_bytes())
    data[0x15E] ^= 0xFF
    p.write_bytes(data)
    ok, msg = validate.validate_nds_header(str(p))
    assert not ok


def test_pit_size(tmp_path):
    p = tmp_path / "pit.bin"
    p.write_bytes(b"x" * 48032)
    ok, _ = validate.validate_pit_file(str(p), "pit_facebook")
    assert ok
    p.write_bytes(b"x" * 100)
    ok, _ = validate.validate_pit_file(str(p), "pit_facebook")
    assert not ok

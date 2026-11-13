"""clean_macos_metadata: remove lixo do macOS mas mantém .fseventsd/no_log (impede o macOS de indexar o SD)."""

from core.cleaner import clean_macos_metadata


def test_keeps_prevention_only_fseventsd_and_removes_other_junk(fake_sd):
    (fake_sd / ".fseventsd").mkdir()
    (fake_sd / ".fseventsd" / "no_log").write_bytes(b"")
    (fake_sd / ".Spotlight-V100").mkdir()
    (fake_sd / "._game.nds").write_bytes(b"x")
    clean_macos_metadata(str(fake_sd))
    assert (fake_sd / ".fseventsd" / "no_log").exists()
    assert not (fake_sd / ".Spotlight-V100").exists()
    assert not (fake_sd / "._game.nds").exists()


def test_removes_fseventsd_with_event_logs(fake_sd):
    (fake_sd / ".fseventsd").mkdir()
    (fake_sd / ".fseventsd" / "0000000000a1b2c3").write_bytes(b"log")
    clean_macos_metadata(str(fake_sd))
    assert not (fake_sd / ".fseventsd").exists()

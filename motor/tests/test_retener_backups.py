import datetime as dt
import os

from motor.retener_backups import inventory, select


def item(tmp, name, stamp, size=1):
    p = tmp / name
    p.mkdir()
    (p / "face_enc_v2.bak").write_bytes(b"x" * size)
    return p, stamp


def test_select_preserves_recent_hourly_daily(tmp_path):
    now = dt.datetime(2026, 10, 2, 12, 0, 0)
    root = tmp_path / "backups"
    root.mkdir()
    for i in range(100):
        stamp = now - dt.timedelta(hours=i)
        name = stamp.strftime("%Y%m%d_%H%M%S_consolidar")
        p = root / name
        p.mkdir()
        (p / "face_enc_v2.bak").write_bytes(b"x")
    items = inventory(str(root))
    keep, purge = select(items, now)
    assert keep
    assert purge
    assert len(keep) >= 50
    assert items[0]["path"] in {x["path"] for x in keep}


def test_inventory_ignores_other_backup_types(tmp_path):
    root = tmp_path / "backups"
    root.mkdir()
    (root / "20261002_100000_consolidar").mkdir()
    (root / "20261002_100000_reparacion").mkdir()
    assert len(inventory(str(root))) == 1

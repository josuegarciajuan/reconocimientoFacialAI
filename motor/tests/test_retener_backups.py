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


# ---------------------------------------------------------------------------
# Retención del spool del pool (returns/ + processed/)
# ---------------------------------------------------------------------------

def test_select_pool_purga_solo_antiguo():
    from motor.retener_backups import select_pool
    now = dt.datetime(2026, 10, 14, 12, 0, 0)
    items = [
        {"name": "returns/nuevo", "path": "/x/nuevo", "kind": "dir",
         "ts": now - dt.timedelta(minutes=10)},
        {"name": "returns/viejo", "path": "/x/viejo", "kind": "dir",
         "ts": now - dt.timedelta(hours=30)},
        {"name": "processed/antiguo", "path": "/y/antiguo", "kind": "file",
         "ts": now - dt.timedelta(days=5)},
    ]
    keep, purge = select_pool(items, now, protect_hours=2)
    assert {x["name"] for x in purge} == {"returns/viejo", "processed/antiguo"}
    assert {x["name"] for x in keep} == {"returns/nuevo"}


def test_inventory_pool_lista_returns_y_processed(tmp_path, monkeypatch):
    import motor.retener_backups as rb
    rroot = tmp_path / "returns"
    proot = tmp_path / "processed"
    (rroot / "jobA").mkdir(parents=True)
    proot.mkdir()
    (proot / "reqA.json").write_text("{}")
    monkeypatch.setattr(rb, "RETURNS_DIR", str(rroot))
    monkeypatch.setattr(rb, "PROCESSED_DIR", str(proot))
    items = rb.inventory_pool()
    names = {x["name"] for x in items}
    assert "returns/jobA" in names
    assert "processed/reqA.json" in names

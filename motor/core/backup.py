"""Reversibilidad de fusiones/backfill (F6): snapshot + journal + rollback.

Hoy las fusiones son irreversibles (`DELETE FROM personas`, `UPDATE estancias`,
`store.merge` con pop del source sin registro). Este módulo añade:

  - SNAPSHOT pre-op automático:
      * face_enc_v2.bak      (copia pickle del diccionario completo)
      * db_snapshot.sql      (mysqldump --add-drop-table de personas/estancias/fotos)
    en `motor/backups/<ts>_<op>/`.
  - JOURNAL JSONL por acción (auditoría y reversión documentada).
  - ROLLBACK (`--rollback <dir>`): restaura BD desde el dump + store desde el
    snapshot (estado completo previo) y verifica recuentos antes/después.

Regla de seguridad: los snapshots viven en motor/backups/ (gitignored);
git = código, no datos.
"""
from __future__ import annotations

import json
import os
import subprocess
import time

from filelock import FileLock

from .env import load_env


# ---------------------------------------------------------------------------
# BD vía CLI mysql/mysqldump (el venv no trae driver MySQL; patrón existente)
# ---------------------------------------------------------------------------

def _db_env(ruta: str) -> dict:
    env = load_env(ruta)
    return {
        "user": env.get("RF_DB_USER", "root"),
        "pass": env.get("RF_DB_PASS", ""),
        "host": env.get("RF_DB_HOST", "localhost"),
        "name": env.get("RF_DB_NAME", "reconocimientofacial"),
    }


def _mysql(ruta: str, sql: str) -> list[str]:
    d = _db_env(ruta)
    cmd = ["mysql", "-u", d["user"], "-p" + d["pass"], "-h", d["host"], d["name"],
           "-N", "-e", sql]
    out = subprocess.run(cmd, capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"mysql error: {out.stderr.strip()}")
    return [l for l in out.stdout.strip().splitlines() if l.strip()]


def snapshot_db(ruta: str, out_dir: str) -> str:
    """Dump restaurable (--add-drop-table) de las 3 tablas de identidad."""
    d = _db_env(ruta)
    path = os.path.join(out_dir, "db_snapshot.sql")
    cmd = ["mysqldump", "-u", d["user"], "-p" + d["pass"], "-h", d["host"],
           "--no-tablespaces", "--add-drop-table", "--single-transaction",
           d["name"], "personas", "estancias", "fotos"]
    with open(path, "w") as fh:
        subprocess.run(cmd, stdout=fh, check=True)
    return path


def restore_db(ruta: str, sql_path: str) -> None:
    """Restaura la BD desde el dump (DROP + CREATE + INSERT de las 3 tablas)."""
    d = _db_env(ruta)
    cmd = ["mysql", "-u", d["user"], "-p" + d["pass"], "-h", d["host"], d["name"]]
    with open(sql_path) as fh:
        subprocess.run(cmd, stdin=fh, check=True)


def count_personas(ruta: str) -> int:
    return int(_mysql(ruta, "SELECT COUNT(*) FROM personas")[0])


def count_estancias(ruta: str) -> int:
    return int(_mysql(ruta, "SELECT COUNT(*) FROM estancias")[0])


# ---------------------------------------------------------------------------
# Journal JSONL (append-only, con flock)
# ---------------------------------------------------------------------------

class Journal:
    def __init__(self, path: str):
        self.path = path

    def append(self, entry: dict) -> None:
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        with FileLock(self.path + ".lock"):
            with open(self.path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, default=str) + "\n")

    def entries(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with FileLock(self.path + ".lock"):
            with open(self.path, encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            out.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        return out


# ---------------------------------------------------------------------------
# Creación de directorios de backup
# ---------------------------------------------------------------------------

def new_backup_dir(ruta: str, op: str) -> str:
    ts = time.strftime("%Y%m%d_%H%M%S")
    out_dir = os.path.join(ruta, "motor/backups", f"{ts}_{op}")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def write_manifest(out_dir: str, **meta) -> None:
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump({"ts": time.time(), **meta}, fh, indent=2, default=str)


def verify_restore(ruta: str, store, before_counts: dict, journal_entries: int) -> None:
    """Verifica recuentos BD/diccionario tras el rollback."""
    now = {"personas": count_personas(ruta),
           "estancias": count_estancias(ruta),
           "store_persons": len(store.persons())}
    ok = (now["personas"] == before_counts.get("personas")
          and now["estancias"] == before_counts.get("estancias")
          and now["store_persons"] == before_counts.get("store_persons"))
    print(f"verificación rollback: {'OK' if ok else 'DIVERGENCIA'}")
    print(f"  antes : {before_counts}")
    print(f"  ahora : {now}")
    print(f"  ops en journal: {journal_entries}")
    if not ok:
        raise RuntimeError("rollback incompleto: los recuentos no coinciden")

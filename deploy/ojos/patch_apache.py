#!/usr/bin/env python3
"""Instala el vhost interno y el include público de /ojos (idempotente)."""
from __future__ import annotations

import os
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
APACHE = Path("/etc/apache2")
INCLUDE = "IncludeOptional /etc/apache2/conf-available/rf-ojos-public.conf"
VHOSTS = [APACHE / "sites-available/josue.ink.conf", APACHE / "sites-available/josue.ink-le-ssl.conf"]


def backup(path: Path) -> None:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    dst = path.with_name(path.name + f".bak-ojos-{stamp}")
    if path.exists() and not dst.exists():
        shutil.copy2(path, dst)


def ensure_include(path: Path) -> None:
    text = path.read_text()
    if INCLUDE in text:
        return
    marker = "    CustomLog "
    if marker not in text:
        raise SystemExit(f"no encuentro CustomLog en {path}")
    backup(path)
    text = text.replace(marker, f"    {INCLUDE}\n\n{marker}", 1)
    path.write_text(text)
    print(f"[ojos] include añadido a {path}")


def main() -> int:
    if os.geteuid() != 0:
        raise SystemExit("ejecuta como root")
    (APACHE / "conf-available/rf-ojos-public.conf").write_text(
        (REPO / "deploy/ojos/rf-ojos-public.conf").read_text()
    )
    (APACHE / "sites-available/rf-ojos-internal.conf").write_text(
        (REPO / "deploy/ojos/rf-ojos-internal.conf").read_text()
    )
    for vhost in VHOSTS:
        if not vhost.exists():
            raise SystemExit(f"falta {vhost}")
        ensure_include(vhost)
    link = APACHE / "sites-enabled/rf-ojos-internal.conf"
    if not link.exists():
        link.symlink_to("../sites-available/rf-ojos-internal.conf")
    print("[ojos] Apache configurado")
    return 0


if __name__ == "__main__":
    sys.exit(main())

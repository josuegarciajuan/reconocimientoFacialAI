#!/usr/bin/env python3
"""Añade /ojos al panel-gate (idempotente). No toca secretos."""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

SERVER = Path("/root/panel-gate/server.js")


def main() -> int:
    if not SERVER.is_file():
        raise SystemExit(f"no existe {SERVER}")
    text = SERVER.read_text()
    original = text

    if "BACKEND_OJOS" not in text:
        text = text.replace(
            "const BACKEND_IA = process.env.BACKEND_IA || 'http://127.0.0.1:8140';\n",
            "const BACKEND_IA = process.env.BACKEND_IA || 'http://127.0.0.1:8140';\n"
            "const BACKEND_OJOS = process.env.BACKEND_OJOS || 'http://127.0.0.1:8086';\n",
            1,
        )

    if "return BACKEND_OJOS" not in text:
        needle = "  // IA local (chat): enrutado por path, protegido por el patrón.\n  if (url === '/ia' || url.startsWith('/ia/') || url.startsWith('/ia?')) return BACKEND_IA;\n"
        add = needle + "  // Instancia personal `ojos` (mismo código, pool/BD propios).\n  if (url === '/ojos' || url.startsWith('/ojos/') || url.startsWith('/ojos?')) return BACKEND_OJOS;\n"
        if needle not in text:
            raise SystemExit("no encuentro el bloque de rutas en panel-gate")
        text = text.replace(needle, add, 1)

    if "  '/ojos/',\n" not in text:
        needle = "  '/kinieleitor/',\n];"
        if needle not in text:
            raise SystemExit("no encuentro PUBLIC_PWA_PREFIXES")
        text = text.replace(needle, "  '/kinieleitor/',\n  '/ojos/',\n];", 1)

    # manifest.php dinámico de la PWA de ojos
    text = text.replace(
        "/^(?:.*\\/)?(?:manifest\\.(?:json|webmanifest)|(?:icon(?:-[a-z0-9]+)*|apple-touch-icon|favicon(?:-[0-9]+)?)\\.(?:png|svg|ico|webp))$/i",
        "/^(?:.*\\/)?(?:manifest\\.(?:json|webmanifest|php)|(?:icon(?:-[a-z0-9]+)*|apple-touch-icon|favicon(?:-[0-9]+)?)\\.(?:png|svg|ico|webp))$/i",
    )

    if text == original:
        print("[ojos] panel-gate ya estaba configurado")
        return 0

    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    shutil.copy2(SERVER, SERVER.with_name(SERVER.name + f".bak-ojos-{stamp}"))
    SERVER.write_text(text)
    print("[ojos] panel-gate actualizado")
    return 0


if __name__ == "__main__":
    sys.exit(main())

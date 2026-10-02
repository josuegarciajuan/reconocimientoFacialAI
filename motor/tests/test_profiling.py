"""Perfil de etapas por lote (F16)."""
import json

from motor.core.profiling import Profiler


def test_profiler_acumula_y_convierte_a_ms(tmp_path):
    p = Profiler()
    p.add("matching", 0.5)
    p.add("matching", 0.25)
    p.add("render", 0.1)
    out = tmp_path / "m.jsonl"
    p.emit(str(out), local="1", cam="15", n=3)
    line = out.read_text(encoding="utf-8").strip()
    rec = json.loads(line)
    assert rec["local"] == "1"
    assert rec["n"] == 3
    assert rec["ms"]["matching"] == 750.0
    assert rec["ms"]["render"] == 100.0
    # tras emitir, se resetea
    assert p.snapshot() == {}


def test_profiler_ignora_valores_invalidos():
    p = Profiler()
    p.add("x", None)
    p.add("x", "no-numero")
    p.add("x", -5.0)
    assert p.snapshot().get("x", 0.0) == 0.0

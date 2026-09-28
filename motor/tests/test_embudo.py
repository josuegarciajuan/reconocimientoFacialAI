"""Tests del embudo de recall (Fase 0) — motor/core/embudo.py + motor/embudo.py."""
from __future__ import annotations

from motor.core.embudo import cobertura, leer_eventos, log_evento, resumir


def test_log_y_leer_roundtrip(tmp_path):
    ruta = str(tmp_path)
    log_evento(ruta, "1", "video", cam="3", frames=100, caras_detect=5,
               caras_guard=3, caras_borroso=1, caras_dedup=1, cuerpos=2, cruces=4)
    log_evento(ruta, "1", "descarte", cam="3", motivo="nopasafiltros", n=2)
    log_evento(ruta, "1", "decision", cam="3", verdict="new", branch="scalar")
    log_evento(ruta, "1", "cuerpo", cam="3", resultado="revision", n=2)

    eventos = leer_eventos(ruta, "1")
    assert len(eventos) == 4
    assert eventos[0]["tipo"] == "video"


def test_resumir_agrega_por_tipo(tmp_path):
    ruta = str(tmp_path)
    log_evento(ruta, "1", "video", cam="3", frames=10, caras_detect=4,
               caras_guard=2, caras_borroso=1, caras_dedup=1, cuerpos=1, cruces=2)
    log_evento(ruta, "1", "video", cam="3", frames=20, caras_detect=6,
               caras_guard=5, caras_borroso=1, caras_dedup=0, cuerpos=0, cruces=3)
    log_evento(ruta, "1", "descarte", cam="3", motivo="notienecaras", n=3)
    log_evento(ruta, "1", "descarte", cam="3", motivo="nopasafiltros", n=1)
    log_evento(ruta, "1", "decision", cam="3", verdict="match")
    log_evento(ruta, "1", "decision", cam="3", verdict="new")
    log_evento(ruta, "1", "decision", cam="3", verdict="new")
    log_evento(ruta, "1", "cuerpo", cam="3", resultado="match", n=2)
    log_evento(ruta, "1", "cuerpo", cam="3", resultado="revision", n=1)

    res = resumir(leer_eventos(ruta, "1"))
    t = res["total"]
    assert t["videos"] == 2
    assert t["frames"] == 30
    assert t["caras_detect"] == 10
    assert t["caras_guard"] == 7
    assert t["caras_borroso"] == 2
    assert t["caras_dedup"] == 1
    assert t["descartes_notienecaras"] == 3
    assert t["descartes_nopasafiltros"] == 1
    assert t["verdicts_match"] == 1
    assert t["verdicts_new"] == 2
    assert t["cuerpos_match"] == 2
    assert t["cuerpos_revision"] == 1
    # un solo día/cámara
    assert len(res["por_dia"]) == 1
    assert "3" in list(res["por_dia"].values())[0]


def test_resumir_filtra_por_desde(tmp_path):
    ruta = str(tmp_path)
    log_evento(ruta, "1", "video", cam="3", frames=1)
    eventos = leer_eventos(ruta, "1")
    futura = "2999-01-01"
    assert resumir(eventos, desde=futura)["total"] == {}


def test_cobertura():
    assert cobertura(50, 100) == 0.5
    assert cobertura(200, 100) == 1.0      # recortada a 1.0
    assert cobertura(10, 0) == 0.0         # sin cruces no se puede medir
    assert cobertura("x", 100) == 0.0


def test_eventos_corruptos_se_ignoran(tmp_path):
    ruta = str(tmp_path)
    log_evento(ruta, "1", "video", cam="3", frames=1)
    path = tmp_path / "motor" / "logs" / "embudo_1.jsonl"
    path.write_text(path.read_text() + "{no es json}\n", encoding="utf-8")
    assert len(leer_eventos(ruta, "1")) == 1

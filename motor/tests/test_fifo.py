"""Tests de fifo.py (B3)."""
from motor.fifo import fifo


def test_apilar_y_desapilar():
    f = fifo()
    f.apilar("a").apilar("b")
    assert f.desapilar() == "a"
    assert f.desapilar() == "b"


def test_desapilar_vacio_devuelve_false():
    f = fifo()
    assert f.desapilar() is False


def test_vaciar_permite_seguir_apilando():
    f = fifo()
    f.apilar("a").apilar("b")
    f.vaciar()
    assert f.tamano() == 0
    assert f.desapilar() is False          # no rompe tras vaciar
    f.apilar("c")
    assert f.desapilar() == "c"


def test_apilar_lista():
    f = fifo()
    f.apilar(["a", "b"])
    assert f.tamano() == 2
    assert f.obtenerPila() == ["a", "b"]

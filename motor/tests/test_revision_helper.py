"""Tests de la validación PURA de rutas de motor/revision.py.

No cargan modelos (insightface/cv2/FaceStore): `ruta_revision_segura` y sus
helpers son stdlib pura. Se crea un árbol sintético `motor/revision/<local>/<cam>/`
en tmp_path para los casos válidos.
"""
import os

from motor.revision import componente_valido, es_cara, es_imagen, ruta_revision_segura


def _mk(root, local, cam, nombre):
    d = os.path.join(root, "motor", "revision", local, cam)
    os.makedirs(d, exist_ok=True)
    p = os.path.join(d, nombre)
    with open(p, "w") as fh:
        fh.write("x")
    return p


def test_componente_valido():
    assert componente_valido("abc_1.2-3") is True
    # Nombres reales del motor: llevan ':' en la hora.
    assert componente_valido("19_2026-09-25_17:10:03.604617.mp4_1.500000_0") is True
    assert componente_valido("") is False
    assert componente_valido(".") is False
    assert componente_valido("..") is False
    assert componente_valido("a/b") is False
    assert componente_valido("a\\b") is False
    assert componente_valido("a b") is False


def test_es_imagen():
    assert es_imagen("a.jpg") and es_imagen("a.JPEG") and es_imagen("a.png")
    assert not es_imagen("a.gif") and not es_imagen("a.txt") and not es_imagen("a")


def test_es_cara():
    assert es_cara("19_2026-09-28_17:10:03.604617.mp4_1.5_0.jpg")
    assert es_cara("14_2026-09-28_10:14:08.jpg")
    assert not es_cara("14_2026-09-28_10:14:08_nocara.jpg")
    assert not es_cara("algo_nocara.png")
    assert not es_cara("a.gif")


def test_valida_jpg(tmp_path):
    root = str(tmp_path)
    p = _mk(root, "1", "2", "a.jpg")
    got = ruta_revision_segura(root, "1", "2", "a.jpg")
    assert got == os.path.realpath(p)


def test_valida_png_y_jpeg(tmp_path):
    root = str(tmp_path)
    _mk(root, "1", "2", "a.png")
    _mk(root, "1", "2", "b.jpeg")
    assert ruta_revision_segura(root, "1", "2", "a.png") is not None
    assert ruta_revision_segura(root, "1", "2", "b.jpeg") is not None


def test_traversal_file(tmp_path):
    root = str(tmp_path)
    _mk(root, "1", "2", "a.jpg")
    assert ruta_revision_segura(root, "1", "2", "../a.jpg") is None
    assert ruta_revision_segura(root, "1", "2", "..") is None
    assert ruta_revision_segura(root, "1", "2", ".") is None
    assert ruta_revision_segura(root, "1", "2", "/tmp/fuera.jpg") is None


def test_traversal_local_y_cam(tmp_path):
    root = str(tmp_path)
    _mk(root, "1", "2", "a.jpg")
    assert ruta_revision_segura(root, "../1", "2", "a.jpg") is None
    assert ruta_revision_segura(root, "1", "../2", "a.jpg") is None
    assert ruta_revision_segura(root, "1", "2/3", "a.jpg") is None
    assert ruta_revision_segura(root, "1", "..", "a.jpg") is None


def test_extension_no_imagen(tmp_path):
    root = str(tmp_path)
    _mk(root, "1", "2", "a.txt")
    _mk(root, "1", "2", "a.gif")
    assert ruta_revision_segura(root, "1", "2", "a.txt") is None
    assert ruta_revision_segura(root, "1", "2", "a.gif") is None


def test_fichero_inexistente_no_decide_existencia(tmp_path):
    # La función SOLO valida/confinar la ruta; la existencia la comprueba el
    # llamante (os.path.isfile en _procesar/cmd_descartar).
    root = str(tmp_path)
    _mk(root, "1", "2", "a.jpg")
    got = ruta_revision_segura(root, "1", "2", "noexiste.jpg")
    assert got is not None and os.path.basename(got) == "noexiste.jpg"


def test_symlink_escape(tmp_path):
    root = str(tmp_path)
    _mk(root, "1", "2", "a.jpg")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "exterior.jpg").write_text("x")
    link = tmp_path / "motor" / "revision" / "1" / "2" / "link.jpg"
    try:
        os.symlink(str(outside / "exterior.jpg"), str(link))
    except (OSError, NotImplementedError):
        return
    assert ruta_revision_segura(root, "1", "2", "link.jpg") is None

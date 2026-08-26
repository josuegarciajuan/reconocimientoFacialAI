"""Tests de escritura defensiva de frames durante la captura."""

from motor.core.video import write_frame_safe


class _WriterQueFalla:
    def write(self, frame):
        raise OSError("pipe cerrado")


def test_write_frame_safe_absorbe_excepciones_del_writer():
    errores = []

    resultado = write_frame_safe(_WriterQueFalla(), object(), errores.append)

    assert resultado is False
    assert len(errores) == 1
    assert "pipe cerrado" in errores[0]

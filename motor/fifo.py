"""Buffer FIFO de frames (usado por guarda_movimientos*).

Fixes (B3):
- `desapilar` capturaba `AttributeError`; `deque.popleft()` lanza `IndexError` al estar vacío.
- `vaciar` sustituía el deque por una `list`, rompiendo `popleft` (y `obtenerPila`).
"""
from collections import deque


class fifo:
    def __init__(self):
        self.lista = deque()

    def apilar(self, elemento):
        if isinstance(elemento, (list, tuple)):
            self.lista.extend(elemento)
        else:
            self.lista.append(elemento)
        return self

    def desapilar(self):
        try:
            return self.lista.popleft()
        except IndexError:
            return False

    def vaciar(self):
        self.lista.clear()
        return self

    def tamano(self):
        return len(self.lista)

    def obtenerPila(self):
        return list(self.lista)

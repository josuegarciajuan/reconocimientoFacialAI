"""Añade la raíz del proyecto a sys.path para que `motor.core` sea importable en pytest."""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

"""Tests de quality.py (pose_label): bandas contiguas sin hueco 'other'."""
import numpy as np

from motor.core.quality import pose_label


class _Face:
    def __init__(self, yaw=0.0, pitch=0.0, roll=0.0):
        self.pose = (yaw, pitch, roll)


def test_pose_label_frontal():
    assert pose_label(_Face(yaw=0.0, pitch=0.0)) == "f"
    assert pose_label(_Face(yaw=10.0, pitch=5.0)) == "f"


def test_pose_label_m45_no_gap():
    """fix 2026-08-21: el giro suave 15-22.5° ya NO es 'other' (era una banda
    hueca entre 'f' y 'm45' que fragmentaba identidades)."""
    assert pose_label(_Face(yaw=18.0, pitch=0.0)) == "m45i"
    assert pose_label(_Face(yaw=-18.0, pitch=0.0)) == "m45d"


def test_pose_label_boundaries():
    assert pose_label(_Face(yaw=15.0, pitch=0.0)) == "f"        # justo frontal
    assert pose_label(_Face(yaw=15.1, pitch=0.0)) == "m45i"     # justo fuera
    assert pose_label(_Face(yaw=30.0, pitch=0.0)) == "m45i"
    assert pose_label(_Face(yaw=70.0, pitch=0.0)) == "pi"       # perfil


def test_pose_label_pitch_extremes():
    assert pose_label(_Face(yaw=0.0, pitch=-30.0)) == "arr"
    assert pose_label(_Face(yaw=0.0, pitch=30.0)) == "aba"

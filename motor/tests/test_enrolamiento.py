"""Tests de la política de enrolamiento (motor/enrolamiento.py + config).

El registro solo debe admitir poses útiles: se conservan frontal + giros
moderados (m45) + arriba/abajo, y se descartan los perfiles 90° (pi/pd,
"casi de espaldas") y la pose degenerada (`other`), que ensuciaban la
galería y daban baja tasa de acierto.
"""
from motor.core.config import Config
from motor.core.quality import pose_label


class _Face:
    def __init__(self, yaw=0.0, pitch=0.0, roll=0.0):
        self.pose = (yaw, pitch, roll)


def test_min_poses_incluye_poses_utiles():
    cfg = Config()
    assert "f" in cfg.min_poses
    assert "m45i" in cfg.min_poses
    assert "m45d" in cfg.min_poses
    assert "arr" in cfg.min_poses
    assert "aba" in cfg.min_poses


def test_min_poses_excluye_perfiles_y_degeneradas():
    cfg = Config()
    assert "pi" not in cfg.min_poses   # perfil 90° (casi de espaldas)
    assert "pd" not in cfg.min_poses
    assert "other" not in cfg.min_poses


def test_policy_discarta_perfil_90_y_degrada():
    """La política de enrolamiento acepta f/m45/arr/aba y rechaza pi/pd/other."""
    cfg = Config()
    casos = {
        _Face(yaw=0.0, pitch=0.0): True,     # f -> admitida
        _Face(yaw=30.0, pitch=0.0): True,    # m45i -> admitida
        _Face(yaw=-30.0, pitch=0.0): True,   # m45d -> admitida
        _Face(yaw=0.0, pitch=-30.0): True,   # arr -> admitida
        _Face(yaw=0.0, pitch=30.0): True,    # aba -> admitida
        _Face(yaw=70.0, pitch=0.0): False,   # pi (perfil 90°) -> descartada
        _Face(yaw=-70.0, pitch=0.0): False,  # pd -> descartada
    }
    for face, admitida in casos.items():
        pl = pose_label(face, cfg.yaw_frontal, cfg.yaw_45, cfg.yaw_90, cfg.pitch_frontal)
        assert (pl in cfg.min_poses) is admitida, f"{pl} debería ser {'admitida' if admitida else 'descartada'}"


def test_enrollment_min_sharpness_default_95():
    cfg = Config()
    assert cfg.enrollment_min_sharpness == 95.0

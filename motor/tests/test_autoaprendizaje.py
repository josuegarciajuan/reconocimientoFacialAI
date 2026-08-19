"""Tests del refinamiento de autoaprendizaje (F1 galerías limpias + F4 perfiles mezclados).

Cubre:
  - split_coherent_clusters: sub-clústeres coherentes (no mezclar personas).
  - _store_add con admisión por cara: un impostor agrupado no contamina la galería.
  - store._prune: poda de outliers estructurales.
  - find_mixed_profiles: detecta perfiles con 2-3 caras distintas.
"""
import numpy as np

from motor.clasificador import split_coherent_clusters, _store_add
from motor.core.config import Config
from motor.core.matching import cosine
from motor.core.model import Face
from motor.core.store import FaceStore
from motor.detectar_mezclados import find_mixed_profiles


def _e(k: int, noise: float = 0.0, seed: int = 0) -> np.ndarray:
    """Vector base e_k (ortonormal en 512-d) + ruido opcional."""
    v = np.zeros(512, dtype=np.float64)
    v[k] = 1.0
    if noise > 0:
        rng = np.random.default_rng(seed)
        v = v + noise * rng.standard_normal(512)
    return v / np.linalg.norm(v)


def _face(emb: np.ndarray, seed: int = 0) -> Face:
    return Face(bbox=(0, 0, 10, 10), det_score=0.99,
                embedding=emb.astype(np.float32), pose=(0.0, 0.0, 0.0))


def _item(emb: np.ndarray, idx: int, seed: int = 0) -> dict:
    img = np.full((20, 20, 3), 128, dtype=np.uint8)
    return {"file": f"cam_2026-08-19_10.00.00.000_00000.avi_{idx}.jpg",
            "path": f"/tmp/fake_{idx}.jpg", "img": img,
            "faces": [_face(emb, seed)], "ts": float(idx)}


def _face_list(battery):
    return [(f.embedding, idx) for idx, it in enumerate(battery) for f in it["faces"]]


# ---------------------------------------------------------------------------
# F1.1 split_coherent_clusters
# ---------------------------------------------------------------------------

def test_split_coherent_keep_same_person_together():
    """Caras de la MISMA persona (muy similares) quedan en un solo sub-clúster."""
    cfg = Config()
    a1 = _e(0, noise=0.05, seed=1)
    a2 = _e(0, noise=0.05, seed=2)
    a3 = _e(0, noise=0.05, seed=3)
    battery = [_item(a1, 0), _item(a2, 1), _item(a3, 2)]
    fl = _face_list(battery)
    subs = split_coherent_clusters([0, 1, 2], fl, battery, cfg)
    assert subs == [[0, 1, 2]], f"debería ser 1 sub-clúster: {subs}"
    # el representativo confirma a todos (coseno >= cluster_confirm)
    rep = fl[subs[0][0]][0]
    for i in subs[0]:
        assert cosine(fl[i][0], rep) >= cfg.cluster_confirm


def test_split_coherent_separa_personas_distintas():
    """Dos personas en la misma batería acaban en sub-clústeres separados."""
    cfg = Config()
    a1, a2 = _e(0, noise=0.05, seed=1), _e(0, noise=0.05, seed=2)
    b1, b2 = _e(1, noise=0.05, seed=3), _e(1, noise=0.05, seed=4)
    battery = [_item(a1, 0), _item(a2, 1), _item(b1, 2), _item(b2, 3)]
    fl = _face_list(battery)
    subs = split_coherent_clusters([0, 1, 2, 3], fl, battery, cfg)
    assert len(subs) == 2, f"deberían separarse 2 personas: {subs}"
    sizes = sorted(len(s) for s in subs)
    assert sizes == [2, 2]


def test_split_coherent_rompe_cadena_transitiva():
    """A~B (0.33), B~C (0.33) pero A~C (0.10): el union-find los uniría; el
    sub-clustering coherente debe romper la cadena (no mezclar C con A)."""
    cfg = Config(cluster_confirm=0.35)
    a = _e(0)                      # e0
    c = _e(1)                      # e1  -> cos(a,c) = 0.10? no: e0·e1 = 0
    # construimos b en el subespacio {a, c, w}: b = 0.3a + 0.3c + 0.8956 w
    rng = np.random.default_rng(7)
    w = rng.standard_normal(512)
    w -= a * float(np.dot(a, w))
    w -= c * float(np.dot(c, w))
    w /= np.linalg.norm(w)
    b = 0.3 * a + 0.3 * c + 0.8956 * w
    b /= np.linalg.norm(b)
    # premisa: A~B = B~C = 0.33, A~C ~ 0.00
    assert 0.30 < cosine(a, b) < 0.36
    assert 0.30 < cosine(b, c) < 0.36
    assert cosine(a, c) < 0.05

    battery = [_item(a, 0), _item(b, 1), _item(c, 2)]
    fl = _face_list(battery)
    subs = split_coherent_clusters([0, 1, 2], fl, battery, cfg)
    assert len(subs) >= 2, f"la cadena transitiva debe romperse: {subs}"
    # ningún sub-clúster puede contener a la vez a (item 0) y c (item 2)
    # porque coseno(a,c) ~0.00 << cluster_confirm; y todo miembro confirma al rep.
    for s in subs:
        members = sorted(fl[i][1] for i in s)
        assert not ({0, 2} <= set(members)), f"a y c mezclados en {members}"
        assert all(cosine(fl[i][0], fl[s[0]][0]) >= cfg.cluster_confirm for i in s[1:])


# ---------------------------------------------------------------------------
# F1.2 _store_add con admisión por cara
# ---------------------------------------------------------------------------

def test_store_add_admision_rechaza_impostor(tmp_path):
    """Un impostor agrupado por transitividad NO entra en la galería de la persona."""
    cfg = Config()   # admission_cosine = 0.32
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=50)
    gal = _e(0, noise=0.05, seed=10)
    store.add("A", [gal], [90.0], ["f"])

    genuino = _e(0, noise=0.05, seed=11)      # coseno ~0.99 con A
    impostor = _e(1, noise=0.05, seed=12)     # coseno ~0 con A
    battery = [_item(genuino, 0), _item(impostor, 1)]
    _store_add(store, "A", [0, 1], battery, cfg)

    assert store.count("A") == 2, "solo el genuino debe admitirse (1 previo + 1 nuevo)"
    encs = store.person_encodings("A")
    sims = [float(np.max(encs @ e)) for e in [genuino, impostor]]
    # el impostor no quedó dentro (su similitud máxima contra la galería es ~0)
    assert max(sims) < 0.5 or min(sims) < 0.32


def test_store_add_new_person_admite_todo(tmp_path):
    """Verdict 'new': la coherencia interna ya la garantiza el sub-clúster."""
    cfg = Config()
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=50)
    a1 = _e(3, noise=0.05, seed=20)
    a2 = _e(3, noise=0.05, seed=21)
    battery = [_item(a1, 0), _item(a2, 1)]
    _store_add(store, "NUEVO", [0, 1], battery, cfg, new_person=True)
    assert store.count("NUEVO") == 2


# ---------------------------------------------------------------------------
# F1.4 store._prune: outliers
# ---------------------------------------------------------------------------

def test_prune_elimina_outliers_estructurales(tmp_path):
    """Encodings lejanos al núcleo (media coseno < 0.25) se podan aunque haya
    capacidad: son típicamente impostores de contaminación histórica."""
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=50)
    nucleo = [_e(0, noise=0.05, seed=i) for i in range(7)]
    ruido = [_e(1, noise=0.05, seed=100 + i) for i in range(2)]   # ortogonales al núcleo
    store.add("A", nucleo + ruido, [80.0] * 9, ["f"] * 9)
    assert store.count("A") == 7, "los 2 ruido deben podarse"


def test_prune_conserva_persona_limpia(tmp_path):
    """Una persona limpia con encodings variados pero genuinos no se toca."""
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=50)
    rng = np.random.default_rng(5)
    base = _e(0)
    encs = []
    for i in range(9):
        # ruido 0.01 -> coseno interno ~0.98 (genuino de sobra)
        v = base + 0.01 * rng.standard_normal(512)
        encs.append(v / np.linalg.norm(v))
    store.add("A", encs, [80.0] * 9, ["f"] * 9)
    assert store.count("A") == 9


# ---------------------------------------------------------------------------
# F4 find_mixed_profiles
# ---------------------------------------------------------------------------

def test_find_mixed_profiles_marca_mezclado(tmp_path):
    """Perfil con 2 grupos de caras distintas (3+3) se marca como MIXED."""
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=100)
    g1 = [_e(0, noise=0.05, seed=i) for i in range(3)]
    g2 = [_e(1, noise=0.05, seed=100 + i) for i in range(3)]
    store.add("MIX", g1 + g2, [80.0] * 6, ["f"] * 6)
    out = find_mixed_profiles(store)
    cods = [m["cod"] for m in out]
    assert "MIX" in cods
    m = next(m for m in out if m["cod"] == "MIX")
    assert m["main_size"] == 3
    assert any(a["size"] == 3 for a in m["aliens"])


def test_find_mixed_profiles_no_marca_limpio(tmp_path):
    """Perfil de una sola persona (6 encodings coherentes) no se marca."""
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=100)
    encs = [_e(0, noise=0.05, seed=i) for i in range(6)]
    store.add("CLEAN", encs, [80.0] * 6, ["f"] * 6)
    assert find_mixed_profiles(store) == []


def test_find_mixed_profiles_no_marca_variacion_genuina(tmp_path):
    """Variación genuina de apariencia/pose (puente >= 0.42 con el núcleo) no
    debe marcarse como mezclada (calibrado con la galería real: satélites
    legítimos con max2main 0.53-0.88)."""
    store = FaceStore(str(tmp_path / "face_enc_v2"), max_per_person=100)
    main = [_e(0, noise=0.05, seed=i) for i in range(6)]
    bridge = np.zeros(512)
    bridge[0] = 0.50                     # coseno 0.50 con el núcleo e0 (genuino)
    bridge[2] = np.sqrt(1 - 0.50 ** 2)
    sat = [bridge.astype(np.float32) for _ in range(3)]
    store.add("VAR", main + sat, [80.0] * 9, ["f"] * 9)
    assert find_mixed_profiles(store) == []

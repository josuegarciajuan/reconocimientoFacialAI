"""Ciclo de vida de artefactos del pipeline.

Garantiza que los artefactos producidos por un worker se publiquen de forma
atómica y que la limpieza respete las dependencias entre trabajos.

Conceptos:
- ``Artifact``: fichero o directorio producido por un trabajo.
- ``Manifest``: lista de artefactos con metadatos (checksum, tamaño, estado).
- Un manifiesto solo se hace visible cuando todos sus artefactos están listos.
- La limpieza elimina artefactos no referenciados por ningún manifiesto activo.
"""
from __future__ import annotations

import dataclasses
import json
import os
import shutil
import time
from typing import Any


class ArtifactError(Exception):
    """Error en la gestión de artefactos."""


@dataclasses.dataclass(frozen=True, slots=True)
class Artifact:
    """Referencia a un artefacto producido por un trabajo."""

    artifact_id: str
    path: str
    kind: str
    size: int
    mtime: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "path": self.path,
            "kind": self.kind,
            "size": self.size,
            "mtime": self.mtime,
        }

    @classmethod
    def from_path(cls, artifact_id: str, path: str, kind: str = "file") -> "Artifact":
        st = os.stat(path)
        return cls(
            artifact_id=artifact_id,
            path=path,
            kind=kind,
            size=int(st.st_size),
            mtime=float(st.st_mtime),
        )

    @classmethod
    def missing(cls, artifact_id: str, path: str, kind: str = "file") -> "Artifact":
        return cls(
            artifact_id=artifact_id,
            path=path,
            kind=kind,
            size=0,
            mtime=0.0,
        )


@dataclasses.dataclass(frozen=True, slots=True)
class ArtifactManifest:
    """Manifiesto de artefactos de un resultado."""

    manifest_id: str
    unit_id: str
    job_id: str
    artifacts: list[Artifact]
    created_at: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "manifest_id": self.manifest_id,
            "unit_id": self.unit_id,
            "job_id": self.job_id,
            "artifacts": [a.to_dict() for a in self.artifacts],
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ArtifactManifest":
        return cls(
            manifest_id=str(d["manifest_id"]),
            unit_id=str(d["unit_id"]),
            job_id=str(d["job_id"]),
            artifacts=[Artifact(**a) for a in d.get("artifacts", [])],
            created_at=float(d["created_at"]),
        )

    def is_complete(self) -> bool:
        """Comprueba que todos los artefactos del manifiesto existen."""
        for artifact in self.artifacts:
            if not os.path.exists(artifact.path):
                return False
        return True


class ArtifactLifecycle:
    """Gestor de publicación y limpieza de artefactos."""

    def __init__(self, root_dir: str):
        self.root_dir = root_dir
        self._manifest_dir = os.path.join(root_dir, "manifests")
        self._pending_dir = os.path.join(root_dir, "manifests_pending")
        os.makedirs(self._manifest_dir, exist_ok=True)
        os.makedirs(self._pending_dir, exist_ok=True)

    def _pending_path(self, manifest_id: str) -> str:
        return os.path.join(self._pending_dir, f"{manifest_id}.json")

    def _final_path(self, manifest_id: str) -> str:
        return os.path.join(self._manifest_dir, f"{manifest_id}.json")

    def create_manifest(
        self,
        manifest_id: str,
        unit_id: str,
        job_id: str,
        artifact_paths: dict[str, str],
    ) -> ArtifactManifest:
        """Crea un manifiesto pendiente a partir de rutas de artefactos."""
        artifacts: list[Artifact] = []
        for artifact_id, path in artifact_paths.items():
            if os.path.exists(path):
                kind = "dir" if os.path.isdir(path) else "file"
                artifacts.append(Artifact.from_path(artifact_id, path, kind))
            else:
                artifacts.append(Artifact.missing(artifact_id, path, "file"))
        manifest = ArtifactManifest(
            manifest_id=manifest_id,
            unit_id=unit_id,
            job_id=job_id,
            artifacts=artifacts,
            created_at=time.time(),
        )
        pending = self._pending_path(manifest_id)
        tmp = pending + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(manifest.to_dict(), fh, ensure_ascii=False, indent=2)
        os.replace(tmp, pending)
        return manifest

    def publish_manifest(self, manifest_id: str) -> ArtifactManifest:
        """Hace visible un manifiesto (mv atómico)."""
        pending = self._pending_path(manifest_id)
        final = self._final_path(manifest_id)
        if not os.path.exists(pending):
            raise ArtifactError(f"Manifiesto pendiente no encontrado: {manifest_id}")
        with open(pending, encoding="utf-8") as fh:
            manifest = ArtifactManifest.from_dict(json.load(fh))
        if not manifest.is_complete():
            missing = [a.artifact_id for a in manifest.artifacts if not os.path.exists(a.path)]
            raise ArtifactError(f"Artefactos incompletos: {missing}")
        os.replace(pending, final)
        return manifest

    def get_manifest(self, manifest_id: str) -> ArtifactManifest | None:
        """Lee un manifiesto publicado."""
        final = self._final_path(manifest_id)
        if not os.path.exists(final):
            return None
        try:
            with open(final, encoding="utf-8") as fh:
                return ArtifactManifest.from_dict(json.load(fh))
        except (OSError, json.JSONDecodeError, KeyError):
            return None

    def is_published(self, manifest_id: str) -> bool:
        return os.path.exists(self._final_path(manifest_id))

    def is_complete(self, manifest_id: str) -> bool:
        manifest = self.get_manifest(manifest_id)
        return manifest.is_complete() if manifest else False

    def discard_pending(self, manifest_id: str) -> None:
        """Descarta un manifiesto pendiente (p. ej., tras un error)."""
        pending = self._pending_path(manifest_id)
        if os.path.exists(pending):
            os.remove(pending)

    def list_manifests(self) -> list[ArtifactManifest]:
        """Lista todos los manifiestos publicados."""
        out: list[ArtifactManifest] = []
        if not os.path.isdir(self._manifest_dir):
            return out
        for name in sorted(os.listdir(self._manifest_dir)):
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(self._manifest_dir, name), encoding="utf-8") as fh:
                    out.append(ArtifactManifest.from_dict(json.load(fh)))
            except (OSError, json.JSONDecodeError, KeyError):
                continue
        return out

    def referenced_paths(self) -> set[str]:
        """Conjunto de rutas referenciadas por manifiestos publicados."""
        refs: set[str] = set()
        for manifest in self.list_manifests():
            for artifact in manifest.artifacts:
                refs.add(os.path.abspath(artifact.path))
                if artifact.kind == "dir":
                    for root, _dirs, files in os.walk(artifact.path):
                        for f in files:
                            refs.add(os.path.abspath(os.path.join(root, f)))
        return refs

    def cleanup_unreferenced(
        self,
        directory: str,
        *,
        dry_run: bool = False,
        min_age_s: float = 60.0,
    ) -> list[str]:
        """Elimina ficheros no referenciados por ningún manifiesto publicado.

        Solo borra ficheros más antiguos que ``min_age_s`` para evitar competir
        con trabajos en curso.
        """
        refs = self.referenced_paths()
        removed: list[str] = []
        now = time.time()
        if not os.path.isdir(directory):
            return removed
        for root, _dirs, files in os.walk(directory):
            for f in files:
                path = os.path.abspath(os.path.join(root, f))
                if path in refs:
                    continue
                try:
                    st = os.stat(path)
                    if now - st.st_mtime < min_age_s:
                        continue
                    if dry_run:
                        removed.append(path)
                    else:
                        os.remove(path)
                        removed.append(path)
                except OSError:
                    continue
        return removed

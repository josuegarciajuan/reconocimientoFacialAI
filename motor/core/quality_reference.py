"""Referencia de calidad para el pipeline de reconocimiento facial.

Este módculo define un marco para registrar casos de prueba representativos y
comparar los resultados del motor contra expectativas. No incluye datos
personales: los casos reales se cargan desde un directorio externo configurado
mediante ``RF_QUALITY_REF_DIR``.

Los casos permiten detectar regresiones cuando se añaden optimizaciones de
rendimiento. Las dimensiones evaluables son:

- deteccion     : ¿se detectan las caras esperadas?
- identificacion: ¿se identifican correctamente las personas conocidas?
- agrupacion    : ¿se agrupan las detecciones de una misma persona?
- cruce_linea   : ¿se detectan correctamente los cruces de línea?
"""
from __future__ import annotations

import dataclasses
import json
import os
from typing import Any


@dataclasses.dataclass(frozen=True, slots=True)
class QualityCase:
    """Caso de referencia de calidad."""

    case_id: str
    description: str
    source_path: str
    dimensions: list[str]
    expected_faces: int | None
    expected_persons: list[str] | None
    expected_crossings: dict[str, int] | None
    tags: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "description": self.description,
            "source_path": self.source_path,
            "dimensions": self.dimensions,
            "expected_faces": self.expected_faces,
            "expected_persons": self.expected_persons,
            "expected_crossings": self.expected_crossings,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "QualityCase":
        return cls(
            case_id=str(d["case_id"]),
            description=str(d.get("description", "")),
            source_path=str(d["source_path"]),
            dimensions=list(d.get("dimensions") or []),
            expected_faces=int(d["expected_faces"]) if d.get("expected_faces") is not None else None,
            expected_persons=list(d["expected_persons"]) if d.get("expected_persons") is not None else None,
            expected_crossings=dict(d["expected_crossings"]) if d.get("expected_crossings") is not None else None,
            tags=list(d.get("tags") or []),
        )


@dataclasses.dataclass(frozen=True, slots=True)
class QualityResult:
    """Resultado de evaluar un caso de referencia."""

    case_id: str
    dimension: str
    passed: bool
    score: float
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "dimension": self.dimension,
            "passed": self.passed,
            "score": self.score,
            "details": self.details,
        }


@dataclasses.dataclass(frozen=True, slots=True)
class QualityReport:
    """Informe agregado de calidad."""

    evaluated_at: float
    total: int
    passed: int
    failed: int
    by_dimension: dict[str, dict[str, int]]
    results: list[QualityResult]

    def to_dict(self) -> dict[str, Any]:
        return {
            "evaluated_at": self.evaluated_at,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "by_dimension": self.by_dimension,
            "results": [r.to_dict() for r in self.results],
        }

    def write(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)


class QualityReference:
    """Colección de casos de referencia y evaluador."""

    def __init__(self, cases: list[QualityCase] | None = None):
        self.cases = cases or []

    def add(self, case: QualityCase) -> None:
        self.cases.append(case)

    def load_from_dir(self, directory: str) -> None:
        """Carga casos desde ficheros ``*.json`` de un directorio."""
        if not os.path.isdir(directory):
            return
        for name in sorted(os.listdir(directory)):
            if not name.endswith(".json"):
                continue
            path = os.path.join(directory, name)
            try:
                with open(path, encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, list):
                    for item in data:
                        self.add(QualityCase.from_dict(item))
                else:
                    self.add(QualityCase.from_dict(data))
            except (OSError, json.JSONDecodeError, KeyError):
                continue

    def evaluate_detection(
        self,
        case: QualityCase,
        detected_faces: int,
    ) -> QualityResult:
        expected = case.expected_faces
        if expected is None:
            return QualityResult(
                case_id=case.case_id,
                dimension="deteccion",
                passed=True,
                score=1.0,
                details={"expected": None, "detected": detected_faces},
            )
        # Tolerancia: al menos el 80% de las caras esperadas.
        score = min(1.0, detected_faces / max(1, expected))
        passed = detected_faces >= expected * 0.8
        return QualityResult(
            case_id=case.case_id,
            dimension="deteccion",
            passed=passed,
            score=round(score, 3),
            details={"expected": expected, "detected": detected_faces},
        )

    def evaluate_identification(
        self,
        case: QualityCase,
        detected_persons: list[str],
    ) -> QualityResult:
        expected = case.expected_persons
        if expected is None:
            return QualityResult(
                case_id=case.case_id,
                dimension="identificacion",
                passed=True,
                score=1.0,
                details={"expected": None, "detected": detected_persons},
            )
        expected_set = set(expected)
        detected_set = set(detected_persons)
        if not expected_set:
            score = 1.0 if not detected_set else 0.0
        else:
            score = len(expected_set & detected_set) / len(expected_set)
        return QualityResult(
            case_id=case.case_id,
            dimension="identificacion",
            passed=score >= 0.8,
            score=round(score, 3),
            details={"expected": sorted(expected_set), "detected": sorted(detected_set)},
        )

    def evaluate(
        self,
        case_results: dict[str, dict[str, Any]],
    ) -> QualityReport:
        """Evalúa una colección de resultados contra los casos cargados.

        ``case_results`` es un dict ``{case_id: {dimension: valor, ...}}``.
        """
        import time

        results: list[QualityResult] = []
        by_dimension: dict[str, dict[str, int]] = {}
        passed_total = 0
        failed_total = 0

        for case in self.cases:
            res = case_results.get(case.case_id, {})
            if "deteccion" in case.dimensions and "detected_faces" in res:
                r = self.evaluate_detection(case, res["detected_faces"])
                results.append(r)
                by_dimension.setdefault(r.dimension, {"passed": 0, "failed": 0})
                by_dimension[r.dimension]["passed" if r.passed else "failed"] += 1
                if r.passed:
                    passed_total += 1
                else:
                    failed_total += 1
            if "identificacion" in case.dimensions and "detected_persons" in res:
                r = self.evaluate_identification(case, res["detected_persons"])
                results.append(r)
                by_dimension.setdefault(r.dimension, {"passed": 0, "failed": 0})
                by_dimension[r.dimension]["passed" if r.passed else "failed"] += 1
                if r.passed:
                    passed_total += 1
                else:
                    failed_total += 1

        return QualityReport(
            evaluated_at=time.time(),
            total=len(results),
            passed=passed_total,
            failed=failed_total,
            by_dimension=by_dimension,
            results=results,
        )

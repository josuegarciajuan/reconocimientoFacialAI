"""Gate de calidad para validar optimizaciones.

Compara un informe de calidad actual contra una línea base y detecta
regresiones. Toda optimización del camino crítico debe pasar este gate antes de
activarse: si empeora detección o identificación, se rechaza.

Reglas:
- Un caso que pasaba en la base y falla ahora -> regresión.
- Un score que cae más de ``tolerance`` -> regresión.
- Un caso de la base ausente en el informe actual -> regresión.
"""
from __future__ import annotations

import dataclasses
import json
import os
from typing import Any

from motor.core.quality_reference import QualityReport, QualityResult


@dataclasses.dataclass(frozen=True, slots=True)
class RegressionIssue:
    case_id: str
    dimension: str
    baseline_score: float
    current_score: float
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "dimension": self.dimension,
            "baseline_score": self.baseline_score,
            "current_score": self.current_score,
            "reason": self.reason,
        }


@dataclasses.dataclass(frozen=True, slots=True)
class RegressionReport:
    passed: bool
    tolerance: float
    baseline_passed: int
    current_passed: int
    issues: list[RegressionIssue]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "tolerance": self.tolerance,
            "baseline_passed": self.baseline_passed,
            "current_passed": self.current_passed,
            "issues": [i.to_dict() for i in self.issues],
        }

    def write(self, path: str) -> None:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(self.to_dict(), fh, ensure_ascii=False, indent=2)


class QualityGateError(RuntimeError):
    """Se ha detectado una regresión de calidad."""


def _index(report: QualityReport) -> dict[tuple[str, str], QualityResult]:
    return {(r.case_id, r.dimension): r for r in report.results}


def compare_reports(
    baseline: QualityReport,
    current: QualityReport,
    *,
    tolerance: float = 0.02,
) -> RegressionReport:
    """Compara dos informes y devuelve las regresiones encontradas."""
    base = _index(baseline)
    cur = _index(current)
    issues: list[RegressionIssue] = []

    for key, b in base.items():
        c = cur.get(key)
        case_id, dimension = key
        if c is None:
            issues.append(
                RegressionIssue(
                    case_id=case_id,
                    dimension=dimension,
                    baseline_score=b.score,
                    current_score=0.0,
                    reason="caso ausente en el informe actual",
                )
            )
            continue
        if b.passed and not c.passed:
            issues.append(
                RegressionIssue(
                    case_id=case_id,
                    dimension=dimension,
                    baseline_score=b.score,
                    current_score=c.score,
                    reason="pasaba antes y falla ahora",
                )
            )
            continue
        if c.score < b.score - tolerance:
            issues.append(
                RegressionIssue(
                    case_id=case_id,
                    dimension=dimension,
                    baseline_score=b.score,
                    current_score=c.score,
                    reason=f"score cae más de {tolerance}",
                )
            )

    return RegressionReport(
        passed=not issues,
        tolerance=float(tolerance),
        baseline_passed=int(baseline.passed),
        current_passed=int(current.passed),
        issues=issues,
    )


def assert_no_regression(
    baseline: QualityReport,
    current: QualityReport,
    *,
    tolerance: float = 0.02,
) -> RegressionReport:
    """Como ``compare_reports`` pero lanza ``QualityGateError`` si hay regresión."""
    report = compare_reports(baseline, current, tolerance=tolerance)
    if not report.passed:
        detail = "; ".join(
            f"{i.case_id}/{i.dimension}: {i.reason} ({i.baseline_score} -> {i.current_score})"
            for i in report.issues
        )
        raise QualityGateError(f"Regresión de calidad: {detail}")
    return report


def load_report(path: str) -> QualityReport:
    """Carga un ``QualityReport`` serializado con ``write``."""
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    results = [
        QualityResult(
            case_id=str(r["case_id"]),
            dimension=str(r["dimension"]),
            passed=bool(r["passed"]),
            score=float(r["score"]),
            details=dict(r.get("details") or {}),
        )
        for r in data.get("results", [])
    ]
    return QualityReport(
        evaluated_at=float(data.get("evaluated_at", 0.0)),
        total=int(data.get("total", len(results))),
        passed=int(data.get("passed", 0)),
        failed=int(data.get("failed", 0)),
        by_dimension=dict(data.get("by_dimension") or {}),
        results=results,
    )

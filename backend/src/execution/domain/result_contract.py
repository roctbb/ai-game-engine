from __future__ import annotations

from collections.abc import Mapping

from execution.domain.model import RunKind
from shared.kernel import InvariantViolationError


def validate_result_payload(run_kind: RunKind, payload: dict[str, object]) -> None:
    _require_non_empty_string(payload, "status")

    if run_kind in {RunKind.SINGLE_TASK, RunKind.COMPETITION_MATCH}:
        _require_object(payload, "metrics")

    if run_kind is RunKind.TRAINING_MATCH:
        if "scores" not in payload and "placements" not in payload:
            raise InvariantViolationError(
                "Для training_match result payload должен содержать scores или placements"
            )

    scores = payload.get("scores")
    if scores is not None:
        _require_score_map(scores)

    placements = payload.get("placements")
    parsed_placements: dict[str, int] | None = None
    if placements is not None:
        parsed_placements = _require_placement_map(placements)

    if run_kind is RunKind.COMPETITION_MATCH:
        if parsed_placements is None:
            raise InvariantViolationError(
                "Для competition_match result payload обязан содержать placements"
            )
        _validate_tie_resolution(payload=payload, placements=parsed_placements)


def _validate_tie_resolution(payload: dict[str, object], placements: dict[str, int]) -> None:
    has_duplicate_places = len(set(placements.values())) != len(placements)
    tie_resolution = payload.get("tie_resolution")
    if has_duplicate_places and tie_resolution != "explicit_tie":
        raise InvariantViolationError(
            "При равных placements нужно явно указать tie_resolution='explicit_tie'"
        )
    if not has_duplicate_places and tie_resolution == "explicit_tie":
        raise InvariantViolationError(
            "tie_resolution='explicit_tie' недопустим, когда все placements уникальны"
        )


def _require_non_empty_string(payload: dict[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InvariantViolationError(f"Поле '{key}' должно быть непустой строкой")
    return value


def _require_object(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    if not isinstance(value, dict):
        raise InvariantViolationError(f"Поле '{key}' должно быть объектом")
    return value


def _require_score_map(value: object) -> dict[str, float]:
    if not isinstance(value, Mapping) or not value:
        raise InvariantViolationError("Поле 'scores' должно быть непустым объектом")

    parsed: dict[str, float] = {}
    for key, score in value.items():
        if not isinstance(key, str) or not key.strip():
            raise InvariantViolationError("Ключи 'scores' должны быть непустыми строками")
        if not isinstance(score, (int, float)):
            raise InvariantViolationError("Значения 'scores' должны быть числами")
        parsed[key] = float(score)
    return parsed


def _require_placement_map(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping) or not value:
        raise InvariantViolationError("Поле 'placements' должно быть непустым объектом")

    parsed: dict[str, int] = {}
    for key, place in value.items():
        if not isinstance(key, str) or not key.strip():
            raise InvariantViolationError("Ключи 'placements' должны быть непустыми строками")
        if not isinstance(place, int) or place <= 0:
            raise InvariantViolationError(
                "Значения 'placements' должны быть целыми положительными числами"
            )
        parsed[key] = place
    return parsed

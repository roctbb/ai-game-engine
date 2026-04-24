from __future__ import annotations

from dataclasses import dataclass, field

from shared.kernel import new_id, utc_now


@dataclass(frozen=True, slots=True)
class SimilarityWarning:
    warning_id: str
    competition_id: str
    team_a_id: str
    team_b_id: str
    slot_key: str
    similarity: float
    algorithm: str
    run_a_id: str
    run_b_id: str
    created_at: object = field(default_factory=utc_now)

    @staticmethod
    def create(
        competition_id: str,
        team_a_id: str,
        team_b_id: str,
        slot_key: str,
        similarity: float,
        algorithm: str,
        run_a_id: str,
        run_b_id: str,
    ) -> "SimilarityWarning":
        return SimilarityWarning(
            warning_id=new_id("warn"),
            competition_id=competition_id,
            team_a_id=team_a_id,
            team_b_id=team_b_id,
            slot_key=slot_key,
            similarity=similarity,
            algorithm=algorithm,
            run_a_id=run_a_id,
            run_b_id=run_b_id,
        )

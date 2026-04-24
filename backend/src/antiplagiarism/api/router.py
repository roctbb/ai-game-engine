from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from antiplagiarism.api.schemas import SimilarityWarningResponse
from antiplagiarism.application.service import AnalyzeCompetitionInput
from app.auth import require_roles
from app.dependencies import ServiceContainer, get_container
from identity.domain.model import AppSession, UserRole

router = APIRouter(tags=["antiplagiarism"])


@router.get(
    "/competitions/{competition_id}/antiplagiarism/warnings",
    response_model=list[SimilarityWarningResponse],
)
def get_antiplagiarism_warnings(
    competition_id: str,
    similarity_threshold: float = Query(default=0.85, ge=0.0, le=1.0),
    min_token_count: int = Query(default=12, ge=1, le=1000),
    _session: AppSession = Depends(require_roles(UserRole.TEACHER, UserRole.ADMIN)),
    container: ServiceContainer = Depends(get_container),
) -> list[SimilarityWarningResponse]:
    warnings = container.antiplagiarism.analyze_competition(
        AnalyzeCompetitionInput(
            competition_id=competition_id,
            similarity_threshold=similarity_threshold,
            min_token_count=min_token_count,
        )
    )
    return [
        SimilarityWarningResponse(
            warning_id=item.warning_id,
            competition_id=item.competition_id,
            team_a_id=item.team_a_id,
            team_b_id=item.team_b_id,
            slot_key=item.slot_key,
            similarity=item.similarity,
            algorithm=item.algorithm,
            run_a_id=item.run_a_id,
            run_b_id=item.run_b_id,
            created_at=item.created_at,
        )
        for item in warnings
    ]

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class SimilarityWarningResponse(BaseModel):
    warning_id: str
    competition_id: str
    team_a_id: str
    team_b_id: str
    slot_key: str
    similarity: float
    algorithm: str
    run_a_id: str
    run_b_id: str
    created_at: datetime

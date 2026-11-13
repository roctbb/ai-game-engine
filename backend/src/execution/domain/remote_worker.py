from dataclasses import dataclass
from datetime import datetime


@dataclass
class RemoteWorkerCredential:
    worker_id: str
    enrollment_hash: str
    enrollment_expires_at: datetime
    token_hash: str | None = None
    connected_at: datetime | None = None
    revoked_at: datetime | None = None

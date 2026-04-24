from __future__ import annotations

import hashlib
import re

from fastapi import FastAPI, HTTPException
import httpx
from pydantic import BaseModel, HttpUrl

from builder_service.settings import settings

app = FastAPI(title=settings.app_name)

_BUILD_ID_RE = re.compile(r"^build_[0-9a-f]{32}$")
_DIGEST_RE = re.compile(r"^sha256:[0-9a-f]{64}$")


class BuildRequest(BaseModel):
    game_source_id: str
    repo_url: HttpUrl


@app.get("/health")
def healthcheck() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/internal/builds/start")
def start_build(request: BuildRequest) -> dict[str, object]:
    with httpx.Client(timeout=settings.request_timeout_seconds) as client:
        build_id: str | None = None
        try:
            start_response = client.post(
                f"{settings.backend_api_url}/internal/builds/start",
                json={
                    "game_source_id": request.game_source_id,
                    "repo_url": str(request.repo_url),
                },
                headers=_internal_headers(),
            )
            start_response.raise_for_status()
            build = start_response.json()

            build_id = _require_started_build_payload(build)
            image_digest = _build_image_digest(
                game_source_id=request.game_source_id,
                repo_url=str(request.repo_url),
            )

            finished_response = client.post(
                f"{settings.backend_api_url}/internal/builds/{build_id}/finished",
                json={"image_digest": image_digest},
                headers=_internal_headers(),
            )
            finished_response.raise_for_status()
            finished_payload = finished_response.json()
            _require_finished_build_payload(finished_payload, build_id=build_id, image_digest=image_digest)
            return finished_payload
        except (httpx.HTTPError, ValueError, TypeError, KeyError) as exc:
            _best_effort_fail(client=client, build_id=build_id, message=str(exc))
            raise HTTPException(status_code=502, detail="Builder service failed to sync build status") from exc


def _build_image_digest(game_source_id: str, repo_url: str) -> str:
    hasher = hashlib.sha256()
    hasher.update(game_source_id.encode("utf-8"))
    hasher.update(b"|")
    hasher.update(repo_url.encode("utf-8"))
    return f"sha256:{hasher.hexdigest()}"


def _require_started_build_payload(payload: dict[str, object]) -> str:
    build_id_raw = payload.get("build_id")
    build_id = str(build_id_raw).strip() if build_id_raw is not None else ""
    if not _BUILD_ID_RE.fullmatch(build_id):
        raise ValueError("Backend returned invalid build_id")

    status = str(payload.get("status", "")).strip().lower()
    if status != "started":
        raise ValueError(f"Backend returned unexpected start status '{status}'")
    return build_id


def _require_finished_build_payload(payload: dict[str, object], *, build_id: str, image_digest: str) -> None:
    status = str(payload.get("status", "")).strip().lower()
    if status != "finished":
        raise ValueError(f"Backend returned unexpected finish status '{status}'")

    payload_build_id = str(payload.get("build_id", "")).strip()
    if payload_build_id != build_id:
        raise ValueError("Backend returned mismatched build_id in finished response")

    payload_digest = str(payload.get("image_digest", "")).strip()
    if not _DIGEST_RE.fullmatch(payload_digest):
        raise ValueError("Backend returned invalid image_digest in finished response")
    if payload_digest != image_digest:
        raise ValueError("Backend returned unexpected image_digest in finished response")


def _best_effort_fail(client: httpx.Client, build_id: str | None, message: str) -> None:
    if not build_id:
        return
    try:
        response = client.post(
            f"{settings.backend_api_url}/internal/builds/{build_id}/failed",
            json={"error_message": message[:3000]},
            headers=_internal_headers(),
        )
        response.raise_for_status()
    except httpx.HTTPError:
        return


def _internal_headers() -> dict[str, str]:
    return {"X-Internal-Token": settings.internal_api_token}

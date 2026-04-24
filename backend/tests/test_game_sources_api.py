from administration.application.builder_gateway import BuildSyncResult
from administration.domain.model import SyncStatus
from shared.kernel import ExternalServiceError


def _admin_headers(client) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/dev-login",
        json={
            "nickname": "admin-gs",
            "role": "admin",
        },
    )
    assert login.status_code == 200
    session_id = login.json()["session_id"]
    return {"X-Session-Id": session_id}


def test_create_and_list_game_sources(client) -> None:
    headers = _admin_headers(client)
    created = client.post(
        "/api/v1/game-sources",
        json={
            "repo_url": "https://github.com/example/public-game-repo",
            "default_branch": "main",
            "created_by": "teacher-1",
        },
        headers=headers,
    )
    assert created.status_code == 200
    created_payload = created.json()
    assert created_payload["source_type"] == "git"
    assert created_payload["last_sync_status"] == "never"

    listed = client.get("/api/v1/game-sources", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["source_id"] == created_payload["source_id"]


def test_game_source_sync_success_and_history(client) -> None:
    headers = _admin_headers(client)
    source = client.post(
        "/api/v1/game-sources",
        json={
            "repo_url": "https://github.com/example/source-sync-success",
            "default_branch": "main",
            "created_by": "teacher-2",
        },
        headers=headers,
    ).json()

    synced = client.post(
        f"/api/v1/game-sources/{source['source_id']}/sync",
        json={"requested_by": "teacher-2"},
        headers=headers,
    )
    assert synced.status_code == 200
    sync_payload = synced.json()
    assert sync_payload["source"]["last_sync_status"] == "finished"
    assert sync_payload["source"]["last_synced_commit_sha"] is not None
    assert sync_payload["sync"]["status"] == "finished"
    assert sync_payload["sync"]["build_id"].startswith("build_")
    assert sync_payload["sync"]["image_digest"].startswith("sha256:")

    history = client.get(f"/api/v1/game-sources/{source['source_id']}/sync-history", headers=headers)
    assert history.status_code == 200
    items = history.json()
    assert len(items) == 1
    assert items[0]["status"] == "finished"


def test_game_source_sync_marks_failed_when_builder_unavailable(client, container) -> None:
    headers = _admin_headers(client)
    class _FailingBuilderGateway:
        def start_build(self, game_source_id: str, repo_url: str):  # noqa: ANN001
            _ = (game_source_id, repo_url)
            raise ExternalServiceError("builder unavailable")

    container.administration._builder_gateway = _FailingBuilderGateway()

    source = client.post(
        "/api/v1/game-sources",
        json={
            "repo_url": "https://github.com/example/source-sync-failure",
            "default_branch": "main",
            "created_by": "teacher-3",
        },
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/game-sources/{source['source_id']}/sync",
        json={"requested_by": "teacher-3"},
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "external_service_error"

    listed = client.get("/api/v1/game-sources", headers=headers).json()
    row = next(item for item in listed if item["source_id"] == source["source_id"])
    assert row["last_sync_status"] == "failed"

    history = client.get(f"/api/v1/game-sources/{source['source_id']}/sync-history", headers=headers)
    assert history.status_code == 200
    assert history.json()[0]["status"] == "failed"


def test_game_source_can_be_disabled_and_sync_blocked_then_reenabled(client) -> None:
    headers = _admin_headers(client)
    source = client.post(
        "/api/v1/game-sources",
        json={
            "repo_url": "https://github.com/example/source-status-toggle",
            "default_branch": "main",
            "created_by": "teacher-4",
        },
        headers=headers,
    ).json()

    disabled = client.patch(
        f"/api/v1/game-sources/{source['source_id']}/status",
        json={"status": "disabled"},
        headers=headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    blocked_sync = client.post(
        f"/api/v1/game-sources/{source['source_id']}/sync",
        json={"requested_by": "teacher-4"},
        headers=headers,
    )
    assert blocked_sync.status_code == 409
    assert blocked_sync.json()["error"]["code"] == "conflict"

    enabled = client.patch(
        f"/api/v1/game-sources/{source['source_id']}/status",
        json={"status": "active"},
        headers=headers,
    )
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "active"

    synced = client.post(
        f"/api/v1/game-sources/{source['source_id']}/sync",
        json={"requested_by": "teacher-4"},
        headers=headers,
    )
    assert synced.status_code == 200
    assert synced.json()["sync"]["status"] == "finished"


def test_create_game_source_rejects_repo_url_with_credentials(client) -> None:
    headers = _admin_headers(client)
    response = client.post(
        "/api/v1/game-sources",
        json={
            "repo_url": "https://user:pass@github.com/example/private-like-repo",
            "default_branch": "main",
            "created_by": "teacher-sec-1",
        },
        headers=headers,
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invariant_violation"


def test_create_game_source_rejects_repo_url_with_query_or_fragment(client) -> None:
    headers = _admin_headers(client)
    with_query = client.post(
        "/api/v1/game-sources",
        json={
            "repo_url": "https://github.com/example/repo.git?token=abc",
            "default_branch": "main",
            "created_by": "teacher-sec-2",
        },
        headers=headers,
    )
    assert with_query.status_code == 422
    assert with_query.json()["error"]["code"] == "invariant_violation"

    with_fragment = client.post(
        "/api/v1/game-sources",
        json={
            "repo_url": "https://github.com/example/repo.git#branch",
            "default_branch": "main",
            "created_by": "teacher-sec-2",
        },
        headers=headers,
    )
    assert with_fragment.status_code == 422
    assert with_fragment.json()["error"]["code"] == "invariant_violation"


def test_game_source_sync_marks_failed_when_builder_returns_invalid_digest(client, container) -> None:
    headers = _admin_headers(client)

    class _InvalidDigestBuilderGateway:
        def start_build(self, game_source_id: str, repo_url: str):  # noqa: ANN001
            _ = (game_source_id, repo_url)
            return BuildSyncResult(
                build_id="build_0123456789abcdef0123456789abcdef",
                status=SyncStatus.FINISHED,
                image_digest="sha256:xyz",
                error_message=None,
            )

    container.administration._builder_gateway = _InvalidDigestBuilderGateway()

    source = client.post(
        "/api/v1/game-sources",
        json={
            "repo_url": "https://github.com/example/source-invalid-digest",
            "default_branch": "main",
            "created_by": "teacher-5",
        },
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/game-sources/{source['source_id']}/sync",
        json={"requested_by": "teacher-5"},
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "external_service_error"

    listed = client.get("/api/v1/game-sources", headers=headers).json()
    row = next(item for item in listed if item["source_id"] == source["source_id"])
    assert row["last_sync_status"] == "failed"

    history = client.get(f"/api/v1/game-sources/{source['source_id']}/sync-history", headers=headers).json()
    assert history[0]["status"] == "failed"
    assert history[0]["error_message"] == "Builder вернул некорректный image_digest"


def test_game_source_sync_marks_failed_when_builder_returns_invalid_build_id(client, container) -> None:
    headers = _admin_headers(client)

    class _InvalidBuildIdBuilderGateway:
        def start_build(self, game_source_id: str, repo_url: str):  # noqa: ANN001
            _ = (game_source_id, repo_url)
            return BuildSyncResult(
                build_id="bad-build-id",
                status=SyncStatus.FINISHED,
                image_digest="sha256:" + ("a" * 64),
                error_message=None,
            )

    container.administration._builder_gateway = _InvalidBuildIdBuilderGateway()

    source = client.post(
        "/api/v1/game-sources",
        json={
            "repo_url": "https://github.com/example/source-invalid-build-id",
            "default_branch": "main",
            "created_by": "teacher-6",
        },
        headers=headers,
    ).json()

    response = client.post(
        f"/api/v1/game-sources/{source['source_id']}/sync",
        json={"requested_by": "teacher-6"},
        headers=headers,
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "external_service_error"

    history = client.get(f"/api/v1/game-sources/{source['source_id']}/sync-history", headers=headers).json()
    assert history[0]["status"] == "failed"
    assert history[0]["error_message"] == "Builder вернул некорректный build_id"


def test_game_sources_allowed_for_teacher_and_forbidden_for_student(client) -> None:
    teacher_login = client.post(
        "/api/v1/auth/dev-login",
        json={
            "nickname": "teacher-gs",
            "role": "teacher",
        },
    )
    assert teacher_login.status_code == 200
    teacher_headers = {"X-Session-Id": teacher_login.json()["session_id"]}
    teacher_response = client.get("/api/v1/game-sources", headers=teacher_headers)
    assert teacher_response.status_code == 200

    login = client.post(
        "/api/v1/auth/dev-login",
        json={
            "nickname": "student-gs",
            "role": "student",
        },
    )
    assert login.status_code == 200
    headers = {"X-Session-Id": login.json()["session_id"]}

    response = client.get("/api/v1/game-sources", headers=headers)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"

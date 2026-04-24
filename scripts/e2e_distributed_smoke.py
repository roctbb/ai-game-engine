from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from uuid import uuid4


def _request(
    method: str,
    url: str,
    payload: dict | None = None,
    request_headers: dict[str, str] | None = None,
) -> tuple[int, dict]:
    data = None
    headers: dict[str, str] = {}
    if request_headers:
        headers.update(request_headers)
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url=url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else {}
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        parsed = json.loads(body) if body else {"error": {"message": str(exc)}}
        return exc.code, parsed


def _healthcheck(base: str, path: str = "/health") -> None:
    code, body = _request("GET", f"{base}{path}")
    if code != 200:
        raise RuntimeError(f"Healthcheck failed for {base}: HTTP {code}, body={body}")


def _wait_for_run_terminal(backend_api: str, run_id: str, timeout_sec: int) -> dict:
    deadline = time.time() + timeout_sec
    last: dict = {}
    while time.time() < deadline:
        code, body = _request("GET", f"{backend_api}/runs/{run_id}")
        if code != 200:
            raise RuntimeError(f"Cannot load run {run_id}: HTTP {code}, body={body}")
        last = body
        status = body.get("status")
        if status in {"finished", "failed", "canceled", "timeout"}:
            return body
        time.sleep(0.35)
    raise RuntimeError(f"Run {run_id} did not finish in time, last={last}")


def _drain_worker_until_completed(worker_api: str, expected_count: int, timeout_sec: int) -> None:
    deadline = time.time() + timeout_sec
    completed = 0
    while completed < expected_count and time.time() < deadline:
        code, body = _request("POST", f"{worker_api}/internal/worker/pull-and-execute")
        if code != 200:
            raise RuntimeError(f"worker pull-and-execute failed: HTTP {code}, body={body}")
        status = body.get("status")
        if status == "completed":
            completed += 1
            continue
        if status == "idle":
            time.sleep(0.25)
            continue
        raise RuntimeError(f"Unexpected worker status while draining queue: {body}")

    if completed < expected_count:
        raise RuntimeError(
            f"Timed out while waiting worker completions: got={completed}, expected={expected_count}"
        )


def _get_games_by_slug(backend_api: str) -> dict[str, dict]:
    code, games = _request("GET", f"{backend_api}/games")
    if code != 200:
        raise RuntimeError(f"GET /games failed: HTTP {code}, body={games}")
    return {game["slug"]: game for game in games}


def _create_team(backend_api: str, game_id: str, name: str, captain: str) -> dict:
    code, team = _request(
        "POST",
        f"{backend_api}/teams",
        {
            "game_id": game_id,
            "name": name,
            "captain_user_id": captain,
        },
    )
    if code != 200:
        raise RuntimeError(f"POST /teams failed: HTTP {code}, body={team}")
    return team


def _put_slot_code(backend_api: str, team_id: str, slot_key: str, actor: str, code_text: str) -> None:
    code, payload = _request(
        "PUT",
        f"{backend_api}/teams/{team_id}/slots/{slot_key}",
        {
            "actor_user_id": actor,
            "code": code_text,
        },
    )
    if code != 200:
        raise RuntimeError(
            f"PUT /teams/{team_id}/slots/{slot_key} failed: HTTP {code}, body={payload}"
        )


def _create_and_queue_run(
    backend_api: str,
    *,
    team_id: str,
    game_id: str,
    requested_by: str,
    run_kind: str,
    lobby_id: str | None = None,
) -> str:
    create_payload: dict[str, object] = {
        "team_id": team_id,
        "game_id": game_id,
        "requested_by": requested_by,
        "run_kind": run_kind,
    }
    if lobby_id is not None:
        create_payload["lobby_id"] = lobby_id

    code, run = _request("POST", f"{backend_api}/runs", create_payload)
    if code != 200:
        raise RuntimeError(f"POST /runs failed: HTTP {code}, body={run}")

    run_id = run["run_id"]
    code, queued = _request("POST", f"{backend_api}/runs/{run_id}/queue")
    if code != 200:
        raise RuntimeError(f"POST /runs/{run_id}/queue failed: HTTP {code}, body={queued}")

    return run_id


def _assert_run_finished(backend_api: str, run_id: str, timeout_sec: int) -> dict:
    terminal = _wait_for_run_terminal(backend_api=backend_api, run_id=run_id, timeout_sec=timeout_sec)
    if terminal.get("status") != "finished":
        raise RuntimeError(f"Run {run_id} is not finished successfully: {terminal}")
    return terminal


def _assert_run_canceled(
    backend_api: str,
    run_id: str,
    timeout_sec: int,
    *,
    expected_reason: str | None = None,
) -> dict:
    terminal = _wait_for_run_terminal(backend_api=backend_api, run_id=run_id, timeout_sec=timeout_sec)
    if terminal.get("status") != "canceled":
        raise RuntimeError(f"Run {run_id} is not canceled as expected: {terminal}")
    if expected_reason is not None and terminal.get("error_message") != expected_reason:
        raise RuntimeError(
            f"Run {run_id} has unexpected cancel reason: got={terminal.get('error_message')}, expected={expected_reason}, payload={terminal}"
        )
    return terminal


def _create_admin_headers(backend_api: str, nickname: str = "smoke-admin") -> dict[str, str]:
    code, session = _request(
        "POST",
        f"{backend_api}/auth/dev-login",
        {
            "nickname": nickname,
            "role": "teacher",
        },
    )
    if code != 200:
        raise RuntimeError(f"POST /auth/dev-login failed: HTTP {code}, body={session}")
    session_id = session.get("session_id")
    if not session_id:
        raise RuntimeError(f"Dev login returned no session_id: {session}")
    return {"X-Session-Id": str(session_id)}


def _create_game_source(
    backend_api: str,
    repo_url: str,
    default_branch: str,
    created_by: str,
    *,
    admin_headers: dict[str, str],
) -> dict:
    code, source = _request(
        "POST",
        f"{backend_api}/game-sources",
        {
            "repo_url": repo_url,
            "default_branch": default_branch,
            "created_by": created_by,
        },
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(f"POST /game-sources failed: HTTP {code}, body={source}")
    return source


def _set_game_source_status(
    backend_api: str,
    source_id: str,
    status: str,
    *,
    admin_headers: dict[str, str],
) -> dict:
    code, source = _request(
        "PATCH",
        f"{backend_api}/game-sources/{source_id}/status",
        {"status": status},
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(
            f"PATCH /game-sources/{source_id}/status failed: HTTP {code}, body={source}"
        )
    return source


def _sync_game_source(
    backend_api: str,
    source_id: str,
    requested_by: str,
    *,
    admin_headers: dict[str, str],
) -> tuple[dict, list[dict]]:
    code, sync_result = _request(
        "POST",
        f"{backend_api}/game-sources/{source_id}/sync",
        {"requested_by": requested_by},
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(f"POST /game-sources/{source_id}/sync failed: HTTP {code}, body={sync_result}")

    code, history = _request(
        "GET",
        f"{backend_api}/game-sources/{source_id}/sync-history",
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(
            f"GET /game-sources/{source_id}/sync-history failed: HTTP {code}, body={history}"
        )
    if not history:
        raise RuntimeError("Game source sync history is empty after sync trigger")
    return sync_result, history


def _assert_sync_blocked_for_disabled_source(
    backend_api: str,
    source_id: str,
    requested_by: str,
    *,
    admin_headers: dict[str, str],
) -> None:
    code, payload = _request(
        "POST",
        f"{backend_api}/game-sources/{source_id}/sync",
        {"requested_by": requested_by},
        request_headers=admin_headers,
    )
    if code != 409:
        raise RuntimeError(
            f"Expected sync block for disabled source, got HTTP {code}, body={payload}"
        )


def _register_single_task_catalog_game(
    backend_api: str,
    *,
    slug: str,
    title: str,
    admin_headers: dict[str, str],
) -> dict:
    code, game = _request(
        "POST",
        f"{backend_api}/games",
        {
            "slug": slug,
            "title": title,
            "mode": "single_task",
            "semver": "1.0.0",
            "required_slots": [{"key": "agent", "title": "Agent", "required": True}],
        },
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(f"POST /games failed for catalog smoke: HTTP {code}, body={game}")
    return game


def _register_small_match_game(
    backend_api: str,
    *,
    slug: str,
    title: str,
    required_worker_labels: dict[str, str],
    admin_headers: dict[str, str],
) -> dict:
    code, game = _request(
        "POST",
        f"{backend_api}/games",
        {
            "slug": slug,
            "title": title,
            "mode": "small_match",
            "semver": "1.0.0",
            "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
            "required_worker_labels": required_worker_labels,
        },
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(f"POST /games failed for label-aware smoke: HTTP {code}, body={game}")
    return game


def _patch_catalog_metadata(
    backend_api: str,
    *,
    game_id: str,
    admin_headers: dict[str, str],
    description: str | None,
    difficulty: str | None,
    topics: list[str],
    status: str,
) -> dict:
    code, game = _request(
        "PATCH",
        f"{backend_api}/games/{game_id}/catalog-metadata",
        {
            "description": description,
            "difficulty": difficulty,
            "topics": topics,
            "catalog_metadata_status": status,
        },
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(
            f"PATCH /games/{game_id}/catalog-metadata failed: HTTP {code}, body={game}"
        )
    return game


def _list_public_single_task_catalog(backend_api: str) -> list[dict]:
    code, payload = _request("GET", f"{backend_api}/catalog/single-tasks")
    if code != 200:
        raise RuntimeError(f"GET /catalog/single-tasks failed: HTTP {code}, body={payload}")
    if not isinstance(payload, list):
        raise RuntimeError(f"Unexpected /catalog/single-tasks payload: {payload}")
    return payload


def _set_worker_status(
    backend_api: str,
    worker_id: str,
    status: str,
    *,
    admin_headers: dict[str, str],
) -> dict:
    code, payload = _request(
        "PATCH",
        f"{backend_api}/workers/{worker_id}/status",
        {"status": status},
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(
            f"PATCH /internal/workers/{worker_id}/status failed: HTTP {code}, body={payload}"
        )
    return payload


def _scheduler_pull_next(
    scheduler_api: str,
    *,
    worker_id: str,
    worker_labels: dict[str, str],
) -> dict:
    code, payload = _request(
        "POST",
        f"{scheduler_api}/internal/workers/pull-next",
        {"worker_id": worker_id, "worker_labels": worker_labels},
    )
    if code != 200:
        raise RuntimeError(f"POST /internal/workers/pull-next failed: HTTP {code}, body={payload}")
    return payload


def _resolve_worker_id(backend_api: str, *, admin_headers: dict[str, str]) -> str:
    worker = _resolve_worker_node(backend_api=backend_api, admin_headers=admin_headers)
    worker_id = str(worker.get("worker_id", "")).strip()
    if not worker_id:
        raise RuntimeError(f"Worker payload does not contain worker_id: {worker}")
    return worker_id


def _resolve_worker_node(backend_api: str, *, admin_headers: dict[str, str]) -> dict:
    code, payload = _request("GET", f"{backend_api}/workers", request_headers=admin_headers)
    if code != 200:
        raise RuntimeError(f"GET /workers failed: HTTP {code}, body={payload}")
    if not isinstance(payload, list) or not payload:
        raise RuntimeError(f"No workers registered in backend: {payload}")

    preferred = sorted(
        payload,
        key=lambda item: (
            0 if str(item.get("status")) == "online" else 1,
            str(item.get("worker_id", "")),
        ),
    )[0]
    if not isinstance(preferred, dict):
        raise RuntimeError(f"Unexpected worker payload row: {preferred}")
    return preferred


def _assert_replay_available(backend_api: str, run_id: str) -> dict:
    code, replay = _request("GET", f"{backend_api}/replays/runs/{run_id}")
    if code != 200:
        raise RuntimeError(f"Replay for run {run_id} is unavailable: HTTP {code}, body={replay}")
    return replay


def _assert_run_stream_available(backend_api: str, run_id: str) -> str:
    req = urllib.request.Request(
        url=f"{backend_api}/runs/{run_id}/stream?poll_interval_ms=10&max_events=1",
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(
            f"Run stream for {run_id} is unavailable: HTTP {exc.code}, body={body}"
        ) from exc
    if "event: agp.update" not in body:
        raise RuntimeError(f"Run stream body has no agp.update event for {run_id}: {body}")
    if '"channel": "run"' not in body:
        raise RuntimeError(f"Run stream body has unexpected channel for {run_id}: {body}")
    return body


def _assert_run_stream_terminal_event(
    backend_api: str,
    run_id: str,
    *,
    expected_status: str,
) -> str:
    req = urllib.request.Request(
        url=f"{backend_api}/runs/{run_id}/stream?poll_interval_ms=10",
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(
            f"Run stream terminal probe for {run_id} failed: HTTP {exc.code}, body={body}"
        ) from exc
    if "event: agp.terminal" not in body:
        raise RuntimeError(f"Run stream body has no agp.terminal event for {run_id}: {body}")
    if '"channel": "run"' not in body:
        raise RuntimeError(f"Run stream terminal body has unexpected channel for {run_id}: {body}")
    expected_marker = f'"status": "{expected_status}"'
    if expected_marker not in body:
        raise RuntimeError(
            f"Run stream terminal body has no expected status marker {expected_marker} for {run_id}: {body}"
        )
    return body


def _assert_lobby_stream_available(backend_api: str, lobby_id: str) -> str:
    req = urllib.request.Request(
        url=f"{backend_api}/lobbies/{lobby_id}/stream?poll_interval_ms=10&max_events=1",
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(
            f"Lobby stream for {lobby_id} is unavailable: HTTP {exc.code}, body={body}"
        ) from exc
    if "event: agp.update" not in body:
        raise RuntimeError(f"Lobby stream body has no agp.update event for {lobby_id}: {body}")
    if '"channel": "lobby"' not in body:
        raise RuntimeError(f"Lobby stream body has unexpected channel for {lobby_id}: {body}")
    return body


def _assert_competition_stream_available(backend_api: str, competition_id: str) -> str:
    req = urllib.request.Request(
        url=f"{backend_api}/competitions/{competition_id}/stream?poll_interval_ms=10&max_events=1",
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        raise RuntimeError(
            f"Competition stream for {competition_id} is unavailable: HTTP {exc.code}, body={body}"
        ) from exc
    if "event: agp.update" not in body:
        raise RuntimeError(
            f"Competition stream body has no agp.update event for {competition_id}: {body}"
        )
    if '"channel": "competition"' not in body:
        raise RuntimeError(
            f"Competition stream body has unexpected channel for {competition_id}: {body}"
        )
    return body


def _single_task_smoke(
    backend_api: str,
    worker_api: str,
    *,
    game: dict,
    slot_code: str,
    timeout_sec: int,
) -> dict:
    user = f"smoke-st-{uuid4().hex[:6]}"
    slot_key = game["versions"][0]["required_slot_keys"][0]
    team = _create_team(
        backend_api=backend_api,
        game_id=game["game_id"],
        name=f"ST Team {user}",
        captain=user,
    )
    _put_slot_code(
        backend_api=backend_api,
        team_id=team["team_id"],
        slot_key=slot_key,
        actor=user,
        code_text=slot_code,
    )

    run_id = _create_and_queue_run(
        backend_api=backend_api,
        team_id=team["team_id"],
        game_id=game["game_id"],
        requested_by=user,
        run_kind="single_task",
    )
    _drain_worker_until_completed(worker_api=worker_api, expected_count=1, timeout_sec=timeout_sec)
    return _assert_run_finished(backend_api=backend_api, run_id=run_id, timeout_sec=timeout_sec)


def _create_training_lobby(
    backend_api: str,
    game_id: str,
    title: str,
    *,
    admin_headers: dict[str, str],
) -> dict:
    code, lobby = _request(
        "POST",
        f"{backend_api}/lobbies",
        {
            "game_id": game_id,
            "title": title,
            "kind": "training",
            "access": "public",
            "max_teams": 32,
        },
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(f"POST /lobbies failed: HTTP {code}, body={lobby}")
    return lobby


def _join_and_ready_team(
    backend_api: str,
    lobby_id: str,
    team_id: str,
    *,
    session_headers: dict[str, str],
) -> None:
    code, body = _request(
        "POST",
        f"{backend_api}/lobbies/{lobby_id}/teams/{team_id}/join",
        {},
        request_headers=session_headers,
    )
    if code != 200:
        raise RuntimeError(f"join team failed: HTTP {code}, body={body}")
    code, body = _request(
        "POST",
        f"{backend_api}/lobbies/{lobby_id}/teams/{team_id}/ready",
        {"ready": True},
        request_headers=session_headers,
    )
    if code != 200:
        raise RuntimeError(f"set ready failed: HTTP {code}, body={body}")


def _run_training_lobby_matchmaking(
    backend_api: str,
    worker_api: str,
    *,
    game: dict,
    teams: list[dict],
    requested_by: str,
    expected_runs: int,
    timeout_sec: int,
    admin_headers: dict[str, str],
) -> list[dict]:
    lobby = _create_training_lobby(
        backend_api=backend_api,
        game_id=game["game_id"],
        title=f"Smoke Lobby {game['slug']}",
        admin_headers=admin_headers,
    )
    for team in teams:
        _join_and_ready_team(
            backend_api=backend_api,
            lobby_id=lobby["lobby_id"],
            team_id=team["team_id"],
            session_headers=admin_headers,
        )

    code, tick = _request(
        "POST",
        f"{backend_api}/lobbies/{lobby['lobby_id']}/matchmaking/tick",
        {"requested_by": requested_by},
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(f"matchmaking tick failed: HTTP {code}, body={tick}")

    run_ids = tick.get("last_scheduled_run_ids") or []
    if len(run_ids) != expected_runs:
        raise RuntimeError(
            f"Unexpected scheduled runs count for {game['slug']}: got={len(run_ids)}, expected={expected_runs}, tick={tick}"
        )

    _drain_worker_until_completed(worker_api=worker_api, expected_count=expected_runs, timeout_sec=timeout_sec)
    return [
        _assert_run_finished(backend_api=backend_api, run_id=run_id, timeout_sec=timeout_sec)
        for run_id in run_ids
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="Distributed smoke flow for full MVP catalog")
    parser.add_argument("--backend", default="http://localhost:8000/api/v1")
    parser.add_argument("--scheduler", default="http://localhost:8010")
    parser.add_argument("--worker", default="http://localhost:8020")
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    print("[1/21] healthchecks...")
    backend_root = args.backend[:-7] if args.backend.endswith("/api/v1") else args.backend.rstrip("/")
    backend_health_path = "/api/v1/health" if args.backend.endswith("/api/v1") else "/health"
    _healthcheck(backend_root, backend_health_path)
    _healthcheck(args.scheduler)
    _healthcheck(args.worker)

    print("[2/21] load catalog...")
    games_by_slug = _get_games_by_slug(args.backend)
    required_slugs = {
        "maze_escape_v1",
        "coins_right_down_v1",
        "tower_defense_v1",
        "template_v1",
        "ttt_connect5_v1",
        "tanks_ctf_v1",
    }
    missing = sorted(slug for slug in required_slugs if slug not in games_by_slug)
    if missing:
        raise RuntimeError(f"Required catalog games missing: {missing}")

    admin_headers = _create_admin_headers(
        backend_api=args.backend,
        nickname=f"smoke-admin-{uuid4().hex[:6]}",
    )

    summary: dict[str, object] = {}

    print("[3/21] catalog publication workflow smoke")
    catalog_slug = f"smoke_catalog_{uuid4().hex[:8]}"
    draft_game = _register_single_task_catalog_game(
        backend_api=args.backend,
        slug=catalog_slug,
        title="Smoke Catalog Single Task",
        admin_headers=admin_headers,
    )
    if draft_game.get("catalog_metadata_status") != "draft":
        raise RuntimeError(f"Expected draft catalog status, got: {draft_game}")
    catalog_before = _list_public_single_task_catalog(backend_api=args.backend)
    if any(item.get("slug") == catalog_slug for item in catalog_before):
        raise RuntimeError("Draft single_task appeared in public catalog unexpectedly")

    ready_game = _patch_catalog_metadata(
        backend_api=args.backend,
        game_id=draft_game["game_id"],
        admin_headers=admin_headers,
        description="Smoke description",
        difficulty="easy",
        topics=["smoke", "catalog"],
        status="ready",
    )
    if ready_game.get("catalog_metadata_status") != "ready":
        raise RuntimeError(f"Expected ready catalog status after patch, got: {ready_game}")
    catalog_after_ready = _list_public_single_task_catalog(backend_api=args.backend)
    if not any(item.get("slug") == catalog_slug for item in catalog_after_ready):
        raise RuntimeError("Ready single_task did not appear in public catalog")

    archived_game = _patch_catalog_metadata(
        backend_api=args.backend,
        game_id=draft_game["game_id"],
        admin_headers=admin_headers,
        description=ready_game.get("description"),
        difficulty=ready_game.get("difficulty"),
        topics=list(ready_game.get("topics") or []),
        status="archived",
    )
    if archived_game.get("catalog_metadata_status") != "archived":
        raise RuntimeError(f"Expected archived catalog status after patch, got: {archived_game}")
    catalog_after_archived = _list_public_single_task_catalog(backend_api=args.backend)
    if any(item.get("slug") == catalog_slug for item in catalog_after_archived):
        raise RuntimeError("Archived single_task remained in public catalog")

    summary["catalog_publication"] = {
        "game_id": draft_game["game_id"],
        "slug": catalog_slug,
        "initial_status": draft_game.get("catalog_metadata_status"),
        "ready_status": ready_game.get("catalog_metadata_status"),
        "archived_status": archived_game.get("catalog_metadata_status"),
        "visible_when_draft": False,
        "visible_when_ready": True,
        "visible_when_archived": False,
    }

    print("[4/21] single_task smoke: maze_escape_v1")
    summary["maze_escape_v1"] = _single_task_smoke(
        backend_api=args.backend,
        worker_api=args.worker,
        game=games_by_slug["maze_escape_v1"],
        slot_code=(
            "def make_move(state):\n"
            "    x = state['position']['x']\n"
            "    y = state['position']['y']\n"
            "    if y < 6 and x in {0, 6}:\n"
            "        return 'down'\n"
            "    if x < 6:\n"
            "        return 'right'\n"
            "    return 'down'\n"
        ),
        timeout_sec=args.timeout,
    )

    print("[5/21] single_task smoke: coins_right_down_v1")
    summary["coins_right_down_v1"] = _single_task_smoke(
        backend_api=args.backend,
        worker_api=args.worker,
        game=games_by_slug["coins_right_down_v1"],
        slot_code=(
            "def make_move(state):\n"
            "    x = state['position']['x']\n"
            "    goal_x = state['goal']['x']\n"
            "    if x < goal_x:\n"
            "        return 'right'\n"
            "    return 'down'\n"
        ),
        timeout_sec=args.timeout,
    )

    print("[6/21] single_task smoke: tower_defense_v1")
    summary["tower_defense_v1"] = _single_task_smoke(
        backend_api=args.backend,
        worker_api=args.worker,
        game=games_by_slug["tower_defense_v1"],
        slot_code=(
            "def place_tower(state):\n"
            "    lane = state['tick'] % state['lanes']\n"
            "    return lane\n"
        ),
        timeout_sec=args.timeout,
    )

    print("[7/21] prepare small_match teams: template_v1")
    template_game = games_by_slug["template_v1"]
    template_slot = template_game["versions"][0]["required_slot_keys"][0]
    template_teams = []
    for idx in range(2):
        user = f"smoke-tpl-{idx}-{uuid4().hex[:6]}"
        team = _create_team(
            backend_api=args.backend,
            game_id=template_game["game_id"],
            name=f"TPL Team {idx}",
            captain=user,
        )
        _put_slot_code(
            backend_api=args.backend,
            team_id=team["team_id"],
            slot_key=template_slot,
            actor=user,
            code_text=(
                "def make_choice(state):\n"
                "    turn = state.get('turn', 0)\n"
                "    if turn >= 8:\n"
                "        return 'stop'\n"
                "    return 'inc'\n"
            ),
        )
        template_teams.append(team)

    print("[8/21] training lobby matchmaking smoke: template_v1")
    summary["template_v1"] = _run_training_lobby_matchmaking(
        backend_api=args.backend,
        worker_api=args.worker,
        game=template_game,
        teams=template_teams,
        requested_by=f"teacher-tpl-{uuid4().hex[:6]}",
        expected_runs=2,
        timeout_sec=args.timeout,
        admin_headers=admin_headers,
    )

    print("[9/21] prepare small_match teams: ttt_connect5_v1")
    ttt_game = games_by_slug["ttt_connect5_v1"]
    ttt_slot = ttt_game["versions"][0]["required_slot_keys"][0]
    ttt_teams = []
    for idx in range(2):
        user = f"smoke-sm-{idx}-{uuid4().hex[:6]}"
        team = _create_team(
            backend_api=args.backend,
            game_id=ttt_game["game_id"],
            name=f"SM Team {idx}",
            captain=user,
        )
        _put_slot_code(
            backend_api=args.backend,
            team_id=team["team_id"],
            slot_key=ttt_slot,
            actor=user,
            code_text=(
                "def make_choice(field, role):\n"
                "    for x in range(5):\n"
                "        for y in range(5):\n"
                "            if field[x][y] == 0:\n"
                "                return x, y\n"
            ),
        )
        ttt_teams.append(team)

    print("[10/21] training lobby matchmaking smoke: ttt_connect5_v1")
    summary["ttt_connect5_v1"] = _run_training_lobby_matchmaking(
        backend_api=args.backend,
        worker_api=args.worker,
        game=ttt_game,
        teams=ttt_teams,
        requested_by=f"teacher-sm-{uuid4().hex[:6]}",
        expected_runs=2,
        timeout_sec=args.timeout,
        admin_headers=admin_headers,
    )

    print("[11/21] prepare massive_lobby teams")
    tanks_game = games_by_slug["tanks_ctf_v1"]
    tanks_slot = tanks_game["versions"][0]["required_slot_keys"][0]
    tanks_teams = []
    for idx in range(3):
        user = f"smoke-ml-{idx}-{uuid4().hex[:6]}"
        team = _create_team(
            backend_api=args.backend,
            game_id=tanks_game["game_id"],
            name=f"ML Team {idx}",
            captain=user,
        )
        _put_slot_code(
            backend_api=args.backend,
            team_id=team["team_id"],
            slot_key=tanks_slot,
            actor=user,
            code_text=(
                "def make_choice(x, y, state):\n"
                "    flag = state['flag']\n"
                "    if x < flag['x']:\n"
                "        return 'right'\n"
                "    if x > flag['x']:\n"
                "        return 'left'\n"
                "    if y < flag['y']:\n"
                "        return 'down'\n"
                "    if y > flag['y']:\n"
                "        return 'up'\n"
                "    return 'stay'\n"
            ),
        )
        tanks_teams.append(team)

    print("[12/21] training lobby matchmaking smoke: tanks_ctf_v1")
    summary["tanks_ctf_v1"] = _run_training_lobby_matchmaking(
        backend_api=args.backend,
        worker_api=args.worker,
        game=tanks_game,
        teams=tanks_teams,
        requested_by=f"teacher-ml-{uuid4().hex[:6]}",
        expected_runs=3,
        timeout_sec=args.timeout,
        admin_headers=admin_headers,
    )

    print("[13/21] game source sync smoke")
    game_source = _create_game_source(
        backend_api=args.backend,
        repo_url=f"https://github.com/example/agp-smoke-{uuid4().hex[:8]}",
        default_branch="main",
        created_by=f"teacher-gs-{uuid4().hex[:6]}",
        admin_headers=admin_headers,
    )

    disabled_source = _set_game_source_status(
        backend_api=args.backend,
        source_id=game_source["source_id"],
        status="disabled",
        admin_headers=admin_headers,
    )
    _assert_sync_blocked_for_disabled_source(
        backend_api=args.backend,
        source_id=disabled_source["source_id"],
        requested_by=f"teacher-gs-{uuid4().hex[:6]}",
        admin_headers=admin_headers,
    )
    _ = _set_game_source_status(
        backend_api=args.backend,
        source_id=game_source["source_id"],
        status="active",
        admin_headers=admin_headers,
    )

    sync_result, sync_history = _sync_game_source(
        backend_api=args.backend,
        source_id=game_source["source_id"],
        requested_by=f"teacher-gs-{uuid4().hex[:6]}",
        admin_headers=admin_headers,
    )
    if sync_result["sync"]["status"] != "finished":
        raise RuntimeError(f"Game source sync did not finish successfully: {sync_result}")
    summary["game_source_sync"] = {
        "source": sync_result["source"],
        "disabled_sync_blocked": True,
        "last_sync": sync_result["sync"],
        "history_count": len(sync_history),
    }

    print("[14/21] worker status gate smoke")
    worker_warmup_code, _worker_warmup_payload = _request(
        "POST",
        f"{args.worker}/internal/worker/pull-and-execute",
        {},
    )
    if worker_warmup_code != 200:
        raise RuntimeError(
            f"Worker warmup pull-and-execute failed: HTTP {worker_warmup_code}, body={_worker_warmup_payload}"
        )
    worker_id = _resolve_worker_id(backend_api=args.backend, admin_headers=admin_headers)

    _set_worker_status(
        backend_api=args.backend,
        worker_id=worker_id,
        status="disabled",
        admin_headers=admin_headers,
    )
    paused_code, paused_payload = _request(
        "POST",
        f"{args.worker}/internal/worker/pull-and-execute",
        {},
    )
    if paused_code != 200:
        raise RuntimeError(
            f"Worker pull-and-execute while disabled failed: HTTP {paused_code}, body={paused_payload}"
        )
    if paused_payload.get("status") != "paused" or paused_payload.get("worker_status") != "disabled":
        raise RuntimeError(f"Expected paused disabled worker response, got: {paused_payload}")

    _set_worker_status(
        backend_api=args.backend,
        worker_id=worker_id,
        status="online",
        admin_headers=admin_headers,
    )
    resumed_code, resumed_payload = _request(
        "POST",
        f"{args.worker}/internal/worker/pull-and-execute",
        {},
    )
    if resumed_code != 200:
        raise RuntimeError(
            f"Worker pull-and-execute after online failed: HTTP {resumed_code}, body={resumed_payload}"
        )
    if resumed_payload.get("status") not in {"idle", "completed"}:
        raise RuntimeError(f"Expected idle/completed after worker online, got: {resumed_payload}")
    summary["worker_status_gate"] = {
        "worker_id": worker_id,
        "paused_response": paused_payload,
        "resume_response": resumed_payload,
    }

    print("[15/21] label-aware scheduler smoke")
    resolved_worker = _resolve_worker_node(backend_api=args.backend, admin_headers=admin_headers)
    worker_labels = {
        str(key): str(value)
        for key, value in (resolved_worker.get("labels") or {}).items()
        if str(key).strip() and str(value).strip()
    }
    if not worker_labels:
        raise RuntimeError(
            f"Label-aware smoke requires non-empty worker labels, got: {resolved_worker}"
        )

    required_labels = {
        next(iter(worker_labels.keys())): next(iter(worker_labels.values()))
    }
    labeled_game = _register_small_match_game(
        backend_api=args.backend,
        slug=f"smoke_labels_{uuid4().hex[:8]}",
        title="Smoke Labels Match",
        required_worker_labels=required_labels,
        admin_headers=admin_headers,
    )
    labeled_slot = labeled_game["versions"][0]["required_slot_keys"][0]
    labeled_user = f"smoke-lbl-{uuid4().hex[:6]}"
    labeled_team = _create_team(
        backend_api=args.backend,
        game_id=labeled_game["game_id"],
        name="LBL Team",
        captain=labeled_user,
    )
    _put_slot_code(
        backend_api=args.backend,
        team_id=labeled_team["team_id"],
        slot_key=labeled_slot,
        actor=labeled_user,
        code_text=(
            "def make_choice(state):\n"
            "    return 'inc'\n"
        ),
    )
    labeled_run_id = _create_and_queue_run(
        backend_api=args.backend,
        team_id=labeled_team["team_id"],
        game_id=labeled_game["game_id"],
        requested_by=labeled_user,
        run_kind="training_match",
    )

    mismatch_pull = _scheduler_pull_next(
        scheduler_api=args.scheduler,
        worker_id=f"scheduler-probe-mismatch-{uuid4().hex[:6]}",
        worker_labels={"pool": "__mismatch__"},
    )
    if mismatch_pull.get("status") != "empty" or mismatch_pull.get("run_id") is not None:
        raise RuntimeError(f"Expected empty on label mismatch pull, got: {mismatch_pull}")

    probe_worker_id = f"scheduler-probe-match-{uuid4().hex[:6]}"
    code, worker_registered = _request(
        "POST",
        f"{args.backend}/internal/workers/register",
        {
            "worker_id": probe_worker_id,
            "hostname": probe_worker_id,
            "capacity_total": 1,
            "labels": required_labels,
        },
    )
    if code != 200:
        raise RuntimeError(
            f"POST /internal/workers/register failed for scheduler probe: HTTP {code}, body={worker_registered}"
        )

    match_pull = _scheduler_pull_next(
        scheduler_api=args.scheduler,
        worker_id=probe_worker_id,
        worker_labels=required_labels,
    )
    if match_pull.get("status") != "assigned" or match_pull.get("run_id") != labeled_run_id:
        raise RuntimeError(
            "Expected assigned run on label match pull, "
            f"got: {match_pull}, expected run_id={labeled_run_id}"
        )

    code, started = _request(
        "POST",
        f"{args.backend}/internal/runs/{labeled_run_id}/started",
        {"worker_id": probe_worker_id},
    )
    if code != 200:
        raise RuntimeError(f"POST /internal/runs/{labeled_run_id}/started failed: HTTP {code}, body={started}")

    code, finished = _request(
        "POST",
        f"{args.backend}/internal/runs/{labeled_run_id}/finished",
        {"payload": {"status": "finished", "scores": {labeled_team['team_id']: 1}}},
    )
    if code != 200:
        raise RuntimeError(f"POST /internal/runs/{labeled_run_id}/finished failed: HTTP {code}, body={finished}")

    code, ack = _request(
        "POST",
        f"{args.scheduler}/internal/runs/ack-finished",
        {"worker_id": probe_worker_id, "run_id": labeled_run_id},
    )
    if code != 200 or ack.get("status") != "acknowledged":
        raise RuntimeError(
            f"POST /internal/runs/ack-finished failed for scheduler probe: HTTP {code}, body={ack}"
        )

    labeled_run = _assert_run_finished(
        backend_api=args.backend,
        run_id=labeled_run_id,
        timeout_sec=args.timeout,
    )
    summary["label_aware_scheduler"] = {
        "game_id": labeled_game["game_id"],
        "required_worker_labels": required_labels,
        "mismatch_pull": mismatch_pull,
        "match_pull": match_pull,
        "terminal_status": labeled_run["status"],
    }

    print("[16/21] replay availability smoke")
    replay_run_ids = [
        summary["maze_escape_v1"]["run_id"],
        summary["coins_right_down_v1"]["run_id"],
        summary["tower_defense_v1"]["run_id"],
        summary["template_v1"][0]["run_id"],
        summary["ttt_connect5_v1"][0]["run_id"],
        summary["tanks_ctf_v1"][0]["run_id"],
    ]
    replay_checks = []
    for replay_run_id in replay_run_ids:
        replay = _assert_replay_available(backend_api=args.backend, run_id=replay_run_id)
        replay_checks.append(
            {
                "run_id": replay_run_id,
                "status": replay.get("status"),
                "frames": len(replay.get("frames") or []),
                "events": len(replay.get("events") or []),
            }
        )
    summary["replay_checks"] = replay_checks

    print("[17/21] run stream smoke")
    stream_probe_run_id = summary["maze_escape_v1"]["run_id"]
    stream_body = _assert_run_stream_available(
        backend_api=args.backend,
        run_id=stream_probe_run_id,
    )
    summary["run_stream_probe"] = {
        "run_id": stream_probe_run_id,
        "body_preview": stream_body[:200],
    }

    print("[18/21] canceled run smoke")
    cancel_game = games_by_slug["maze_escape_v1"]
    cancel_slot = cancel_game["versions"][0]["required_slot_keys"][0]
    cancel_user = f"smoke-cancel-{uuid4().hex[:6]}"
    cancel_team = _create_team(
        backend_api=args.backend,
        game_id=cancel_game["game_id"],
        name="Cancel Probe Team",
        captain=cancel_user,
    )
    _put_slot_code(
        backend_api=args.backend,
        team_id=cancel_team["team_id"],
        slot_key=cancel_slot,
        actor=cancel_user,
        code_text=(
            "def make_move(state):\n"
            "    return 'right'\n"
        ),
    )
    canceled_run_id = _create_and_queue_run(
        backend_api=args.backend,
        team_id=cancel_team["team_id"],
        game_id=cancel_game["game_id"],
        requested_by=cancel_user,
        run_kind="single_task",
    )
    cancel_code, cancel_payload = _request("POST", f"{args.backend}/runs/{canceled_run_id}/cancel")
    if cancel_code != 200:
        raise RuntimeError(
            f"POST /runs/{canceled_run_id}/cancel failed in smoke: HTTP {cancel_code}, body={cancel_payload}"
        )
    canceled_terminal = _assert_run_canceled(
        backend_api=args.backend,
        run_id=canceled_run_id,
        timeout_sec=args.timeout,
        expected_reason="manual_cancel",
    )
    canceled_stream_body = _assert_run_stream_terminal_event(
        backend_api=args.backend,
        run_id=canceled_run_id,
        expected_status="canceled",
    )
    summary["canceled_run_probe"] = {
        "run_id": canceled_run_id,
        "status": canceled_terminal.get("status"),
        "error_message": canceled_terminal.get("error_message"),
        "stream_preview": canceled_stream_body[:200],
    }

    print("[19/21] lobby stream smoke")
    probe_lobby = _create_training_lobby(
        backend_api=args.backend,
        game_id=template_game["game_id"],
        title=f"Stream Probe Lobby {uuid4().hex[:6]}",
        admin_headers=admin_headers,
    )
    lobby_stream_body = _assert_lobby_stream_available(
        backend_api=args.backend,
        lobby_id=probe_lobby["lobby_id"],
    )
    summary["lobby_stream_probe"] = {
        "lobby_id": probe_lobby["lobby_id"],
        "body_preview": lobby_stream_body[:200],
    }

    print("[20/21] competition stream smoke")
    code, probe_competition = _request(
        "POST",
        f"{args.backend}/competitions",
        {
            "game_id": template_game["game_id"],
            "title": f"Stream Probe Competition {uuid4().hex[:6]}",
            "format": "single_elimination",
            "tie_break_policy": "manual",
            "advancement_top_k": 1,
            "match_size": 2,
        },
        request_headers=admin_headers,
    )
    if code != 200:
        raise RuntimeError(f"POST /competitions failed in stream probe: HTTP {code}, body={probe_competition}")
    competition_stream_body = _assert_competition_stream_available(
        backend_api=args.backend,
        competition_id=probe_competition["competition_id"],
    )
    summary["competition_stream_probe"] = {
        "competition_id": probe_competition["competition_id"],
        "body_preview": competition_stream_body[:200],
    }

    print("[21/21] inspect scheduler queue stats")
    code, queue_stats = _request("GET", f"{args.scheduler}/internal/queue/stats")
    if code != 200:
        raise RuntimeError(f"Scheduler stats failed: HTTP {code}, body={queue_stats}")

    print("\nSMOKE SUMMARY")
    print(json.dumps({"summary": summary, "scheduler": queue_stats}, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

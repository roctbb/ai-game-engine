from datetime import UTC, datetime, timedelta

import pytest

from execution.application.scheduler_gateway import SchedulerGateway
from execution.domain.model import RunStatus
from shared.kernel import ExternalServiceError, InvariantViolationError
from training_lobby.application.service import _partition_match_groups
from training_lobby.domain.model import LobbyStatus


class _FailingSchedulerGateway(SchedulerGateway):
    def schedule_run(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> None:
        raise ExternalServiceError("scheduler unavailable")


def test_multiplayer_partition_starts_parallel_games_and_leaves_only_incomplete_tail() -> None:
    teams = [f"team-{index}" for index in range(10)]

    assert _partition_match_groups(ready_team_ids=teams, min_players=2, max_players=4) == [
        ["team-0", "team-1", "team-2", "team-3"],
        ["team-4", "team-5", "team-6", "team-7"],
        ["team-8", "team-9"],
    ]
    assert _partition_match_groups(ready_team_ids=teams[:6], min_players=3, max_players=4) == [
        ["team-0", "team-1", "team-2"],
        ["team-3", "team-4", "team-5"],
    ]
    assert _partition_match_groups(ready_team_ids=teams[:5], min_players=3, max_players=4) == [
        ["team-0", "team-1", "team-2", "team-3"],
    ]


def _create_game(
    client,
    slug: str,
    mode: str,
    headers: dict[str, str],
    *,
    min_players_per_match: int | None = None,
    max_players_per_match: int | None = None,
) -> dict:
    payload = {
        "slug": slug,
        "title": f"{mode} game",
        "mode": mode,
        "semver": "1.0.0",
        "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
    }
    if min_players_per_match is not None:
        payload["min_players_per_match"] = min_players_per_match
    if max_players_per_match is not None:
        payload["max_players_per_match"] = max_players_per_match
    return client.post(
        "/api/v1/games",
        json=payload,
        headers=headers,
    ).json()


def _create_ready_team(client, game_id: str, captain: str, name: str) -> dict:
    team = client.post(
        "/api/v1/teams",
        json={"game_id": game_id, "name": name, "captain_user_id": captain},
    ).json()
    client.put(
        f"/api/v1/teams/{team['team_id']}/slots/bot",
        json={"actor_user_id": captain, "code": "def make_choice(field, role):\n    return 0, 0\n"},
    )
    return team


def _create_training_lobby(client, game_id: str, title: str, headers: dict[str, str]) -> dict:
    return client.post(
        "/api/v1/lobbies",
        json={
            "game_id": game_id,
            "title": title,
            "kind": "training",
            "access": "public",
            "max_teams": 32,
        },
        headers=headers,
    ).json()


def test_multiplayer_matchmaking_schedules_only_full_pairs(client, teacher_headers) -> None:
    game = next(item for item in client.get("/api/v1/games").json() if item["slug"] == "ttt_connect5_v1")
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="cap-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="cap-b", name="Bravo")
    team_c = _create_ready_team(client, game_id=game["game_id"], captain="cap-c", name="Charlie")

    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Small", headers=teacher_headers)
    ready_responses = []
    for team in (team_a, team_b, team_c):
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        ready_responses.append(
            client.post(
                f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/ready",
                json={"ready": True},
                headers=teacher_headers,
            )
        )

    assert ready_responses[1].status_code == 200
    auto_tick = ready_responses[1].json()
    assert auto_tick["status"] == "running"
    assert len(auto_tick["last_scheduled_run_ids"]) == 2

    runs = client.get(f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match").json()
    assert len(runs) == 2
    assert {item["team_id"] for item in runs} == {team_a["team_id"], team_b["team_id"]}
    assert all(item["status"] == "queued" for item in runs)
    for run in runs:
        context = client.get(f"/api/v1/internal/runs/{run['run_id']}/execution-context")
        assert context.status_code == 200
        assert {item["team_id"] for item in context.json()["participants"]} == {
            team_a["team_id"],
            team_b["team_id"],
        }

    tick_again = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/matchmaking/tick",
        json={"requested_by": "teacher-mm"},
        headers=teacher_headers,
    ).json()
    assert set(tick_again["last_scheduled_run_ids"]) == set(auto_tick["last_scheduled_run_ids"])


def test_multiplayer_matchmaking_continues_after_finished_match(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="multiplayer_mm_continues",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="loop-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="loop-b", name="Bravo")

    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Loop", headers=teacher_headers)
    for team in (team_a, team_b):
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/ready",
            json={"ready": True},
            headers=teacher_headers,
        )

    first_runs = client.get(
        f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match",
        headers=teacher_headers,
    ).json()
    assert len(first_runs) == 2

    for index, run in enumerate(first_runs):
        finished = client.post(
            f"/api/v1/internal/runs/{run['run_id']}/finished",
            json={"payload": {"status": "ok", "scores": {run["team_id"]: 10 - index}}},
        )
        assert finished.status_code == 200

    all_runs = client.get(
        f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match",
        headers=teacher_headers,
    ).json()
    active_runs = [item for item in all_runs if item["status"] in {"created", "queued", "running"}]
    assert len(all_runs) == 2
    assert active_runs == []

    lobby_during_result = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers).json()
    assert lobby_during_result["cycle_phase"] in {"replay", "result"}
    assert set(lobby_during_result["current_run_ids"]) == {item["run_id"] for item in first_runs}

    old_finished_at = datetime.now(tz=UTC) - timedelta(seconds=30)
    for run in first_runs:
        model = container.execution._run_repository.get(run["run_id"])
        model.finished_at = old_finished_at
        container.execution._run_repository.save(model)

    listed_lobbies = client.get("/api/v1/lobbies", headers=teacher_headers)
    assert listed_lobbies.status_code == 200
    all_runs = client.get(
        f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match",
        headers=teacher_headers,
    ).json()
    assert len(all_runs) == 2

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200

    all_runs = client.get(
        f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match",
        headers=teacher_headers,
    ).json()
    active_runs = [item for item in all_runs if item["status"] in {"created", "queued", "running"}]
    assert len(all_runs) == 4
    assert len(active_runs) == 2
    assert {item["team_id"] for item in active_runs} == {team_a["team_id"], team_b["team_id"]}


def test_multiplayer_matchmaking_uses_match_bounds(client, teacher_headers) -> None:
    game = _create_game(
        client,
        slug="bounded_multiplayer_mm_game",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=4,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="mcap-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="mcap-b", name="Bravo")
    team_c = _create_ready_team(client, game_id=game["game_id"], captain="mcap-c", name="Charlie")

    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Massive", headers=teacher_headers)
    ready_responses = []
    for team in (team_a, team_b, team_c):
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        ready_responses.append(
            client.post(
                f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/ready",
                json={"ready": True},
                headers=teacher_headers,
            )
        )

    assert ready_responses[1].status_code == 200
    auto_tick = ready_responses[1].json()
    assert auto_tick["status"] == "running"
    assert len(auto_tick["last_scheduled_run_ids"]) == 2

    runs = client.get(f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match").json()
    assert len(runs) == 2
    assert {item["team_id"] for item in runs} == {
        team_a["team_id"],
        team_b["team_id"],
    }


def test_matchmaking_queue_failure_clears_batch_and_does_not_leave_created_runs(
    client,
    teacher_headers,
    container,
) -> None:
    game = _create_game(
        client,
        slug="multiplayer_mm_scheduler_failure",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="fail-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="fail-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Failure", headers=teacher_headers)
    container.execution._scheduler_gateway = _FailingSchedulerGateway()
    for team in (team_a, team_b):
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/ready",
            json={"ready": True},
            headers=teacher_headers,
        )

    with pytest.raises(InvariantViolationError):
        container.training_lobby.run_matchmaking_cycle(lobby_id=lobby["lobby_id"], requested_by="teacher-mm")

    recovered_lobby = container.training_lobby.get_lobby(lobby["lobby_id"])
    assert recovered_lobby.status is LobbyStatus.OPEN
    assert recovered_lobby.last_scheduled_run_ids == ()
    runs = container.execution.list_runs(lobby_id=lobby["lobby_id"], include_result_payload=False)
    assert runs
    assert all(item.status is not RunStatus.CREATED for item in runs)
    assert {item.status for item in runs} <= {RunStatus.FAILED, RunStatus.CANCELED}


def test_stopped_lobby_is_not_matchmade_by_due_tick(client, teacher_headers) -> None:
    game = _create_game(
        client,
        slug="multiplayer_mm_stopped_no_tick",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="stop-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="stop-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Stopped", headers=teacher_headers)
    for team in (team_a, team_b):
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/ready",
            json={"ready": True},
            headers=teacher_headers,
        )

    stopped = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/status",
        json={"status": "stopped"},
        headers=teacher_headers,
    )
    assert stopped.status_code == 200
    assert stopped.json()["status"] == "stopped"

    tick_all = client.post("/api/v1/lobbies/matchmaking/tick", headers=teacher_headers)
    assert tick_all.status_code == 200
    assert tick_all.json() == []

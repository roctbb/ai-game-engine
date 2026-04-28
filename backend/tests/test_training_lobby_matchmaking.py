from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from execution.application.scheduler_gateway import SchedulerGateway
from execution.domain.model import RunKind, RunStatus
from shared.kernel import ExternalServiceError, InvariantViolationError, NotFoundError
from training_lobby.application.service import _partition_match_groups
from training_lobby.domain.model import LobbyStatus


class _FailingSchedulerGateway(SchedulerGateway):
    def schedule_run(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> None:
        raise ExternalServiceError("scheduler unavailable")


class _RecordingSchedulerGateway(SchedulerGateway):
    def __init__(self) -> None:
        self.scheduled_run_ids: list[str] = []

    def schedule_run(self, run_id: str, required_worker_labels: dict[str, str] | None = None) -> None:
        self.scheduled_run_ids.append(run_id)


class _FakeDistributedLock:
    def __init__(self, *, acquired: bool = True) -> None:
        self.acquired = acquired
        self.acquire_calls = 0
        self.release_calls = 0

    def acquire(self, blocking: bool = True) -> bool:
        self.acquire_calls += 1
        return self.acquired

    def release(self) -> None:
        self.release_calls += 1


class _FakeDistributedLockClient:
    def __init__(self, lock: _FakeDistributedLock) -> None:
        self.lock_instance = lock
        self.lock_names: list[str] = []

    def lock(
        self,
        name: str,
        timeout: float | None = None,
        blocking_timeout: float | None = None,
    ) -> _FakeDistributedLock:
        self.lock_names.append(name)
        return self.lock_instance


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


def test_multiplayer_matchmaking_schedules_only_full_pairs(client, teacher_headers, container) -> None:
    scheduler = _RecordingSchedulerGateway()
    container.execution._scheduler_gateway = scheduler
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
    assert scheduler.scheduled_run_ids == [auto_tick["last_scheduled_run_ids"][0]]

    runs = client.get(f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match").json()
    assert len(runs) == 2
    assert {item["team_id"] for item in runs} == {team_a["team_id"], team_b["team_id"]}
    assert all(item["status"] == "queued" for item in runs)
    assert len({item["match_execution_id"] for item in runs}) == 1
    assert sum(1 for item in runs if item["run_id"] == item["match_primary_run_id"]) == 1
    assert all(item["worker_id"] is None for item in runs)
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

    primary_run = next(item for item in runs if item["run_id"] == item["match_primary_run_id"])
    shadow_run = next(item for item in runs if item["run_id"] != item["match_primary_run_id"])
    canceled = client.post(f"/api/v1/runs/{primary_run['run_id']}/cancel", headers=teacher_headers)
    assert canceled.status_code == 200
    shadow_after_cancel = client.get(f"/api/v1/runs/{shadow_run['run_id']}", headers=teacher_headers)
    assert shadow_after_cancel.status_code == 200
    assert shadow_after_cancel.json()["status"] == "canceled"


def test_matchmaking_cycle_uses_distributed_lock(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="multiplayer_mm_distributed_lock",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="lock-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="lock-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Lock", headers=teacher_headers)
    for team in (team_a, team_b):
        client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        container.training_lobby.set_ready(lobby_id=lobby["lobby_id"], team_id=team["team_id"], ready=True)

    lock = _FakeDistributedLock(acquired=True)
    container.training_lobby._matchmaking_lock_client = _FakeDistributedLockClient(lock)

    result = container.training_lobby.run_matchmaking_cycle(
        lobby_id=lobby["lobby_id"],
        requested_by="teacher-mm",
    )

    assert result.last_scheduled_run_ids
    assert lock.acquire_calls == 1
    assert lock.release_calls == 1
    assert container.training_lobby._matchmaking_lock_client.lock_names == [
        f"ai-game:training-lobby:{lobby['lobby_id']}:matchmaking"
    ]


def test_matchmaking_cycle_stops_when_distributed_lock_is_busy(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="multiplayer_mm_distributed_lock_busy",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Lock Busy", headers=teacher_headers)
    lock = _FakeDistributedLock(acquired=False)
    container.training_lobby._matchmaking_lock_client = _FakeDistributedLockClient(lock)

    with pytest.raises(InvariantViolationError):
        container.training_lobby.run_matchmaking_cycle(lobby_id=lobby["lobby_id"], requested_by="teacher-mm")

    assert lock.acquire_calls == 1
    assert lock.release_calls == 0


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

    primary_run = next(item for item in first_runs if item["run_id"] == item["match_primary_run_id"])
    shadow_run = next(item for item in first_runs if item["run_id"] != item["match_primary_run_id"])
    finished = client.post(
        f"/api/v1/internal/runs/{primary_run['run_id']}/finished",
        json={
            "payload": {
                "status": "ok",
                "frames": [{"tick": 0}, {"tick": 1}],
                "events": [{"type": "finished"}],
                "scores": {primary_run["team_id"]: 10, shadow_run["team_id"]: 9},
            }
        },
    )
    assert finished.status_code == 200
    stored_primary = client.get(f"/api/v1/runs/{primary_run['run_id']}", headers=teacher_headers).json()
    stored_shadow = client.get(f"/api/v1/runs/{shadow_run['run_id']}", headers=teacher_headers).json()
    assert stored_primary["result_payload"]["frames"]
    assert "frames" not in stored_shadow["result_payload"]
    assert "events" not in stored_shadow["result_payload"]
    assert stored_shadow["result_payload"]["shadow_result"] is True

    all_runs = client.get(
        f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match",
        headers=teacher_headers,
    ).json()
    active_runs = [item for item in all_runs if item["status"] in {"created", "queued", "running"}]
    assert len(all_runs) == 2
    assert active_runs == []
    assert all(item["status"] == "finished" for item in all_runs)
    replays = client.get(f"/api/v1/replays?game_id={game['game_id']}&run_kind=training_match", headers=teacher_headers)
    assert replays.status_code == 200
    assert [item["run_id"] for item in replays.json()] == [primary_run["run_id"]]
    shadow_replay = client.get(f"/api/v1/replays/runs/{shadow_run['run_id']}", headers=teacher_headers)
    assert shadow_replay.status_code == 200
    assert shadow_replay.json()["run_id"] == shadow_run["run_id"]

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


def test_archived_match_groups_use_payload_participants_for_parallel_batches(client, teacher_headers) -> None:
    game = _create_game(
        client,
        slug="bounded_multiplayer_archive_groups",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=4,
        headers=teacher_headers,
    )
    teams = [
        _create_ready_team(client, game_id=game["game_id"], captain=f"archive-group-{index}", name=f"Team {index}")
        for index in range(6)
    ]
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="MM Archive Groups", headers=teacher_headers)
    for team in teams:
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    expected_groups = [
        [team["team_id"] for team in teams[:3]],
        [team["team_id"] for team in teams[3:]],
    ]
    for group in expected_groups:
        for index, team_id in enumerate(group):
            run = client.post(
                "/api/v1/runs",
                json={
                    "team_id": team_id,
                    "game_id": game["game_id"],
                    "requested_by": "teacher-mm",
                    "run_kind": "training_match",
                    "lobby_id": lobby["lobby_id"],
                },
                headers=teacher_headers,
            )
            assert run.status_code == 200
            queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
            assert queued.status_code == 200
            finished = client.post(
                f"/api/v1/internal/runs/{run.json()['run_id']}/finished",
                json={
                    "payload": {
                        "status": "ok",
                        "scores": {group_team_id: 100 - score_index for score_index, group_team_id in enumerate(group)},
                        "placements": {group_team_id: score_index + 1 for score_index, group_team_id in enumerate(group)},
                    }
                },
            )
            assert finished.status_code == 200

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    archived_groups = lobby_view.json()["archived_match_groups"]
    assert len(archived_groups) == 2
    assert {frozenset(group["team_ids"]) for group in archived_groups} == {frozenset(group) for group in expected_groups}
    for group in archived_groups:
        assert set(group["scores_by_team"]) == set(group["team_ids"])


def test_finished_training_runs_store_match_participants_for_archive_grouping(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="finished_runs_store_match_participants",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=4,
        headers=teacher_headers,
    )
    teams = [
        _create_ready_team(client, game_id=game["game_id"], captain=f"stored-group-{index}", name=f"Team {index}")
        for index in range(6)
    ]
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Stored Archive Groups", headers=teacher_headers)
    for team in teams:
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    run_groups: list[list[str]] = []
    for group in (teams[:3], teams[3:]):
        run_group: list[str] = []
        for team in group:
            run = client.post(
                "/api/v1/runs",
                json={
                    "team_id": team["team_id"],
                    "game_id": game["game_id"],
                    "requested_by": "teacher-mm",
                    "run_kind": "training_match",
                    "lobby_id": lobby["lobby_id"],
                },
                headers=teacher_headers,
            )
            assert run.status_code == 200
            queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
            assert queued.status_code == 200
            run_group.append(run.json()["run_id"])
        run_groups.append(run_group)

    lobby_model = container.training_lobby.get_lobby(lobby["lobby_id"])
    lobby_model.set_last_scheduled_match_groups(run_groups)
    container.training_lobby._repository.save(lobby_model)

    expected_groups = [[team["team_id"] for team in teams[:3]], [team["team_id"] for team in teams[3:]]]
    for group_index, run_group in enumerate(run_groups):
        for index, run_id in enumerate(run_group):
            team_id = expected_groups[group_index][index]
            finished = client.post(
                f"/api/v1/internal/runs/{run_id}/finished",
                json={
                    "payload": {
                        "status": "ok",
                        "scores": {team_id: 100 - index},
                        "placements": {team_id: index + 1},
                    }
                },
            )
            assert finished.status_code == 200
            assert {item["team_id"] for item in finished.json()["result_payload"]["match_participants"]} == set(
                expected_groups[group_index]
            )

    lobby_model = container.training_lobby.get_lobby(lobby["lobby_id"])
    lobby_model.set_last_scheduled_match_groups([])
    container.training_lobby._repository.save(lobby_model)

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    archived_groups = lobby_view.json()["archived_match_groups"]
    assert len(archived_groups) == 2
    assert {frozenset(group["team_ids"]) for group in archived_groups} == {frozenset(group) for group in expected_groups}
    assert all(len(group["team_ids"]) == 3 for group in archived_groups)


def test_archived_training_watch_context_uses_stored_match_participants(client, teacher_headers, container) -> None:
    game = next(item for item in client.get("/api/v1/games").json() if item["slug"] == "ttt_connect5_v1")
    teams = [
        _create_ready_team(client, game_id=game["game_id"], captain=f"watch-group-{index}", name=f"Team {index}")
        for index in range(4)
    ]
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Stored Watch Context", headers=teacher_headers)
    for team in teams:
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    expected_groups = [[team["team_id"] for team in teams[:2]], [team["team_id"] for team in teams[2:]]]
    run_groups: list[list[str]] = []
    for group in expected_groups:
        group_run_ids: list[str] = []
        for team_id in group:
            run = client.post(
                "/api/v1/runs",
                json={
                    "team_id": team_id,
                    "game_id": game["game_id"],
                    "requested_by": "teacher-mm",
                    "run_kind": "training_match",
                    "lobby_id": lobby["lobby_id"],
                },
                headers=teacher_headers,
            )
            assert run.status_code == 200
            queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
            assert queued.status_code == 200
            group_run_ids.append(run.json()["run_id"])
        run_groups.append(group_run_ids)

    lobby_model = container.training_lobby.get_lobby(lobby["lobby_id"])
    lobby_model.set_last_scheduled_match_groups(run_groups)
    container.training_lobby._repository.save(lobby_model)

    for group, run_group in zip(expected_groups, run_groups, strict=True):
        for index, (team_id, run_id) in enumerate(zip(group, run_group, strict=True)):
            finished = client.post(
                f"/api/v1/internal/runs/{run_id}/finished",
                json={
                    "payload": {
                        "status": "ok",
                        "scores": {team_id: 100 - index},
                        "placements": {team_id: index + 1},
                    }
                },
            )
            assert finished.status_code == 200

    lobby_model = container.training_lobby.get_lobby(lobby["lobby_id"])
    lobby_model.set_last_scheduled_match_groups([])
    container.training_lobby._repository.save(lobby_model)

    watched = client.get(f"/api/v1/runs/{run_groups[0][0]}/watch-context", headers=teacher_headers)
    assert watched.status_code == 200
    assert {item["team_id"] for item in watched.json()["participants"]} == set(expected_groups[0])


def test_incomplete_signed_archive_group_does_not_count_as_solo_match(client, teacher_headers) -> None:
    game = _create_game(
        client,
        slug="incomplete_signed_archive_group",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="orphan-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="orphan-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Incomplete Signed Group", headers=teacher_headers)
    for team in (team_a, team_b):
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team_a["team_id"],
            "game_id": game["game_id"],
            "requested_by": "teacher-mm",
            "run_kind": "training_match",
            "lobby_id": lobby["lobby_id"],
        },
        headers=teacher_headers,
    )
    assert run.status_code == 200
    queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
    assert queued.status_code == 200
    finished = client.post(
        f"/api/v1/internal/runs/{run.json()['run_id']}/finished",
        json={
            "payload": {
                "status": "ok",
                "scores": {team_a["team_id"]: 100, team_b["team_id"]: 80},
                "placements": {team_a["team_id"]: 1, team_b["team_id"]: 2},
                "match_participants": [
                    {"run_id": run.json()["run_id"], "team_id": team_a["team_id"], "display_name": "Alpha"},
                    {"run_id": "missing-peer", "team_id": team_b["team_id"], "display_name": "Bravo"},
                ],
            }
        },
    )
    assert finished.status_code == 200

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    payload = lobby_view.json()
    assert payload["archived_match_groups"] == []
    stats_by_team = {item["team_id"]: item for item in payload["participant_stats"]}
    assert stats_by_team[team_a["team_id"]]["matches_total"] == 0
    assert stats_by_team[team_a["team_id"]]["wins"] == 0
    assert stats_by_team[team_b["team_id"]]["matches_total"] == 0
    assert stats_by_team[team_b["team_id"]]["wins"] == 0


def test_archived_match_groups_do_not_depend_on_run_order_for_same_players(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="interleaved_archive_groups",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="interleave-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="interleave-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Interleaved Archive", headers=teacher_headers)
    for team in (team_a, team_b):
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    created_runs: list[dict] = []
    for _match_index in range(2):
        for team in (team_a, team_b):
            run = client.post(
                "/api/v1/runs",
                json={
                    "team_id": team["team_id"],
                    "game_id": game["game_id"],
                    "requested_by": "teacher-mm",
                    "run_kind": "training_match",
                    "lobby_id": lobby["lobby_id"],
                },
                headers=teacher_headers,
            )
            assert run.status_code == 200
            queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
            assert queued.status_code == 200
            finished = client.post(
                f"/api/v1/internal/runs/{run.json()['run_id']}/finished",
                json={
                    "payload": {
                        "status": "ok",
                        "scores": {team_a["team_id"]: 100, team_b["team_id"]: 90},
                        "placements": {team_a["team_id"]: 1, team_b["team_id"]: 2},
                    }
                },
            )
            assert finished.status_code == 200
            created_runs.append(run.json())

    # Force the repository order to be A2, A1, B2, B1. Time-only grouping would
    # pair equal teams together, while payload-signature grouping restores matches.
    base_time = datetime.now(tz=UTC)
    ordered_run_ids = [
        created_runs[2]["run_id"],
        created_runs[0]["run_id"],
        created_runs[3]["run_id"],
        created_runs[1]["run_id"],
    ]
    for offset, run_id in enumerate(ordered_run_ids):
        model = container.execution._run_repository.get(run_id)
        model.created_at = base_time - timedelta(milliseconds=offset)
        container.execution._run_repository.save(model)

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    archived_groups = lobby_view.json()["archived_match_groups"]
    assert len(archived_groups) == 2
    assert [set(group["team_ids"]) for group in archived_groups] == [
        {team_a["team_id"], team_b["team_id"]},
        {team_a["team_id"], team_b["team_id"]},
    ]


def test_archived_match_groups_keep_same_players_separate_across_time_windows(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="same_players_archive_windows",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="window-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="window-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Archive Windows", headers=teacher_headers)
    for team in (team_a, team_b):
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    match_run_ids: list[list[str]] = []
    for match_index in range(2):
        group_ids: list[str] = []
        for team in (team_a, team_b):
            run = client.post(
                "/api/v1/runs",
                json={
                    "team_id": team["team_id"],
                    "game_id": game["game_id"],
                    "requested_by": "teacher-mm",
                    "run_kind": "training_match",
                    "lobby_id": lobby["lobby_id"],
                },
                headers=teacher_headers,
            )
            assert run.status_code == 200
            queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
            assert queued.status_code == 200
            finished = client.post(
                f"/api/v1/internal/runs/{run.json()['run_id']}/finished",
                json={
                    "payload": {
                        "status": "ok",
                        "scores": {team_a["team_id"]: 100 + match_index, team_b["team_id"]: 90 + match_index},
                        "placements": {team_a["team_id"]: 1, team_b["team_id"]: 2},
                    }
                },
            )
            assert finished.status_code == 200
            group_ids.append(run.json()["run_id"])
        match_run_ids.append(group_ids)

    first_window = datetime.now(tz=UTC) - timedelta(minutes=10)
    second_window = datetime.now(tz=UTC)
    for run_id in match_run_ids[0]:
        model = container.execution._run_repository.get(run_id)
        model.created_at = first_window
        container.execution._run_repository.save(model)
    for run_id in match_run_ids[1]:
        model = container.execution._run_repository.get(run_id)
        model.created_at = second_window
        container.execution._run_repository.save(model)

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    archived_groups = lobby_view.json()["archived_match_groups"]
    assert len(archived_groups) == 2
    assert [set(group["run_ids"]) for group in archived_groups] == [
        set(match_run_ids[1]),
        set(match_run_ids[0]),
    ]


def test_archived_match_groups_keep_legacy_unsigned_runs_in_time_order(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="mixed_archive_group_order",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    teams = [
        _create_ready_team(client, game_id=game["game_id"], captain=f"mixed-{index}", name=f"Team {index}")
        for index in range(4)
    ]
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Mixed Archive Order", headers=teacher_headers)
    for team in teams:
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    def create_finished_run(team: dict, payload: dict) -> str:
        run = client.post(
            "/api/v1/runs",
            json={
                "team_id": team["team_id"],
                "game_id": game["game_id"],
                "requested_by": "teacher-mm",
                "run_kind": "training_match",
                "lobby_id": lobby["lobby_id"],
            },
            headers=teacher_headers,
        )
        assert run.status_code == 200
        queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
        assert queued.status_code == 200
        finished = client.post(
            f"/api/v1/internal/runs/{run.json()['run_id']}/finished",
            json={"payload": payload},
        )
        assert finished.status_code == 200
        return run.json()["run_id"]

    signed_ids = [
        create_finished_run(
            team,
            {
                "status": "ok",
                "scores": {teams[0]["team_id"]: 10, teams[1]["team_id"]: 5},
                "placements": {teams[0]["team_id"]: 1, teams[1]["team_id"]: 2},
            },
        )
        for team in teams[:2]
    ]
    legacy_ids = [
        create_finished_run(
            team,
            {
                "status": "ok",
                "scores": {teams[2]["team_id"]: 8, teams[3]["team_id"]: 4},
                "placements": {teams[2]["team_id"]: 1, teams[3]["team_id"]: 2},
            },
        )
        for team in teams[2:]
    ]

    older_time = datetime.now(tz=UTC) - timedelta(minutes=5)
    newer_time = datetime.now(tz=UTC)
    for run_id in signed_ids:
        model = container.execution._run_repository.get(run_id)
        model.created_at = older_time
        container.execution._run_repository.save(model)
    for run_id in legacy_ids:
        model = container.execution._run_repository.get(run_id)
        model.created_at = newer_time
        model.result_payload = {"status": "ok", "metrics": {"score": 1}}
        container.execution._run_repository.save(model)

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    archived_groups = lobby_view.json()["archived_match_groups"]
    assert len(archived_groups) == 2
    assert set(archived_groups[0]["run_ids"]) == set(legacy_ids)
    assert set(archived_groups[1]["run_ids"]) == set(signed_ids)


def test_participant_stats_count_one_win_per_archived_match(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="participant_stats_repeated_pairs",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="stats-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="stats-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Stats Repeated Pairs", headers=teacher_headers)
    for team in (team_a, team_b):
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    match_count = 3
    match_run_ids: list[list[str]] = []
    for match_index in range(match_count):
        group_ids: list[str] = []
        scores = {team_a["team_id"]: 100 + match_index, team_b["team_id"]: 10 + match_index}
        placements = {team_a["team_id"]: 1, team_b["team_id"]: 2}
        for team in (team_a, team_b):
            run = client.post(
                "/api/v1/runs",
                json={
                    "team_id": team["team_id"],
                    "game_id": game["game_id"],
                    "requested_by": "teacher-mm",
                    "run_kind": "training_match",
                    "lobby_id": lobby["lobby_id"],
                },
                headers=teacher_headers,
            )
            assert run.status_code == 200
            queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
            assert queued.status_code == 200
            finished = client.post(
                f"/api/v1/internal/runs/{run.json()['run_id']}/finished",
                json={"payload": {"status": "ok", "scores": scores, "placements": placements}},
            )
            assert finished.status_code == 200
            group_ids.append(run.json()["run_id"])
        match_run_ids.append(group_ids)

    base_time = datetime.now(tz=UTC)
    for match_index, group in enumerate(match_run_ids):
        created_at = base_time + timedelta(seconds=match_index * 10)
        for run_id in group:
            model = container.execution._run_repository.get(run_id)
            model.created_at = created_at
            container.execution._run_repository.save(model)

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    stats_by_team = {item["team_id"]: item for item in lobby_view.json()["participant_stats"]}
    assert stats_by_team[team_a["team_id"]]["matches_total"] == match_count
    assert stats_by_team[team_b["team_id"]]["matches_total"] == match_count
    assert stats_by_team[team_a["team_id"]]["wins"] == match_count
    assert stats_by_team[team_b["team_id"]]["wins"] == 0
    assert sum(item["wins"] for item in stats_by_team.values()) == match_count


def test_training_lobby_keeps_last_30_matches_but_preserves_wins(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="training_archive_limit_preserves_wins",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="limit-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="limit-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Archive Limit", headers=teacher_headers)
    for team in (team_a, team_b):
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    match_run_ids: list[list[str]] = []
    match_count = 31
    base_time = datetime.now(tz=UTC) - timedelta(minutes=match_count)
    for match_index in range(match_count):
        group_ids: list[str] = []
        created_at = base_time + timedelta(seconds=match_index * 10)
        scores = {team_a["team_id"]: 100 + match_index, team_b["team_id"]: match_index}
        placements = {team_a["team_id"]: 1, team_b["team_id"]: 2}
        for team in (team_a, team_b):
            run = client.post(
                "/api/v1/runs",
                json={
                    "team_id": team["team_id"],
                    "game_id": game["game_id"],
                    "requested_by": "teacher-mm",
                    "run_kind": "training_match",
                    "lobby_id": lobby["lobby_id"],
                },
                headers=teacher_headers,
            )
            assert run.status_code == 200
            model = container.execution._run_repository.get(run.json()["run_id"])
            model.created_at = created_at
            container.execution._run_repository.save(model)
            queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
            assert queued.status_code == 200
            finished = client.post(
                f"/api/v1/internal/runs/{run.json()['run_id']}/finished",
                json={"payload": {"status": "ok", "scores": scores, "placements": placements}},
            )
            assert finished.status_code == 200
            group_ids.append(run.json()["run_id"])
        match_run_ids.append(group_ids)

    container.training_lobby.cleanup_training_match_archive(lobby_id=lobby["lobby_id"])

    assert client.get(f"/api/v1/runs/{match_run_ids[0][0]}", headers=teacher_headers).status_code == 404
    assert client.get(f"/api/v1/runs/{match_run_ids[0][1]}", headers=teacher_headers).status_code == 404
    remaining_runs = client.get(
        f"/api/v1/runs?lobby_id={lobby['lobby_id']}&run_kind=training_match",
        headers=teacher_headers,
    ).json()
    assert len(remaining_runs) == 60
    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    payload = lobby_view.json()
    assert len(payload["archived_match_groups"]) == 30
    stats_by_team = {item["team_id"]: item for item in payload["participant_stats"]}
    assert stats_by_team[team_a["team_id"]]["matches_total"] == match_count
    assert stats_by_team[team_a["team_id"]]["wins"] == match_count
    assert stats_by_team[team_b["team_id"]]["matches_total"] == match_count
    assert stats_by_team[team_b["team_id"]]["wins"] == 0


def test_lobby_live_view_skips_runs_deleted_during_archive_cleanup(client, teacher_headers, container, monkeypatch) -> None:
    game = _create_game(
        client,
        slug="training_archive_stale_run_race",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team = _create_ready_team(client, game_id=game["game_id"], captain="stale-race-a", name="Alpha")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Archive Race", headers=teacher_headers)
    joined = client.post(
        f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
        json={},
        headers=teacher_headers,
    )
    assert joined.status_code == 200
    run = client.post(
        "/api/v1/runs",
        json={
            "team_id": team["team_id"],
            "game_id": game["game_id"],
            "requested_by": "teacher-mm",
            "run_kind": "training_match",
            "lobby_id": lobby["lobby_id"],
        },
        headers=teacher_headers,
    )
    assert run.status_code == 200
    queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
    assert queued.status_code == 200
    finished = client.post(
        f"/api/v1/internal/runs/{run.json()['run_id']}/finished",
        json={"payload": {"status": "ok", "scores": {team["team_id"]: 10}}},
    )
    assert finished.status_code == 200

    lobby_model = container.training_lobby.get_lobby(lobby_id=lobby["lobby_id"])
    runs_without_payload = container.execution.list_runs(
        lobby_id=lobby["lobby_id"],
        run_kind=RunKind.TRAINING_MATCH,
        include_result_payload=False,
    )
    assert runs_without_payload
    assert runs_without_payload[0].result_payload is None

    runs_with_summary = container.training_lobby._finished_runs_with_payload_cached(
        lobby=lobby_model,
        runs=runs_without_payload,
    )
    assert runs_with_summary
    assert runs_with_summary[0].result_payload == runs_without_payload[0].result_summary

    def missing_run(_run_id: str):
        raise NotFoundError("Run was deleted by archive cleanup")

    monkeypatch.setattr(container.execution, "get_run", missing_run)

    legacy_runs_without_summary = [replace(runs_without_payload[0], result_summary=None)]
    container.training_lobby._clear_lobby_derived_caches(lobby["lobby_id"])

    assert container.training_lobby._finished_runs_with_payload_cached(
        lobby=lobby_model,
        runs=legacy_runs_without_summary,
    ) == []


def test_finishing_primary_match_uses_match_execution_to_finish_shadow_run(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="finish_shadow_from_match_execution",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="finish-shadow-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="finish-shadow-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Finish Shadow", headers=teacher_headers)
    for team in (team_a, team_b):
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200
        container.training_lobby.set_ready(lobby_id=lobby["lobby_id"], team_id=team["team_id"], ready=True)

    scheduled = container.training_lobby.run_matchmaking_cycle(lobby_id=lobby["lobby_id"], requested_by="teacher-mm")
    primary_run_id = scheduled.last_scheduled_run_ids[0]
    shadow_run_id = scheduled.last_scheduled_run_ids[1]

    lobby_model = container.training_lobby.get_lobby(lobby_id=lobby["lobby_id"])
    lobby_model.set_last_scheduled_match_groups([])
    container.training_lobby._repository.save(lobby_model)

    finished = client.post(
        f"/api/v1/internal/runs/{primary_run_id}/finished",
        json={
            "payload": {
                "status": "ok",
                "scores": {team_a["team_id"]: 20, team_b["team_id"]: 10},
                "placements": {team_a["team_id"]: 1, team_b["team_id"]: 2},
            }
        },
    )
    assert finished.status_code == 200
    shadow = client.get(f"/api/v1/runs/{shadow_run_id}", headers=teacher_headers)
    assert shadow.status_code == 200
    assert shadow.json()["status"] == "finished"


def test_reconcile_finishes_orphaned_shadow_run_when_primary_is_finished(client, teacher_headers, container) -> None:
    game = _create_game(
        client,
        slug="reconcile_orphaned_shadow",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="orphan-shadow-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="orphan-shadow-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Orphan Shadow", headers=teacher_headers)
    for team in (team_a, team_b):
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200
        container.training_lobby.set_ready(lobby_id=lobby["lobby_id"], team_id=team["team_id"], ready=True)

    scheduled = container.training_lobby.run_matchmaking_cycle(lobby_id=lobby["lobby_id"], requested_by="teacher-mm")
    primary_run_id = scheduled.last_scheduled_run_ids[0]
    shadow_run_id = scheduled.last_scheduled_run_ids[1]
    container.execution.finish_run(
        primary_run_id,
        {
            "status": "ok",
            "scores": {team_a["team_id"]: 20, team_b["team_id"]: 10},
            "placements": {team_a["team_id"]: 1, team_b["team_id"]: 2},
        },
    )
    assert container.execution.get_run(shadow_run_id).status is RunStatus.QUEUED

    container.training_lobby.reconcile_training_lobby_status(lobby_id=lobby["lobby_id"])

    assert container.execution.get_run(shadow_run_id).status is RunStatus.FINISHED


def test_lobby_winner_and_stats_use_group_scores_from_any_payload(client, teacher_headers) -> None:
    game = _create_game(
        client,
        slug="group_scores_from_any_payload",
        mode="multiplayer",
        min_players_per_match=2,
        max_players_per_match=2,
        headers=teacher_headers,
    )
    team_a = _create_ready_team(client, game_id=game["game_id"], captain="group-score-a", name="Alpha")
    team_b = _create_ready_team(client, game_id=game["game_id"], captain="group-score-b", name="Bravo")
    lobby = _create_training_lobby(client, game_id=game["game_id"], title="Group Scores", headers=teacher_headers)
    for team in (team_a, team_b):
        joined = client.post(
            f"/api/v1/lobbies/{lobby['lobby_id']}/teams/{team['team_id']}/join",
            json={},
            headers=teacher_headers,
        )
        assert joined.status_code == 200

    runs: list[dict] = []
    for team in (team_a, team_b):
        run = client.post(
            "/api/v1/runs",
            json={
                "team_id": team["team_id"],
                "game_id": game["game_id"],
                "requested_by": "teacher-mm",
                "run_kind": "training_match",
                "lobby_id": lobby["lobby_id"],
            },
            headers=teacher_headers,
        )
        assert run.status_code == 200
        queued = client.post(f"/api/v1/runs/{run.json()['run_id']}/queue", headers=teacher_headers)
        assert queued.status_code == 200
        runs.append(run.json())

    participants = [
        {"run_id": runs[0]["run_id"], "team_id": team_a["team_id"], "display_name": "Alpha"},
        {"run_id": runs[1]["run_id"], "team_id": team_b["team_id"], "display_name": "Bravo"},
    ]
    first_finished = client.post(
        f"/api/v1/internal/runs/{runs[0]['run_id']}/finished",
        json={
            "payload": {
                "status": "ok",
                "scores": {team_a["team_id"]: 10, team_b["team_id"]: 100},
                "match_participants": participants,
            }
        },
    )
    assert first_finished.status_code == 200
    second_finished = client.post(
        f"/api/v1/internal/runs/{runs[1]['run_id']}/finished",
        json={"payload": {"status": "ok", "scores": {team_b["team_id"]: 0}, "match_participants": participants}},
    )
    assert second_finished.status_code == 200

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    payload = lobby_view.json()
    archived_group = payload["archived_match_groups"][0]
    assert archived_group["winner_team_ids"] == [team_b["team_id"]]
    assert archived_group["scores_by_team"] == {team_a["team_id"]: 10.0, team_b["team_id"]: 100.0}
    stats_by_team = {item["team_id"]: item for item in payload["participant_stats"]}
    assert stats_by_team[team_a["team_id"]]["wins"] == 0
    assert stats_by_team[team_a["team_id"]]["average_score"] == 10.0
    assert stats_by_team[team_b["team_id"]]["wins"] == 1
    assert stats_by_team[team_b["team_id"]]["average_score"] == 100.0


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

    replays = client.get(f"/api/v1/replays?game_id={game['game_id']}&run_kind=training_match", headers=teacher_headers)
    assert replays.status_code == 200
    assert replays.json() == []

    lobby_view = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=teacher_headers)
    assert lobby_view.status_code == 200
    payload = lobby_view.json()
    assert payload["current_run_ids"] == []
    assert payload["archived_match_groups"] == []
    assert all(item["matches_total"] == 0 for item in payload["participant_stats"])


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

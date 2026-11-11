from datetime import timedelta

import pytest

from shared.kernel import utc_now


def _setup(client, container, *, count=4, access="public", builtin=False):
    game = client.post("/api/v1/games", json={
        "slug": "arena-journey", "title": "Арена", "mode": "multiplayer", "semver": "1.0.0",
        "min_players_per_match": 2, "max_players_per_match": 8,
        "required_slots": [{"key": "bot", "title": "Bot", "required": True}],
    }).json()
    if builtin:
        game = next(item for item in client.get("/api/v1/games").json() if item["slug"] == "ttt_connect5_v1")
    lobby = client.post("/api/v1/lobbies", json={
        "game_id": game["game_id"], "title": "Арена", "kind": "training", "access": access,
        "access_code": "private" if access == "code" else None,
    }).json()
    teams = []
    for index in range(count):
        name = f"player-{index}"
        team = client.post("/api/v1/teams", json={"game_id": game["game_id"], "name": name, "captain_user_id": name}).json()
        client.put(f"/api/v1/teams/{team['team_id']}/slots/bot", json={"actor_user_id": name, "code": "def make_choice(state):\n    return 0\n"})
        container.training_lobby.join_team(lobby["lobby_id"], team["team_id"], access_code="private" if access == "code" else None)
        teams.append(team)
    return lobby, teams


def test_teacher_viewing_starts_queued_bots_without_joining_queue(client, container):
    lobby, teams = _setup(client, container)
    for team in teams:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], "test-teacher")
    result = container.training_lobby.run_matchmaking_cycle(lobby["lobby_id"], "system")
    assert len(result.last_scheduled_run_ids) == len(teams)


def test_offline_queued_bots_wait_without_any_viewer(client, container):
    lobby, teams = _setup(client, container)
    for team in teams:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
    result = container.training_lobby.run_matchmaking_cycle(lobby["lobby_id"], "system")
    assert result.last_scheduled_run_ids == ()


def test_unqueued_player_viewing_starts_offline_queued_bots(client, container):
    lobby, teams = _setup(client, container)
    for team in teams[1:]:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], teams[0]["captain_user_id"])
    result = container.training_lobby.run_matchmaking_cycle(lobby["lobby_id"], "system")
    runs = container.execution.list_runs(lobby_id=lobby["lobby_id"])
    assert len(result.last_scheduled_run_ids) == 3
    assert teams[0]["team_id"] not in {run.team_id for run in runs}


def test_opening_lobby_starts_one_queued_bot_with_offline_opponent(client, container):
    lobby, teams = _setup(client, container)
    container.training_lobby.set_ready(lobby["lobby_id"], teams[0]["team_id"], True)
    response = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}")
    assert response.status_code == 200
    runs = container.execution.list_runs(lobby_id=lobby["lobby_id"])
    assert len(runs) == 2
    assert teams[0]["team_id"] in {run.team_id for run in runs}


def test_viewer_timeout_stops_new_offline_matches(client, container, monkeypatch):
    lobby, teams = _setup(client, container)
    for team in teams:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], "spectator")
    later = utc_now() + timedelta(seconds=21)
    monkeypatch.setattr("training_lobby.application.service.utc_now", lambda: later)
    assert container.training_lobby.run_due_matchmaking_cycles() == ()


def test_viewer_presence_is_shared_with_a_separate_matchmaker(client, container):
    from training_lobby.application.service import TrainingLobbyService
    from training_lobby.infrastructure.redis_presence import RedisLobbyViewerPresence

    class SharedRedis:
        def __init__(self):
            self.values = {}

        def set(self, key, value, *, ex):
            self.values[key] = (value, ex)

        def exists(self, key):
            return key in self.values

    shared = SharedRedis()
    container.training_lobby._viewer_presence = RedisLobbyViewerPresence(shared)
    matchmaker = TrainingLobbyService(
        repository=container.training_lobby._repository,
        game_catalog=container.game_catalog,
        team_workspace=container.team_workspace,
        execution=container.execution,
        viewer_presence=RedisLobbyViewerPresence(shared),
    )
    lobby, teams = _setup(client, container)
    for team in teams:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
    assert matchmaker.run_due_matchmaking_cycles() == ()
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], "spectator")
    assert len(matchmaker.run_due_matchmaking_cycles()[0].last_scheduled_run_ids) == len(teams)
    assert next(iter(shared.values.values()))[1] == 20


def test_unauthorized_private_lobby_view_cannot_wake_bots(client, container):
    lobby, teams = _setup(client, container, access="code")
    for team in teams:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
    session = client.post("/api/v1/auth/dev-login", json={"nickname": "outsider", "role": "student"}).json()
    response = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers={"X-Session-Id": session["session_id"]})
    assert response.status_code == 403
    assert container.training_lobby.run_due_matchmaking_cycles() == ()


def test_admin_bots_remain_queued_but_only_play_when_watched(client, container, monkeypatch):
    lobby, _ = _setup(client, container, builtin=True)
    admin = client.post("/api/v1/auth/dev-login", json={"nickname": "demo-admin", "role": "admin"}).json()
    headers = {"X-Session-Id": admin["session_id"]}
    for _ in range(2):
        response = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/admin-bots", headers=headers)
        assert response.status_code == 200, response.text
    later = utc_now() + timedelta(minutes=20)
    monkeypatch.setattr("training_lobby.application.service.utc_now", lambda: later)
    assert container.training_lobby.run_due_matchmaking_cycles() == ()
    response = client.get(f"/api/v1/lobbies/{lobby['lobby_id']}", headers=headers)
    assert response.status_code == 200
    bots = [state for state in response.json()["teams"] if state["is_bot"]]
    assert len(bots) == 2 and all(state["ready"] for state in bots)
    assert len(container.execution.list_runs(lobby_id=lobby["lobby_id"])) == 2


def test_requeueing_an_offline_player_starts_a_fresh_grace_period(client, container):
    lobby, teams = _setup(client, container)
    team_id = teams[0]["team_id"]
    model = container.training_lobby.get_lobby(lobby["lobby_id"])
    model.teams[team_id].last_seen_at = utc_now() - timedelta(hours=1)
    container.training_lobby._repository.save(model)
    container.training_lobby.set_ready(lobby["lobby_id"], team_id, True)
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], "spectator")
    assert container.training_lobby.get_lobby(lobby["lobby_id"]).teams[team_id].ready


def test_online_queue_fills_only_minimum_with_offline_code(client, container):
    lobby, teams = _setup(client, container)
    container.training_lobby.set_ready(lobby["lobby_id"], teams[0]["team_id"], True)
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], teams[0]["captain_user_id"])
    result = container.training_lobby.run_matchmaking_cycle(lobby["lobby_id"], "system")
    assert len(result.last_scheduled_run_ids) == 2
    runs = container.execution.list_runs(lobby_id=lobby["lobby_id"])
    assert teams[0]["team_id"] in {run.team_id for run in runs}


def test_online_players_are_prioritized_without_filling_maximum(client, container):
    lobby, teams = _setup(client, container, count=6)
    for team in teams[:3]:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
        container.training_lobby.mark_viewer_online(lobby["lobby_id"], team["captain_user_id"])
    result = container.training_lobby.run_matchmaking_cycle(lobby["lobby_id"], "system")
    assert len(result.last_scheduled_run_ids) == 3


def test_reconnect_after_ten_minutes_does_not_requeue(client, container):
    lobby, teams = _setup(client, container)
    team_id = teams[0]["team_id"]
    container.training_lobby.set_ready(lobby["lobby_id"], team_id, True)
    model = container.training_lobby.get_lobby(lobby["lobby_id"])
    model.teams[team_id].last_seen_at = utc_now() - timedelta(minutes=10, seconds=1)
    model.teams[team_id].queued_at = model.teams[team_id].last_seen_at
    container.training_lobby._repository.save(model)
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], teams[0]["captain_user_id"])
    state = container.training_lobby.get_lobby(lobby["lobby_id"]).teams[team_id]
    assert not state.ready
    assert "10 минут" in state.blocker_reason
    assert container.training_lobby.is_team_online(state)


@pytest.mark.parametrize("mode", ["queue", "selected"])
def test_competition_roster_is_fixed_to_selection(client, container, mode):
    lobby, teams = _setup(client, container)
    chosen = [team["team_id"] for team in teams[:2]]
    for team_id in chosen:
        container.training_lobby.set_ready(lobby["lobby_id"], team_id, True)
    response = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={
        "title": "Турнир", "participant_selection": mode, "team_ids": chosen,
    })
    assert response.status_code == 200, response.text
    competition = container.competition.get_competition(response.json()["competition_id"])
    assert set(competition.entrants) == set(chosen)


def test_invalid_roster_does_not_interrupt_training(client, container):
    lobby, _ = _setup(client, container)
    response = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={
        "title": "Турнир", "participant_selection": "selected", "team_ids": ["foreign-team"],
    })
    assert response.status_code == 422
    assert container.training_lobby.get_lobby(lobby["lobby_id"]).status.value == "open"
    assert not container.competition.list_competitions(lobby_id=lobby["lobby_id"])


@pytest.mark.parametrize("race", ["before_cancel", "after_cancel", "finished"])
def test_tournament_start_handles_concurrent_training_completion(client, container, monkeypatch, race):
    from execution.domain.model import RunKind
    from shared.kernel import ConflictError

    lobby, teams = _setup(client, container)
    for team in teams:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], "test-teacher")
    container.training_lobby.run_matchmaking_cycle(lobby["lobby_id"], "system")
    cancel = container.execution.cancel_run
    raced = False

    def racing_cancel(run_id, message=None):
        nonlocal raced
        if not raced:
            raced = True
            if race == "after_cancel":
                cancel(run_id, message)
            elif race == "finished":
                container.execution.finish_run(run_id, {"status": "finished", "scores": {team["team_id"]: 1 for team in teams}})
            raise ConflictError("Worker updated the training run")
        return cancel(run_id, message)

    monkeypatch.setattr(container.execution, "cancel_run", racing_cancel)
    response = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={
        "title": "Турнир", "match_size": 2,
    })
    assert response.status_code == 200, response.text
    assert raced
    runs = container.execution.list_runs(lobby_id=lobby["lobby_id"], run_kind=RunKind.TRAINING_MATCH)
    assert runs and all(run.status.value in {"finished", "canceled"} for run in runs)


def test_student_can_watch_other_tournament_match_but_not_source(client, container):
    lobby, teams = _setup(client, container, builtin=True)
    started = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={"title": "Турнир", "match_size": 2}).json()
    competition = client.get(f"/api/v1/competitions/{started['competition_id']}").json()
    match = competition["rounds"][0]["matches"][0]
    observer = next(team for team in teams if team["team_id"] not in match["team_ids"])
    login = client.post("/api/v1/auth/dev-login", json={"nickname": observer["captain_user_id"], "role": "student"}).json()
    headers = {"X-Session-Id": login["session_id"]}
    run_id = next(iter(match["run_ids_by_team"].values()))
    assert client.get(f"/api/v1/runs/{run_id}/watch-context", headers=headers).status_code == 200
    assert client.get(f"/api/v1/runs/{run_id}/code", headers=headers).status_code == 403


@pytest.mark.parametrize("access,expected", [("public", 200), ("code", 403)])
def test_training_spectator_needs_lobby_access_and_cannot_read_source(client, container, access, expected):
    lobby, teams = _setup(client, container, access=access, builtin=True)
    for team in teams:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], "test-teacher")
    current = container.training_lobby.run_matchmaking_cycle(lobby["lobby_id"], "system")
    run_id = current.last_scheduled_run_ids[0]
    login = client.post("/api/v1/auth/dev-login", json={"nickname": "spectator", "role": "student"}).json()
    headers = {"X-Session-Id": login["session_id"]}
    assert container.training_lobby.find_user_team_in_lobby(lobby["lobby_id"], "spectator") is None
    assert client.get(f"/api/v1/runs/{run_id}/watch-context", headers=headers).status_code == expected
    assert client.get(f"/api/v1/runs/{run_id}/code", headers=headers).status_code == 403


@pytest.mark.parametrize("tie", [False, True])
def test_round_results_do_not_automatically_launch_next_round(client, container, tie):
    lobby, _ = _setup(client, container)
    started = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={"title": "Турнир", "match_size": 2}).json()
    competition_id = started["competition_id"]
    competition = client.get(f"/api/v1/competitions/{competition_id}").json()
    for match in competition["rounds"][0]["matches"]:
        run_id = next(iter(match["run_ids_by_team"].values()))
        response = client.post(f"/api/v1/internal/runs/{run_id}/finished", json={"payload": {
            "status": "ok", "metrics": {},
            "placements": {team_id: 1 if tie else index + 1 for index, team_id in enumerate(match["team_ids"])},
            "scores": {team_id: 100 if tie else 100 - index for index, team_id in enumerate(match["team_ids"])},
            **({"tie_resolution": "explicit_tie"} if tie else {}),
        }})
        assert response.status_code == 200
    if tie:
        paused = client.get(f"/api/v1/competitions/{competition_id}").json()
        assert paused["status"] == "paused"
        matches = paused["rounds"][0]["matches"]
        for index, match in enumerate(matches):
            resolved = client.post(f"/api/v1/competitions/{competition_id}/matches/resolve", json={
                "round_index": 1, "match_id": match["match_id"], "advanced_team_ids": [match["team_ids"][0]],
            })
            assert resolved.status_code == 200, resolved.text
            result = resolved.json()
            assert len(result["rounds"]) == 1
            if index < len(matches) - 1:
                assert result["status"] == "paused" and result["pending_reason"]
            else:
                assert result["status"] == "running" and not result["pending_reason"]
    for _ in range(2):
        result = client.get(f"/api/v1/competitions/{competition_id}").json()
        assert len(result["rounds"]) == 1
        assert result["rounds"][0]["status"] == "finished"
    advanced = client.post(f"/api/v1/competitions/{competition_id}/advance", json={"requested_by": "test-teacher"})
    assert advanced.status_code == 200
    assert len(advanced.json()["rounds"]) == 2


def test_public_replay_keeps_game_events_and_only_own_diagnostics(client, container):
    lobby, teams = _setup(client, container, count=2, builtin=True)
    competition = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={"title": "Турнир"}).json()
    model = container.competition.get_competition(competition["competition_id"])
    match = model.rounds[0].matches[0]
    run_ids = list(match.run_ids_by_team.values())
    team_ids = list(match.run_ids_by_team)
    own_team = container.team_workspace.get_team(team_ids[0])
    payload = {"status": "ok", "metrics": {"active_slots": ["red", "blue"]},
               "placements": {team_ids[0]: 1, team_ids[1]: 2},
               "events": [{"type": "move", "role": "blue"},
                          {"type": "bot_print", "role": "red", "message": "own-log"},
                          {"type": "bot_print", "role": "bot", "message": "own-legacy-log"},
                          {"type": "bot_print", "role": "blue", "message": "other-log"},
                          {"type": "debug_snapshot", "role": "blue", "locals": {"secret": "hidden"}}],
               "frames": [{"tick": 0, "frame": {"board": [[0]]}}]}
    client.post(f"/api/v1/internal/runs/{run_ids[0]}/finished", json={"payload": payload})
    login = client.post("/api/v1/auth/dev-login", json={"nickname": own_team.captain_user_id, "role": "student"}).json()
    headers = {"X-Session-Id": login["session_id"]}
    for url in (f"/api/v1/runs/{run_ids[0]}", f"/api/v1/replays/runs/{run_ids[0]}"):
        response = client.get(url, headers=headers)
        assert response.status_code == 200, response.text
        assert "own-log" in response.text
        assert "own-legacy-log" in response.text
        assert "other-log" not in response.text
        assert "hidden" not in response.text
        assert '"move"' in response.text
    teacher = client.get(f"/api/v1/replays/runs/{run_ids[0]}")
    assert "other-log" in teacher.text
    assert "hidden" in teacher.text


def test_platform_failure_is_retried_with_frozen_source_and_seed(client, container):
    lobby, _ = _setup(client, container, count=2, builtin=True)
    started = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={
        "title": "Турнир", "tie_break_policy": "shared_advancement",
    }).json()
    competition_id = started["competition_id"]
    match = container.competition.get_competition(competition_id).rounds[0].matches[0]
    old_ids = dict(match.run_ids_by_team)
    old_runs = {team: container.execution.get_run(run_id) for team, run_id in old_ids.items()}
    primary = next(iter(old_ids.values()))
    failed = client.post(f"/api/v1/internal/runs/{primary}/failed", json={"message": "worker unavailable"})
    assert failed.status_code == 200
    paused = client.get(f"/api/v1/competitions/{competition_id}").json()
    assert paused["status"] == "paused"
    assert not paused["winner_team_ids"]
    assert paused["rounds"][0]["matches"][0]["advanced_team_ids"] == []
    response = client.post(f"/api/v1/competitions/{competition_id}/matches/{match.match_id}/retry")
    assert response.status_code == 200, response.text
    new_ids = response.json()["rounds"][0]["matches"][0]["run_ids_by_team"]
    for team_id, run_id in new_ids.items():
        retry = container.execution.get_run(run_id)
        assert run_id != old_ids[team_id]
        assert retry.snapshot_id == old_runs[team_id].snapshot_id
        assert retry.execution_options["seed"] == old_runs[team_id].execution_options["seed"]
        assert container.execution.get_run(old_ids[team_id]).status.value == "failed"


def test_student_opens_task_by_link_without_catalog_access(client):
    task = next(game for game in client.get("/api/v1/games").json() if game["mode"] == "single_task" and not game["is_hidden"])
    login = client.post("/api/v1/auth/dev-login", json={"nickname": "linked-task-student", "role": "student"}).json()
    headers = {"X-Session-Id": login["session_id"]}
    for path in ("/catalog/single-tasks", "/catalog/single-tasks/grouped", "/catalog/single-tasks/solved-summary"):
        assert client.get("/api/v1" + path, headers=headers).status_code == 403
    assert client.get(f"/api/v1/games/{task['game_id']}", headers=headers).status_code == 200
    games = client.get("/api/v1/games", headers=headers).json()
    assert all(game["mode"] != "single_task" for game in games)

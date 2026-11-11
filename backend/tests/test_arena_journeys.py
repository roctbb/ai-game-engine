from datetime import timedelta
import json

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
    own_match = next(item for item in competition['rounds'][0]['matches'] if observer['team_id'] in item['team_ids'])
    own_run_id = own_match['run_ids_by_team'][observer['team_id']]
    own_code = client.get(f'/api/v1/runs/{own_run_id}/code', headers=headers)
    assert own_code.status_code == 200, own_code.text
    assert 'def make_choice' in own_code.json()['codes_by_slot']['bot']
    assert client.post(f'/api/v1/runs/{own_run_id}/cancel', headers=headers).status_code == 403


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


@pytest.mark.parametrize("replay_pending", [False, True])
def test_public_replay_keeps_game_events_and_only_own_diagnostics(client, container, replay_pending):
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
    if replay_pending:
        container.spectator_replay.delete_runs(run_ids)
    login = client.post("/api/v1/auth/dev-login", json={"nickname": own_team.captain_user_id, "role": "student"}).json()
    headers = {"X-Session-Id": login["session_id"]}
    for url in (f"/api/v1/runs/{run_ids[0]}", *(f"/api/v1/replays/runs/{run_id}" for run_id in run_ids)):
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


@pytest.mark.parametrize("mode", ["instant", "sequential"])
def test_tournament_presentation_reveals_results_in_order(client, container, monkeypatch, mode):
    lobby, _ = _setup(client, container, count=4, builtin=True)
    started = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={
        "title": "Показ матчей", "participant_selection": "all", "presentation_mode": mode,
    })
    assert started.status_code == 200, started.text
    competition_id = started.json()["competition_id"]
    competition = container.competition.get_competition(competition_id)
    matches = competition.rounds[0].matches
    assert len(matches) == 2
    for match in matches:
        run_id = next(iter(match.run_ids_by_team.values()))
        finished = client.post(f"/api/v1/internal/runs/{run_id}/finished", json={"payload": {
            "status": "ok", "metrics": {}, "frames": [{"tick": tick} for tick in range(20)],
            "scores": {team_id: 10 - index for index, team_id in enumerate(match.team_ids)},
            "placements": {team_id: index + 1 for index, team_id in enumerate(match.team_ids)},
        }})
        assert finished.status_code == 200, finished.text
    now = max(container.execution.get_run(run_id).finished_at for match in matches for run_id in match.run_ids_by_team.values())
    monkeypatch.setattr("competition.application.service.utc_now", lambda: now)
    response = client.get(f"/api/v1/competitions/{competition_id}").json()
    assert response["presentation_mode"] == mode
    if mode == "instant":
        assert response["broadcast"] is None
        assert all(match["scores_by_team"] for match in response["rounds"][0]["matches"])
        assert response["rounds"][0]["status"] == "finished"
        return

    assert response["broadcast"]["match_id"] == matches[0].match_id
    assert response["broadcast"]["phase"] == "playing"
    assert all(not match["scores_by_team"] for match in response["rounds"][0]["matches"])
    assert all(run["result_payload"] is None for run in client.get(f"/api/v1/competitions/{competition_id}/runs").json())
    scheduled = container.competition.get_competition(competition_id).rounds[0].matches
    assert scheduled[0].show_ends_at == scheduled[1].show_started_at
    for match in scheduled:
        clocks = [client.get(f"/api/v1/runs/{run_id}/watch-context").json()["first_show"]
                  for run_id in match.run_ids_by_team.values()]
        assert clocks[0] == clocks[1]
        assert clocks[0]["started_at"] == match.show_started_at.isoformat().replace("+00:00", "Z")

    now = scheduled[0].show_reveal_at + timedelta(milliseconds=10)
    stream = client.get(f"/api/v1/competitions/{competition_id}/stream?max_events=1")
    response = next(json.loads(line.removeprefix("data: "))["payload"]
                    for line in stream.text.splitlines() if line.startswith("data: "))
    assert response["broadcast"]["phase"] == "result"
    assert response["rounds"][0]["matches"][0]["scores_by_team"]
    assert not response["rounds"][0]["matches"][1]["scores_by_team"]
    now = scheduled[1].show_started_at + timedelta(milliseconds=10)
    response = client.get(f"/api/v1/competitions/{competition_id}").json()
    assert response["broadcast"]["match_id"] == matches[1].match_id
    assert response["broadcast"]["phase"] == "playing"
    now = scheduled[1].show_reveal_at + timedelta(milliseconds=10)
    response = client.post(f"/api/v1/competitions/{competition_id}/advance", json={"requested_by": "test-teacher"}).json()
    assert len(response["rounds"]) == 1  # The result hold must not be cut short by the next round.
    assert response["rounds"][0]["status"] == "finished"
    now = scheduled[1].show_ends_at + timedelta(milliseconds=10)
    response = client.get(f"/api/v1/competitions/{competition_id}").json()
    assert response["broadcast"] is None
    assert len(response["rounds"]) == 1  # New rounds still start on the teacher's command.
    advanced = client.post(f"/api/v1/competitions/{competition_id}/advance", json={"requested_by": "test-teacher"}).json()
    assert len(advanced["rounds"]) == 2
    assert advanced["broadcast"]["phase"] == "preparing"


def test_pending_tie_does_not_stop_revealing_later_broadcast_matches(client, container, monkeypatch):
    lobby, _ = _setup(client, container, count=4, builtin=True)
    started = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={
        "title": "Ничьи на показе", "participant_selection": "all", "presentation_mode": "sequential",
    }).json()
    competition_id = started["competition_id"]
    for match in container.competition.get_competition(competition_id).rounds[0].matches:
        response = client.post(f"/api/v1/internal/runs/{next(iter(match.run_ids_by_team.values()))}/finished", json={"payload": {
            "status": "ok", "metrics": {}, "frames": [{"tick": 0}, {"tick": 1}],
            "scores": {team: 0 for team in match.team_ids}, "placements": {team: 1 for team in match.team_ids},
            "tie_resolution": "explicit_tie",
        }})
        assert response.status_code == 200, response.text
    client.get(f"/api/v1/competitions/{competition_id}")
    matches = container.competition.get_competition(competition_id).rounds[0].matches
    now = matches[0].show_reveal_at + timedelta(milliseconds=10)
    monkeypatch.setattr("competition.application.service.utc_now", lambda: now)
    assert client.get(f"/api/v1/competitions/{competition_id}").json()["status"] == "paused"
    now = matches[1].show_ends_at + timedelta(milliseconds=10)
    response = client.get(f"/api/v1/competitions/{competition_id}").json()
    assert all(match["status"] == "awaiting_tiebreak" and len(match["scores_by_team"]) == 2
               for match in response["rounds"][0]["matches"])
    for match in matches:
        resolved = client.post(f"/api/v1/competitions/{competition_id}/matches/resolve", json={
            "round_index": 1, "match_id": match.match_id, "advanced_team_ids": [match.team_ids[0]],
        })
        assert resolved.status_code == 200, resolved.text
    response = client.get(f"/api/v1/competitions/{competition_id}").json()
    assert response["status"] == "running" and response["rounds"][0]["status"] == "finished"
    assert len(response["rounds"]) == 1


@pytest.mark.parametrize("naive_timestamp", [False, True])
def test_first_show_uses_common_training_batch_clock(client, container, monkeypatch, naive_timestamp):
    from datetime import datetime

    lobby, teams = _setup(client, container, builtin=True)
    for team in teams:
        container.training_lobby.set_ready(lobby["lobby_id"], team["team_id"], True)
    container.training_lobby.mark_viewer_online(lobby["lobby_id"], "test-teacher")
    scheduled = container.training_lobby.run_matchmaking_cycle(lobby["lobby_id"], "system")
    groups = scheduled.last_scheduled_match_groups
    assert len(groups) == 2
    def finish_group(group):
        team_ids = [container.execution.get_run(run_id).team_id for run_id in group]
        payload = {"status": "ok", "metrics": {},
                   "scores": {team_id: 100 - i for i, team_id in enumerate(team_ids)},
                   "placements": {team_id: i + 1 for i, team_id in enumerate(team_ids)},
                   "frames": [{"tick": i, "frame": {"board": [[0]]}} for i in range(80)]}
        response = client.post(f"/api/v1/internal/runs/{group[0]}/finished", json={"payload": payload})
        assert response.status_code == 200, response.text
    finish_group(groups[0])
    waiting = client.get(f"/api/v1/runs/{groups[0][0]}/watch-context").json()
    assert waiting["first_show"] == {"started_at": None, "frame_ms": 500}
    earlier = utc_now() - timedelta(seconds=3)
    if naive_timestamp:
        earlier = earlier.replace(tzinfo=None)
    for run_id in groups[0]:
        run = container.execution._run_repository.get(run_id)
        run.finished_at = earlier
        container.execution._run_repository.save(run)
    finish_group(groups[1])
    expected = max(container.execution.get_run(run_id).finished_at for run_id in groups[1])
    clocks = [client.get(f"/api/v1/runs/{group[0]}/watch-context").json()["first_show"] for group in groups]
    assert clocks[0] == clocks[1]
    assert datetime.fromisoformat(clocks[0]["started_at"]) == expected
    later = expected + timedelta(seconds=12)
    monkeypatch.setattr("execution.api.router.utc_now", lambda: later)
    joined_late = client.get(f"/api/v1/runs/{groups[0][0]}/watch-context").json()
    assert joined_late["first_show"] == clocks[0]
    assert datetime.fromisoformat(joined_late["server_now"]) == later


def test_tournament_first_show_clock_is_shared_within_match_not_whole_round(client, container):
    lobby, _ = _setup(client, container, builtin=True)
    competition = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={"title": "Турнир"}).json()
    matches = container.competition.get_competition(competition["competition_id"]).rounds[0].matches
    first_ids = list(matches[0].run_ids_by_team.values())
    second_id = next(iter(matches[1].run_ids_by_team.values()))
    team_ids = list(matches[0].run_ids_by_team)
    payload = {"status": "ok", "metrics": {},
               "scores": {team_id: 100 - i for i, team_id in enumerate(team_ids)},
               "placements": {team_id: i + 1 for i, team_id in enumerate(team_ids)},
               "frames": [{"tick": i, "frame": {"board": [[0]]}} for i in range(80)]}
    assert client.post(f"/api/v1/internal/runs/{first_ids[0]}/finished", json={"payload": payload}).status_code == 200
    contexts = [client.get(f"/api/v1/runs/{run_id}/watch-context").json() for run_id in first_ids]
    assert contexts[0]["first_show"]["started_at"]
    assert contexts[0]["first_show"] == contexts[1]["first_show"]
    pending = client.get(f"/api/v1/runs/{second_id}/watch-context").json()
    assert pending["first_show"]["started_at"] is None


def test_just_archived_tournament_opens_as_free_replay(client, container):
    lobby, _ = _setup(client, container, count=2, builtin=True)
    started = client.post(f"/api/v1/lobbies/{lobby['lobby_id']}/competitions/start", json={
        "title": "Быстрый архив", "participant_selection": "all", "presentation_mode": "instant",
    }).json()
    competition_id = started['competition_id']
    match = container.competition.get_competition(competition_id).rounds[0].matches[0]
    run_ids = list(match.run_ids_by_team.values())
    response = client.post(f"/api/v1/internal/runs/{run_ids[0]}/finished", json={'payload': {
        'status': 'ok', 'metrics': {}, 'frames': [{'tick': tick} for tick in range(100)],
        'scores': {team: 1 - index for index, team in enumerate(match.team_ids)},
        'placements': {team: index + 1 for index, team in enumerate(match.team_ids)},
    }})
    assert response.status_code == 200, response.text
    assert client.get(f'/api/v1/competitions/{competition_id}').json()['status'] == 'completed'
    assert client.get(f'/api/v1/runs/{run_ids[0]}/watch-context').json()['first_show'] is not None
    assert client.post(f'/api/v1/competitions/{competition_id}/finish').status_code == 200
    login = client.post('/api/v1/auth/dev-login', json={'nickname': 'archived-viewer', 'role': 'student'}).json()
    for headers in ({}, {'X-Session-Id': login['session_id']}):
        for run_id in run_ids:
            context = client.get(f'/api/v1/runs/{run_id}/watch-context', headers=headers)
            assert context.status_code == 200
            assert context.json()['first_show'] is None


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

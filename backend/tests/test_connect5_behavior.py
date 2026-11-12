import importlib.util
from datetime import datetime, timedelta, UTC
from pathlib import Path

import pytest


def engine():
    path = Path(__file__).resolve().parents[2] / "games/tic_tac_toe/engine.py"
    spec = importlib.util.spec_from_file_location("connect5_behavior", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIRST_FREE = "def make_choice(field, role):\n    for x in range(5):\n        for y in range(5):\n            if field[x][y] == 0: return x, y\n"
CENTER = "def make_choice(field, role):\n    if field[2][2] == 0: return 2, 2\n    for x in range(5):\n        for y in range(5):\n            if field[x][y] == 0: return x, y\n"


def play(first, second=FIRST_FREE):
    return engine().run({"run_kind": "competition_match", "seed": "repeatable", "participants": [
        {"team_id": "a", "codes_by_slot": {"bot": first}},
        {"team_id": "b", "codes_by_slot": {"bot": second}},
    ]})


@pytest.mark.parametrize("imports", ["import random as r", "from random import choice"])
def test_random_import_does_not_replace_player_code(imports):
    result = play(imports + "\n" + CENTER)
    assert not result["metrics"].get("compile_errors")
    first = next(event for event in result["events"] if event["type"] == "move")
    assert (first["x"], first["y"]) == (2, 2)


def test_random_choices_are_reproducible_and_player_local():
    code = "import random\ndef make_choice(field, role):\n    free = [(x,y) for x in range(5) for y in range(5) if field[x][y] == 0]\n    return random.choice(free)\n"
    assert play(code)["frames"] == play(code)["frames"]
    assert not play(code)["metrics"]["bot_errors"]


@pytest.mark.parametrize("code,kind,line", [
    ("import os\n" + CENTER, "compile_error", 1),
    ("def make_choice(field, role):\n    return 1 / 0\n", "bot_error", 2),
    ("def make_choice(field, role):\n    return len(1)\n", "bot_error", 2),
    ("def make_choice(field, role):\n    return 99, 99\n", "bot_error", None),
])
def test_code_error_is_attributed_and_skips_the_turn(code, kind, line):
    result = play(code)
    errors = [event for event in result["events"] if event["type"] == kind]
    assert errors and errors[0]["team_id"] == "a"
    assert errors[0]["line"] == line
    assert result["frames"][1]["frame"]["board"] == [[0] * 5 for _ in range(5)]
    first_move = next(event for event in result["events"] if event["type"] == "move")
    assert first_move["role"] == -1
    assert any(event["type"] == "turn_skipped" and event["team_id"] == "a" for event in result["events"])
    assert result["metrics"]["bot_errors_by_team"]["a"] > 0
    assert result["metrics"]["bot_errors_by_team"]["b"] == 0


def test_draw_scores_half_a_point_per_player():
    result = play(CENTER, CENTER)
    assert result["metrics"]["draw"] is True
    assert result["scores"] == {"a": 0.5, "b": 0.5}


def start_series(client, teacher_headers, mode):
    game = next(game for game in client.get("/api/v1/games").json() if game["slug"] == "ttt_connect5_v1")
    teams = []
    for name in ("series-a", "series-b"):
        team = client.post("/api/v1/teams", json={"game_id": game["game_id"], "name": name, "captain_user_id": name}).json()
        client.put(f"/api/v1/teams/{team['team_id']}/slots/bot", json={"actor_user_id": name, "code": CENTER})
        teams.append(team["team_id"])
    created = client.post("/api/v1/competitions", headers=teacher_headers, json={
        "game_id": game["game_id"], "title": "Draw series", "format": "single_elimination",
        "tie_break_policy": "replay_then_shared", "code_policy": "locked_on_start",
        "advancement_top_k": 1, "match_size": 2, "presentation_mode": mode,
    })
    assert created.status_code == 200, created.text
    comp = created.json()
    for team in teams:
        assert client.post(f"/api/v1/competitions/{comp['competition_id']}/register", headers=teacher_headers, json={"team_id": team}).status_code == 200
    started = client.post(f"/api/v1/competitions/{comp['competition_id']}/start", headers=teacher_headers, json={"requested_by": "teacher"})
    assert started.status_code == 200, started.text
    return started.json(), teams


@pytest.mark.parametrize("mode", ["instant", "sequential"])
@pytest.mark.parametrize("decisive_second", [False, True])
def test_draw_series_replays_and_terminates(client, container, teacher_headers, monkeypatch, mode, decisive_second):
    from competition.infrastructure.sqlalchemy_repository import _map_competition_to_orm, _map_competition_from_orm
    comp, teams = start_series(client, teacher_headers, mode)
    url = f"/api/v1/competitions/{comp['competition_id']}"
    initial = comp["rounds"][0]["matches"][0]
    snapshots = {team: container.execution.get_run(rid).snapshot_id for team, rid in initial["run_ids_by_team"].items()}
    original_order = initial["team_ids"]
    count = 2 if decisive_second else 3
    for attempt in range(1, count + 1):
        match = comp["rounds"][0]["matches"][-1]
        assert match["attempt_number"] == attempt
        assert match["team_ids"] == (original_order if attempt % 2 else original_order[::-1])
        for team, rid in match["run_ids_by_team"].items():
            assert container.execution.get_run(rid).snapshot_id == snapshots[team]
        won = decisive_second and attempt == 2
        payload = {"status": "finished", "metrics": {"draw": not won},
                   "scores": {teams[0]: 1 if won else .5, teams[1]: 0 if won else .5},
                   "placements": {teams[0]: 1, teams[1]: 2 if won else 1},
                   "frames": [{"tick": 0, "frame": {}}, {"tick": 1, "frame": {}}], "events": []}
        if not won:
            payload["tie_resolution"] = "explicit_tie"
        container.execution.finish_run(next(iter(match["run_ids_by_team"].values())), payload)
        if mode == "sequential" and attempt == 1:
            early = client.get(url, headers=teacher_headers).json()
            assert len(early["rounds"][0]["matches"]) == 1
            assert early["status"] == "running"
            monkeypatch.setattr("competition.application.service.utc_now", lambda: datetime.now(UTC) + timedelta(days=1))
        response = client.get(url, headers=teacher_headers)
        assert response.status_code == 200, response.text
        comp = response.json()
        if attempt < count:
            assert comp["status"] == "running"
            assert len(comp["rounds"][0]["matches"]) == attempt + 1
            # Repeated viewers must not schedule additional attempts.
            assert len(client.get(url, headers=teacher_headers).json()["rounds"][0]["matches"]) == attempt + 1
    assert comp["status"] == "completed"
    assert set(comp["winner_team_ids"]) == ({teams[0]} if decisive_second else set(teams))
    last = comp["rounds"][0]["matches"][-1]
    assert last["series_scores_by_team"] == ({teams[0]: 1.5, teams[1]: .5} if decisive_second else {team: 1.5 for team in teams})
    saved = container.competition.get_competition(comp["competition_id"])
    restored = _map_competition_from_orm(_map_competition_to_orm(saved))
    assert len(restored.rounds[0].matches) == count
    assert restored.rounds[0].matches[-1].series_scores_by_team == last["series_scores_by_team"]
    ended = client.post(url + "/finish", headers=teacher_headers)
    assert ended.status_code == 200
    assert ended.json()["status"] == "finished"
    assert len(client.get(url, headers=teacher_headers).json()["rounds"][0]["matches"]) == count


@pytest.mark.parametrize("legacy", [False, True])
def test_replay_shows_only_own_bot_errors(client, container, teacher_headers, legacy):
    comp, teams = start_series(client, teacher_headers, "instant")
    match = comp["rounds"][0]["matches"][0]
    primary = match["team_ids"][0]
    other = match["team_ids"][1]
    if legacy:
        payload = {
            "metrics": {"compile_error": "first private error", "opponent_compile_error": "second private error"},
            "events": [{"type": "compile_error", "message": message}
                       for message in ("first private error", "second private error")],
        }
    else:
        payload = {
            "metrics": {"bot_errors_by_team": {primary: 2, other: 3}, "bot_errors": 5},
            "events": [{"type": "bot_error", "team_id": team, "line": 3, "message": message}
                       for team, message in ((primary, "first private error"), (other, "second private error"))],
        }
    payload.update({"status": "finished", "tie_resolution": "explicit_tie", "scores": {team: .5 for team in teams},
                    "placements": {team: 1 for team in teams}, "frames": [{"tick": 0, "frame": {}}]})
    run_id = match["run_ids_by_team"][primary]
    container.execution.finish_run(run_id, payload)
    for team in teams:
        owner = container.team_workspace.get_team(team).captain_user_id
        login = client.post("/api/v1/auth/dev-login", json={"nickname": owner, "role": "student"}).json()
        response = client.get(f"/api/v1/replays/runs/{run_id}", headers={"X-Session-Id": login["session_id"]})
        assert response.status_code == 200, response.text
        replay = response.json()
        messages = [event["message"] for event in replay["events"] if event["type"] in {"compile_error", "bot_error"}]
        assert messages == ["first private error" if team == primary else "second private error"]
        error = next(event for event in replay["events"] if event["type"] in {"compile_error", "bot_error"})
        assert error["team_id"] == team
        assert ("second private error" if team == primary else "first private error") not in response.text

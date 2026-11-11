"""Exercise both Arena journeys against a running, isolated Docker stack.

Requires development login and automatic workers. Creates uniquely named test
users and one lobby, and leaves its completed tournament available for review.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
from uuid import uuid4


class Api:
    def __init__(self, base: str, nickname: str, role: str):
        self.base = base.rstrip("/")
        self.nickname = nickname
        self.headers: dict[str, str] = {}
        session = self.call("POST", "/auth/dev-login", {"nickname": nickname, "role": role})
        self.headers["X-Session-Id"] = session["session_id"]

    def call(self, method: str, path: str, body=None, *, expected=200):
        headers = {**self.headers, "Content-Type": "application/json"}
        request = urllib.request.Request(
            self.base + path, method=method, headers=headers,
            data=json.dumps(body).encode() if body is not None else None,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                status, raw = response.status, response.read()
        except urllib.error.HTTPError as error:
            status, raw = error.code, error.read()
        result = json.loads(raw) if raw else None
        if status != expected:
            raise RuntimeError(f"{method} {path}: HTTP {status}, expected {expected}; {str(result)[:300]}")
        return result


def wait_run(api: Api, run_id: str, timeout: int):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        run = api.call("GET", f"/runs/{run_id}")
        if run["status"] == "finished":
            return run
        if run["status"] in {"failed", "canceled", "timeout"}:
            raise RuntimeError(f"Execution {run_id}: {run['status']} ({run.get('error_message')})")
        time.sleep(.4)
    raise TimeoutError(f"Execution {run_id} did not finish")


def wait_round(api: Api, competition_id: str, index: int, timeout: int):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        competition = api.call("GET", f"/competitions/{competition_id}")
        current = next(item for item in competition["rounds"] if item["round_index"] == index)
        for match in current["matches"]:
            if match["status"] == "awaiting_tiebreak":
                # This is an explicit organizer choice for the test fixture,
                # not automatic winner selection in the application.
                for run_id in match["run_ids_by_team"].values():
                    wait_run(api, run_id, timeout)
                api.call("POST", f"/competitions/{competition_id}/matches/resolve", {
                    "round_index": index, "match_id": match["match_id"],
                    "advanced_team_ids": match["team_ids"][:competition["advancement_top_k"]],
                })
        if current["status"] == "finished":
            return competition
        time.sleep(.4)
    raise TimeoutError(f"Tournament round {index} did not finish")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="http://localhost:8000/api/v1")
    parser.add_argument("--scheduler", default="http://localhost:8010")
    parser.add_argument("--worker", default="http://localhost:8020")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    for url in [args.backend + "/health", args.scheduler + "/health", args.worker + "/health"]:
        with urllib.request.urlopen(url, timeout=15) as response:
            assert response.status == 200, url

    prefix = "arena-e2e-" + uuid4().hex[:8]
    admin = Api(args.backend, prefix + "-admin", "admin")
    teacher = Api(args.backend, prefix + "-teacher", "teacher")
    student = Api(args.backend, prefix + "-student", "student")
    outsider = Api(args.backend, prefix + "-viewer", "student")
    games = teacher.call("GET", "/games")
    task = next(game for slug in ("knight_coins_v1", "maze_escape_v1", "gate_keys_v1") for game in games
                if game["slug"] == slug)
    multiplayer = next(game for game in games if game["slug"] == "ttt_connect5_v1")

    print("[1/8] Roles, direct task link and catalog access", flush=True)
    student.call("GET", "/catalog/single-tasks", expected=403)
    assert all(game["mode"] != "single_task" for game in student.call("GET", "/games"))
    assert student.call("GET", "/games/" + task["game_id"])["game_id"] == task["game_id"]
    templates = teacher.call("GET", f"/games/{task['game_id']}/templates")
    team = student.call("POST", "/teams", {
        "game_id": task["game_id"], "name": student.nickname, "captain_user_id": student.nickname,
    })
    codes = {}
    for item in templates["templates"]:
        demo = next((strategy for strategy in templates.get("demo_strategies", []) if strategy["slot_key"] == item["slot_key"]), None)
        code = demo["code"] if demo else item["code"]
        codes[item["slot_key"]] = code
        student.call("PUT", f"/teams/{team['team_id']}/slots/{item['slot_key']}", {"actor_user_id": student.nickname, "code": code})

    print("[2/8] Real task execution, immutable source and private access", flush=True)
    good = student.call("POST", f"/single-tasks/{task['game_id']}/run", {"team_id": team["team_id"], "requested_by": student.nickname})
    good = wait_run(student, good["run_id"], args.timeout)
    assert good.get("worker_id"), "The attempt must be executed by a real worker"
    source = student.call("GET", f"/runs/{good['run_id']}/code")
    assert source["codes_by_slot"] == codes and source.get("captured_at")
    outsider.call("GET", f"/runs/{good['run_id']}/code", expected=403)
    teacher.call("GET", f"/runs/{good['run_id']}/code")

    print("[3/8] Code error, history and preservation of best result", flush=True)
    board = student.call("GET", f"/single-tasks/{task['game_id']}/leaderboard?limit=200")
    previous = next(entry for entry in board["entries"] if entry["user_id"] == student.nickname)["best_score"]
    slot = next(iter(codes))
    student.call("PUT", f"/teams/{team['team_id']}/slots/{slot}", {"actor_user_id": student.nickname, "code": "def make_move(x, y, board):\n    return 1 / 0\n"})
    bad = student.call("POST", f"/single-tasks/{task['game_id']}/run", {"team_id": team["team_id"], "requested_by": student.nickname})
    bad = wait_run(student, bad["run_id"], args.timeout)
    assert "ZeroDivisionError" in json.dumps(bad.get("result_payload"), ensure_ascii=False)
    assert student.call("GET", f"/runs/{good['run_id']}/code")["codes_by_slot"] == codes
    attempts = student.call("GET", f"/single-tasks/{task['game_id']}/attempts")
    assert {good["run_id"], bad["run_id"]} <= {run["run_id"] for run in attempts}
    assert all(run["requested_by"] == student.nickname for run in attempts)
    board = student.call("GET", f"/single-tasks/{task['game_id']}/leaderboard?limit=200")
    assert next(entry for entry in board["entries"] if entry["user_id"] == student.nickname)["best_score"] == previous

    print("[4/8] Queued demo bots remain idle without a viewer", flush=True)
    lobby = teacher.call("POST", "/lobbies", {"game_id": multiplayer["game_id"], "title": prefix, "kind": "training", "access": "public", "max_teams": 16})
    lobby_id = lobby["lobby_id"]
    for _ in range(4):
        lobby = admin.call("POST", f"/lobbies/{lobby_id}/admin-bots")
    bot_ids = [item["team_id"] for item in lobby["teams"] if item["is_bot"]]
    assert len(bot_ids) == 4 and all(item["ready"] for item in lobby["teams"])
    assert not admin.call("GET", f"/runs?lobby_id={lobby_id}")

    print("[5/8] A spectator wakes real matches; new matches stop after viewing expires", flush=True)
    student.call("POST", f"/lobbies/{lobby_id}/presence", expected=204)
    deadline = time.monotonic() + args.timeout
    runs = []
    while time.monotonic() < deadline:
        runs = admin.call("GET", f"/runs?lobby_id={lobby_id}")
        if len(runs) >= 4:
            break
        time.sleep(.4)
    assert len(runs) == 4, "Four queued bots should produce two real two-player matches"
    training = [wait_run(admin, run["run_id"], args.timeout) for run in runs]
    assert any(run.get("worker_id") for run in training)
    max_frames = max(len(admin.call("GET", f"/replays/runs/{run['run_id']}")["frames"]) for run in training)
    time.sleep(max(22, max_frames * .5 + 6))
    idle_count = len(admin.call("GET", f"/runs?lobby_id={lobby_id}"))
    time.sleep(5)
    assert len(admin.call("GET", f"/runs?lobby_id={lobby_id}")) == idle_count

    print("[6/8] Explicit tournament roster, first round and manual round start", flush=True)
    started = teacher.call("POST", f"/lobbies/{lobby_id}/competitions/start", {
        "title": prefix + " tournament", "participant_selection": "selected", "team_ids": bot_ids,
        "match_size": 2, "advancement_top_k": 1, "tie_break_policy": "manual",
    })
    competition_id = started["competition_id"]
    competition = teacher.call("GET", f"/competitions/{competition_id}")
    assert {item["team_id"] for item in competition["entrants"]} == set(bot_ids)
    first_index = competition["current_round_index"]
    competition = wait_round(teacher, competition_id, first_index, args.timeout)
    assert len(competition["rounds"]) == 1
    time.sleep(1.5)
    assert len(teacher.call("GET", f"/competitions/{competition_id}")["rounds"]) == 1
    advanced = teacher.call("POST", f"/competitions/{competition_id}/advance", {"requested_by": teacher.nickname})
    competition = wait_round(teacher, competition_id, advanced["rounds"][-1]["round_index"], args.timeout)
    assert competition["status"] == "completed" and competition["winner_team_ids"]

    print("[7/8] Tournament archive, arbitrary match replay and protected source", flush=True)
    teacher.call("POST", f"/lobbies/{lobby_id}/competitions/{competition_id}/finish")
    archive = student.call("GET", f"/lobbies/{lobby_id}/competitions/archive")
    assert any(item["competition_id"] == competition_id for item in archive["items"])
    competition = student.call("GET", f"/competitions/{competition_id}")
    assert competition["status"] == "finished"
    match = competition["rounds"][0]["matches"][-1]
    other_run = next(iter(match["run_ids_by_team"].values()))
    student.call("GET", f"/runs/{other_run}")
    replay = student.call("GET", f"/replays/runs/{other_run}")
    assert replay["frames"], "An arbitrary tournament match must have a usable replay"
    student.call("GET", f"/runs/{other_run}/code", expected=403)
    teacher.call("GET", f"/runs/{other_run}/code")
    teacher.call("POST", f"/lobbies/{lobby_id}/status", {"status": "paused"})

    print("[8/8] Worker health and execution evidence", flush=True)
    workers = admin.call("GET", "/workers")
    assert any(worker["status"] == "online" for worker in workers)
    report = {"status": "passed", "task_id": task["game_id"], "good_run_id": good["run_id"], "error_run_id": bad["run_id"], "lobby_id": lobby_id, "competition_id": competition_id, "other_match_run_id": other_run, "tournament_rounds": len(competition["rounds"]), "training_run_count_after_idle": idle_count}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

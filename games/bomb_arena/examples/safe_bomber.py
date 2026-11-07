# ruff: noqa: F821
# blast_times(state) предоставляется движком.
from collections import deque
from copy import deepcopy

DIRECTIONS = [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1), ("stay", 0, 0)]


def escape(state, plant):
    me = state["me"]
    player = state["players"][me]
    forecast = deepcopy(state)
    if plant:
        forecast["bombs"].append({"owner": me, "x": player["x"], "y": player["y"],
                                  "range": player["range"], "explode_at": state["tick"] + state["fuse"]})
    danger = blast_times(forecast, all_phases=True)
    bombs = {(b["x"], b["y"]): b["explode_at"] for b in forecast["bombs"]}
    occupied = {(p["x"], p["y"]) for s, p in state["players"].items() if s != me and p["alive"]}
    horizon = state["fuse"] + 2
    queue = deque([(player["x"], player["y"], 0, None)])
    seen = set()
    best, best_value = None, -100000
    while queue:
        x, y, elapsed, first = queue.popleft()
        if elapsed == horizon:
            ring = min(x, y, state["width"] - 1 - x, state["height"] - 1 - y)
            crates = sum(state["board"][x + dx][y + dy] == 1
                         for _, dx, dy in DIRECTIONS[:4]
                         if 0 <= x + dx < state["width"] and 0 <= y + dy < state["height"])
            bonuses = sum(8 for b in state["powerups"] if b["x"] == x and b["y"] == y)
            value = crates * 3 + bonuses + ring * .1
            if value > best_value:
                best, best_value = first, value
            continue
        for move, dx, dy in DIRECTIONS:
            nx, ny, step = x + dx, y + dy, elapsed + 1
            if not (0 <= nx < state["width"] and 0 <= ny < state["height"]):
                continue
            arrival = state["tick"] + step
            if state["board"][nx][ny] != 0 or (nx, ny) in occupied:
                continue
            if (nx, ny) in bombs and arrival <= bombs[(nx, ny)] and (nx, ny) != (x, y):
                continue
            if arrival in danger[nx][ny]:
                continue
            ring = min(nx, ny, state["width"] - 1 - nx, state["height"] - 1 - ny)
            collapse = state["shrink"]["start"] + (ring - 1) * state["shrink"]["interval"]
            if arrival >= collapse:
                continue
            key = (nx, ny, step)
            if key not in seen:
                seen.add(key)
                queue.append((nx, ny, step, move if first is None else first))
    return best


def make_move(state):
    me = state["me"]
    player = state["players"][me]
    x, y = player["x"], player["y"]
    active = sum(b["owner"] == me for b in state["bombs"])
    useful = False
    for _, dx, dy in DIRECTIONS[:4]:
        for distance in range(1, player["range"] + 1):
            nx, ny = x + dx * distance, y + dy * distance
            if not (0 <= nx < state["width"] and 0 <= ny < state["height"]):
                break
            if state["board"][nx][ny] in (-1, -2):
                break
            if state["board"][nx][ny] == 1:
                useful = True
                break
            if any(p["alive"] and s != me and p["x"] == nx and p["y"] == ny
                   for s, p in state["players"].items()):
                useful = True
    if useful and active < player["capacity"] and not any(b["x"] == x and b["y"] == y for b in state["bombs"]):
        move = escape(state, True)
        if move is not None:
            return {"move": move, "bomb": True}
    return {"move": escape(state, False) or "stay", "bomb": False}

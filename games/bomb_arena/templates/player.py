# ruff: noqa: F821
# Безопасное начало: пока без установки бомб.
# blast_times(state)[x][y] — ближайший известный взрыв или None.
def make_move(state):
    player = state["players"][state["me"]]
    danger = blast_times(state)
    occupied = [(b["x"], b["y"]) for b in state["bombs"]]
    for move, dx, dy in (("right", 1, 0), ("down", 0, 1),
                         ("left", -1, 0), ("up", 0, -1), ("stay", 0, 0)):
        x, y = player["x"] + dx, player["y"] + dy
        if not (0 <= x < state["width"] and 0 <= y < state["height"]):
            continue
        if state["board"][x][y] != 0 or (x, y) in occupied:
            continue
        when = danger[x][y]
        if when is None or when > state["tick"] + 2:
            return {"move": move, "bomb": False}
    return {"move": "stay", "bomb": False}

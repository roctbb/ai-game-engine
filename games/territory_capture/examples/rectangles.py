# ruff: noqa: F821
# capture_area(territory, me, trail) предоставляется движком.
from collections import deque

plan = []
DIRECTIONS = [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)]


def make_move(state):
    global plan
    me = state["me"]
    player = state["players"][me]
    x, y = player["x"], player["y"]
    board = state["territory"]
    if plan:
        return plan.pop(0)
    best, best_gain = [], 0
    for start in range(4):
        route = []
        for offset, length in ((0, 5), (1, 4), (2, 5), (3, 4)):
            route += [DIRECTIONS[(start + offset) % 4]] * length
        cx, cy, trail, steps = x, y, [], []
        for action, dx, dy in route:
            cx, cy = cx + dx, cy + dy
            if not (0 <= cx < state["width"] and 0 <= cy < state["height"]):
                break
            steps.append(action)
            if board[cx][cy] == me and trail:
                gain = len(capture_area(board, me, trail))
                if gain > best_gain:
                    best, best_gain = steps[:], gain
                break
            if board[cx][cy] != me:
                trail.append((cx, cy))
    if best:
        plan = best
        return plan.pop(0)
    # Move inside our own land toward a fresh border.
    queue = deque([(x, y, [])])
    seen = {(x, y)}
    while queue:
        cx, cy, route = queue.popleft()
        for action, dx, dy in DIRECTIONS:
            nx, ny = cx + dx, cy + dy
            if not (0 <= nx < state["width"] and 0 <= ny < state["height"]):
                continue
            if board[nx][ny] != me and route:
                return route[0]
            if board[nx][ny] == me and (nx, ny) not in seen:
                seen.add((nx, ny))
                queue.append((nx, ny, route + [action]))
    return "stay"

ORDER = ["up", "right", "down", "left"]
DELTAS = {
    "up": (0, -1),
    "right": (1, 0),
    "down": (0, 1),
    "left": (-1, 0),
}

direction = "right"


def can_go(state, action):
    maze = state["maze"]
    x = state["position"]["x"] + DELTAS[action][0]
    y = state["position"]["y"] + DELTAS[action][1]
    if y < 0 or y >= len(maze):
        return False
    if x < 0 or x >= len(maze[y]):
        return False
    return maze[y][x] != -1


def turn_right(action):
    return ORDER[(ORDER.index(action) + 1) % len(ORDER)]


def turn_left(action):
    return ORDER[(ORDER.index(action) - 1) % len(ORDER)]


def turn_back(action):
    return ORDER[(ORDER.index(action) + 2) % len(ORDER)]


def make_move(state):
    global direction

    for candidate in (
        turn_right(direction),
        direction,
        turn_left(direction),
        turn_back(direction),
    ):
        if can_go(state, candidate):
            direction = candidate
            return candidate

    return "right"

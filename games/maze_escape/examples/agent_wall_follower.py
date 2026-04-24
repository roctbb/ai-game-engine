ORDER = ["up", "right", "down", "left"]
DELTAS = {
    "up": (0, -1),
    "right": (1, 0),
    "down": (0, 1),
    "left": (-1, 0),
}

direction = "right"


def can_go(x, y, maze, action):
    next_x = x + DELTAS[action][0]
    next_y = y + DELTAS[action][1]
    if next_y < 0 or next_y >= len(maze):
        return False
    if next_x < 0 or next_x >= len(maze[next_y]):
        return False
    return maze[next_y][next_x] != -1


def turn_right(action):
    return ORDER[(ORDER.index(action) + 1) % len(ORDER)]


def turn_left(action):
    return ORDER[(ORDER.index(action) - 1) % len(ORDER)]


def turn_back(action):
    return ORDER[(ORDER.index(action) + 2) % len(ORDER)]


def make_move(x, y, maze):
    global direction

    for candidate in (
        turn_right(direction),
        direction,
        turn_left(direction),
        turn_back(direction),
    ):
        if can_go(x, y, maze, candidate):
            direction = candidate
            return candidate

    return "right"

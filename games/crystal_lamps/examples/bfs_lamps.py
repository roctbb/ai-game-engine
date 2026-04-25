MEMORY = {}
DIRECTIONS = [
    ("right", 1, 0),
    ("down", 0, 1),
    ("left", -1, 0),
    ("up", 0, -1),
]


def remember(board):
    for x, column in enumerate(board):
        for y, cell in enumerate(column):
            if cell != -9:
                MEMORY[(x, y)] = cell


def first_step_to(start, goals, width, height):
    queue = [start]
    came_from = {start: ("stay", start)}
    head = 0

    while head < len(queue):
        current = queue[head]
        head += 1
        if current in goals and current != start:
            while came_from[current][1] != start:
                current = came_from[current][1]
            return came_from[current][0]

        for action, dx, dy in DIRECTIONS:
            nx = current[0] + dx
            ny = current[1] + dy
            nxt = (nx, ny)
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                continue
            if MEMORY.get(nxt, -9) in (-9, -1) or nxt in came_from:
                continue
            came_from[nxt] = (action, current)
            queue.append(nxt)

    return None


def is_frontier(cell, width, height):
    if MEMORY.get(cell, -9) in (-9, -1):
        return False
    x, y = cell
    for _action, dx, dy in DIRECTIONS:
        nx = x + dx
        ny = y + dy
        if 0 <= nx < width and 0 <= ny < height and MEMORY.get((nx, ny), -9) == -9:
            return True
    return False


def make_move(x, y, board, lamps_lit):
    remember(board)
    width = len(board)
    height = len(board[0]) if width else 0
    start = (x, y)

    lamps = [cell for cell, value in MEMORY.items() if value == 1]
    exits = [cell for cell, value in MEMORY.items() if value == 2]

    targets = lamps if lamps or lamps_lit < 6 else exits
    action = first_step_to(start, targets, width, height)
    if action is not None:
        return action

    frontiers = [cell for cell in MEMORY if is_frontier(cell, width, height)]
    action = first_step_to(start, frontiers, width, height)
    if action is not None:
        return action

    for action, dx, dy in DIRECTIONS:
        nx = x + dx
        ny = y + dy
        if 0 <= nx < width and 0 <= ny < height and MEMORY.get((nx, ny), -1) != -1:
            return action
    return "stay"

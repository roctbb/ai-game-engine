DIRECTIONS = [
    ("right", 1, 0),
    ("down", 0, 1),
    ("left", -1, 0),
    ("up", 0, -1),
]


def make_move(x, y, board, has_flag):
    if has_flag:
        return step_to_value(x, y, board, 2)

    shot = shoot_carrier_if_visible(x, y, board)
    if shot:
        return shot

    if find_cells(board, 1):
        return step_to_value(x, y, board, 1)

    return step_next_to_carrier(x, y, board)


def shoot_carrier_if_visible(x, y, board):
    for action, dx, dy in DIRECTIONS:
        nx = x + dx
        ny = y + dy
        while 0 <= nx < len(board) and 0 <= ny < len(board[nx]):
            cell = board[nx][ny]
            if cell == -4:
                return "shoot_" + action
            if cell in (-3, -2, -1):
                break
            nx += dx
            ny += dy
    return None


def step_to_value(x, y, board, target_value):
    targets = find_cells(board, target_value)
    return bfs_step(x, y, board, targets)


def step_next_to_carrier(x, y, board):
    carriers = find_cells(board, -4)
    targets = []
    for cx, cy in carriers:
        for _action, dx, dy in DIRECTIONS:
            nx = cx + dx
            ny = cy + dy
            if is_open(nx, ny, board):
                targets.append((nx, ny))
    return bfs_step(x, y, board, targets)


def find_cells(board, value):
    cells = []
    for x in range(len(board)):
        for y in range(len(board[x])):
            if board[x][y] == value:
                cells.append((x, y))
    return cells


def bfs_step(x, y, board, targets):
    if not targets:
        return "stay"

    start = (x, y)
    target_set = set(targets)
    queue = [start]
    came_from = {start: ("stay", start)}
    head = 0
    found = None

    while head < len(queue):
        current = queue[head]
        head += 1
        if current in target_set and current != start:
            found = current
            break
        cx, cy = current
        for action, dx, dy in DIRECTIONS:
            nx = cx + dx
            ny = cy + dy
            nxt = (nx, ny)
            if not is_open(nx, ny, board) or nxt in came_from:
                continue
            came_from[nxt] = (action, current)
            queue.append(nxt)

    if found is None:
        return "stay"
    current = found
    while came_from[current][1] != start:
        current = came_from[current][1]
    return came_from[current][0]


def is_open(x, y, board):
    if x < 0 or x >= len(board) or y < 0 or y >= len(board[x]):
        return False
    return board[x][y] not in (-4, -3, -2, -1)

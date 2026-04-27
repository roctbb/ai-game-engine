CAPACITY = 3


def make_move(x, y, board, carrying, players=None, bases=None):
    throw = throw_if_aligned(x, y, board, carrying, players)
    if throw:
        return throw

    steal_target = opponent_base_with_apples(bases, carrying)
    if steal_target is not None:
        return step_to(x, y, board, steal_target, [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)])

    target = 2 if carrying >= CAPACITY or not any(cell == 1 for row in board for cell in row) else 1
    return step_to(x, y, board, target, [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)])


def throw_if_aligned(x, y, board, carrying, players=None):
    if carrying <= 0:
        return None
    for action, dx, dy in [("throw_right", 1, 0), ("throw_down", 0, 1), ("throw_left", -1, 0), ("throw_up", 0, -1)]:
        nx = x
        ny = y
        for _ in range(5):
            nx += dx
            ny += dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                break
            if board[nx][ny] in (-1, 3):
                break
            if board[nx][ny] == -2 and opponent_carrying_at(nx, ny, players) > 0:
                return action
    return None


def opponent_carrying_at(x, y, players):
    if not players:
        return 1
    for player in players:
        if player.get("is_me"):
            continue
        if player.get("x") == x and player.get("y") == y:
            return player.get("carrying", 0)
    return 0


def opponent_base_with_apples(bases, carrying):
    if not bases or carrying >= CAPACITY:
        return None
    best = None
    for base in bases:
        if base.get("is_me"):
            continue
        if base.get("apples", 0) <= 0:
            continue
        if best is None or base.get("apples", 0) > best.get("apples", 0):
            best = base
    if best is None:
        return None
    return (best["x"], best["y"])


def step_to(x, y, board, target, directions):
    start = (x, y)
    queue = [start]
    came_from = {start: ("stay", start)}
    head = 0
    found = None
    while head < len(queue):
        current = queue[head]
        head += 1
        cx, cy = current
        if (current == target or board[cx][cy] == target) and current != start:
            found = current
            break
        for action, dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            nxt = (nx, ny)
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            if board[nx][ny] in (-1, -2, 3) or nxt in came_from:
                continue
            came_from[nxt] = (action, current)
            queue.append(nxt)
    if found is None:
        return "stay"
    current = found
    while came_from[current][1] != start:
        current = came_from[current][1]
    return came_from[current][0]

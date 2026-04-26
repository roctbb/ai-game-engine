def make_move(x, y, board, carrying):
    throw = throw_if_aligned(x, y, board, carrying)
    if throw:
        return throw

    target = 2 if carrying >= 2 or not any(cell == 1 for row in board for cell in row) else 1
    return step_to(x, y, board, target, [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)])


def throw_if_aligned(x, y, board, carrying):
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
            if board[nx][ny] == -2:
                return action
    return None


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
        if board[cx][cy] == target and current != start:
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

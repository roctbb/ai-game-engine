MOVES = (
    (-1, -2),
    (1, -2),
    (2, -1),
    (2, 1),
    (1, 2),
    (-1, 2),
    (-2, 1),
    (-2, -1),
)


def make_move(x, y, board):
    target_value = 1
    has_coins = False
    for row in board:
        if 1 in row:
            has_coins = True
            break
    if not has_coins:
        target_value = 2

    queue = [((x, y), [])]
    seen = {(x, y)}
    head = 0
    while head < len(queue):
        (cx, cy), path = queue[head]
        head += 1
        if board[cx][cy] == target_value:
            return path[0] if path else (0, 0)
        for dx, dy in MOVES:
            nx, ny = cx + dx, cy + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            if board[nx][ny] == -1 or (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            queue.append(((nx, ny), path + [(dx, dy)]))
    return (0, 0)

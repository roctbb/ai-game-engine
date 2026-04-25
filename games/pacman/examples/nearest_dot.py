def make_move(x, y, board):
    directions = [
        ("right", 1, 0),
        ("down", 0, 1),
        ("left", -1, 0),
        ("up", 0, -1),
    ]

    ghosts = []
    targets = []
    for col_x, column in enumerate(board):
        for row_y, cell in enumerate(column):
            if cell == -2:
                ghosts.append((col_x, row_y))
            elif cell in (1, 2):
                targets.append((col_x, row_y))

    best_action = "stay"
    best_score = -100000
    for action, dx, dy in directions:
        nx = x + dx
        ny = y + dy
        if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
            continue
        if board[nx][ny] == -1:
            continue

        nearest_dot = 0
        if targets:
            nearest_dot = min(abs(nx - tx) + abs(ny - ty) for tx, ty in targets)
        nearest_ghost = 99
        if ghosts:
            nearest_ghost = min(abs(nx - gx) + abs(ny - gy) for gx, gy in ghosts)

        score = -nearest_dot + nearest_ghost * 3
        if board[nx][ny] == 1:
            score += 20
        elif board[nx][ny] == 2:
            score += 60
        if nearest_ghost <= 1:
            score -= 200

        if score > best_score:
            best_score = score
            best_action = action

    return best_action

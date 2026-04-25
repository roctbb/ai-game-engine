def make_move(x, y, board):
    return best_move(x, y, board, ["right", "down", "left", "up"])


def best_move(x, y, board, order):
    gems = []
    for col_x, column in enumerate(board):
        for row_y, cell in enumerate(column):
            if cell == 1:
                gems.append((col_x, row_y))
    best_action = "stay"
    best_score = -100000
    for action in order:
        dx, dy = {"right": (1, 0), "down": (0, 1), "left": (-1, 0), "up": (0, -1)}[action]
        nx = x + dx
        ny = y + dy
        if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
            continue
        if board[nx][ny] in (-1, -2):
            continue
        distance = min((abs(nx - gx) + abs(ny - gy) for gx, gy in gems), default=0)
        score = -distance + (50 if board[nx][ny] == 1 else 0)
        if score > best_score:
            best_score = score
            best_action = action
    return best_action

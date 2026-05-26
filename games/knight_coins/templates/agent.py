MOVES = [
    (-1, -2), (1, -2),
    (2, -1), (2, 1),
    (1, 2), (-1, 2),
    (-2, 1), (-2, -1),
]


def make_move(x, y, board):
    for dx, dy in MOVES:
        nx = x + dx
        ny = y + dy
        if 0 <= nx < len(board) and 0 <= ny < len(board[nx]) and board[nx][ny] != -1:
            return (dx, dy)
    return (0, 0)

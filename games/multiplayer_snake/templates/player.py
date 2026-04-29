DIRECTIONS = [
    ("right", 1, 0),
    ("down", 0, 1),
    ("left", -1, 0),
    ("up", 0, -1),
]


def make_move(x, y, board):
    for action, dx, dy in DIRECTIONS:
        nx = x + dx
        ny = y + dy
        if 0 <= nx < len(board) and 0 <= ny < len(board[nx]) and board[nx][ny] >= 0:
            return action
    return "right"

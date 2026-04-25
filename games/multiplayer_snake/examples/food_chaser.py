def make_move(x, y, board):
    food = None
    for col_x, column in enumerate(board):
        for row_y, cell in enumerate(column):
            if cell == 1:
                food = (col_x, row_y)
                break
        if food is not None:
            break

    moves = [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)]
    if food is not None:
        moves.sort(key=lambda move: abs(x + move[1] - food[0]) + abs(y + move[2] - food[1]))
    for action, dx, dy in moves:
        nx, ny = x + dx, y + dy
        if 0 <= nx < len(board) and 0 <= ny < len(board[nx]) and board[nx][ny] != -1:
            return action
    return "right"

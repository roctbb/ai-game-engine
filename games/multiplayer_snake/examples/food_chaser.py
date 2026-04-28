DIRECTIONS = [
    ("right", 1, 0),
    ("down", 0, 1),
    ("left", -1, 0),
    ("up", 0, -1),
]


def make_move(x, y, board):
    foods = []
    for col_x, column in enumerate(board):
        for row_y, cell in enumerate(column):
            if cell == 1:
                foods.append((col_x, row_y))

    best_action = None
    best_score = None
    for action, dx, dy in DIRECTIONS:
        nx, ny = x + dx, y + dy
        if not _is_open(nx, ny, board):
            continue

        free_neighbors = 0
        nearby_walls = 0
        for _, ndx, ndy in DIRECTIONS:
            tx, ty = nx + ndx, ny + ndy
            if _is_open(tx, ty, board):
                free_neighbors += 1
            else:
                nearby_walls += 1

        food_distance = min((abs(nx - fx) + abs(ny - fy) for fx, fy in foods), default=0)
        eats_now = 1 if board[nx][ny] == 1 else 0
        score = eats_now * 1000 - food_distance * 10 + free_neighbors * 6 - nearby_walls * 3
        if best_score is None or score > best_score:
            best_score = score
            best_action = action

    return best_action or "right"


def _is_open(x, y, board):
    return 0 <= x < len(board) and 0 <= y < len(board[x]) and board[x][y] != -1

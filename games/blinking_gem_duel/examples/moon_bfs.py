DELTAS = {"left": (-1, 0), "down": (0, 1), "right": (1, 0), "up": (0, -1), "stay": (0, 0)}


def flip(board):
    result = []
    for row in board:
        new_row = []
        for cell in row:
            if cell == 2:
                new_row.append(-2)
            elif cell == -2:
                new_row.append(2)
            else:
                new_row.append(cell)
        result.append(new_row)
    return result


def make_move(x, y, board, score=0, slot="moon"):
    queue = [((x, y), board, [])]
    seen = {((x, y), tuple(tuple(row) for row in board))}
    head = 0
    while head < len(queue):
        (cx, cy), current_board, path = queue[head]
        head += 1
        if current_board[cx][cy] == 1:
            return path[0] if path else "stay"
        next_board = flip(current_board)
        for action, (dx, dy) in DELTAS.items():
            nx, ny = cx + dx, cy + dy
            if ny < 0 or ny >= len(current_board) or nx < 0 or nx >= len(current_board[ny]):
                continue
            if current_board[nx][ny] in (-3, -2, -1):
                continue
            state = ((nx, ny), tuple(tuple(row) for row in next_board))
            if state in seen:
                continue
            seen.add(state)
            queue.append(((nx, ny), next_board, path + [action]))
    return "stay"

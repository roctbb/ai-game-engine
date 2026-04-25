DELTAS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}


def step(position, action, board):
    x, y = position
    distance = board[x][y] if board[x][y] in (2, 3) else 1
    dx, dy = DELTAS[action]
    nx, ny = x + dx * distance, y + dy * distance
    if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]) or board[nx][ny] == -1:
        return position
    return nx, ny


def make_move(x, y, board):
    queue = [((x, y), [])]
    seen = {(x, y)}
    head = 0
    while head < len(queue):
        current, path = queue[head]
        head += 1
        if board[current[0]][current[1]] == 1:
            return path[0] if path else "stay"
        for action in ("up", "right", "down", "left"):
            nxt = step(current, action, board)
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append((nxt, path + [action]))
    return "stay"

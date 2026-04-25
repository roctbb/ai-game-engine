DELTAS = {"up": (0, -1), "right": (1, 0), "down": (0, 1), "left": (-1, 0)}
CONVEYORS = {2: "up", 3: "right", 4: "down", 5: "left"}


def move(position, action):
    dx, dy = DELTAS[action]
    return position[0] + dx, position[1] + dy


def transition(position, action, board):
    x, y = move(position, action)
    if x < 0 or x >= len(board) or y < 0 or y >= len(board[x]) or board[x][y] in (-1, -2):
        return position
    current = (x, y)
    seen = {current}
    while board[current[0]][current[1]] in CONVEYORS:
        action = CONVEYORS[board[current[0]][current[1]]]
        nx, ny = move(current, action)
        if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]) or board[nx][ny] in (-1, -2):
            return current
        current = (nx, ny)
        if current in seen:
            return current
        seen.add(current)
    return current


def make_move(x, y, board, score=0, slot="orange"):
    queue = [((x, y), [])]
    seen = {(x, y)}
    head = 0
    while head < len(queue):
        current, path = queue[head]
        head += 1
        if board[current[0]][current[1]] == 1:
            return path[0] if path else "stay"
        for action in ("up", "right", "down", "left"):
            nxt = transition(current, action, board)
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append((nxt, path + [action]))
    return "stay"

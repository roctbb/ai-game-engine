DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


def slide(x, y, action, board):
    dx, dy = DELTAS[action]
    while True:
        nx, ny = x + dx, y + dy
        if board[nx][ny] in (-1, -2):
            return x, y
        x, y = nx, ny


def make_move(x, y, board, score=0, slot="sapphire"):
    queue = [((x, y), [])]
    seen = {(x, y)}
    head = 0
    while head < len(queue):
        (cx, cy), path = queue[head]
        head += 1
        if board[cx][cy] == 1:
            return path[0] if path else "stay"
        for action in ("up", "down", "left", "right"):
            nxt = slide(cx, cy, action, board)
            if nxt in seen:
                continue
            seen.add(nxt)
            queue.append((nxt, path + [action]))
    return "stay"

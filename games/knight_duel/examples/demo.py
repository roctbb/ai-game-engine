MOVES = {
    "up_left": (-1, -2),
    "up_right": (1, -2),
    "right_up": (2, -1),
    "right_down": (2, 1),
    "down_right": (1, 2),
    "down_left": (-1, 2),
    "left_down": (-2, 1),
    "left_up": (-2, -1),
}


def make_move(x, y, board, score=0, slot="white"):
    queue = [((x, y), [])]
    seen = {(x, y)}
    head = 0
    while head < len(queue):
        (cx, cy), path = queue[head]
        head += 1
        if board[cx][cy] == 1:
            return path[0] if path else "stay"
        for action, (dx, dy) in MOVES.items():
            nx, ny = cx + dx, cy + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            if board[nx][ny] in (-1, -2) or (nx, ny) in seen:
                continue
            seen.add((nx, ny))
            queue.append(((nx, ny), path + [action]))
    return "stay"

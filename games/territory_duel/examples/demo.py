def make_move(x, y, board):
    directions = [
        ("right", 1, 0),
        ("down", 0, 1),
        ("left", -1, 0),
        ("up", 0, -1),
    ]

    def first_step_to(values):
        start = (x, y)
        queue = [start]
        came_from = {start: ("stay", start)}
        head = 0
        found = None

        while head < len(queue):
            current = queue[head]
            head += 1
            cx, cy = current
            if board[cx][cy] in values and current != start:
                found = current
                break
            for action, dx, dy in directions:
                nx = cx + dx
                ny = cy + dy
                nxt = (nx, ny)
                if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                    continue
                if board[nx][ny] in (-1, -2) or nxt in came_from:
                    continue
                came_from[nxt] = (action, current)
                queue.append(nxt)

        if found is None:
            return "stay"
        current = found
        while came_from[current][1] != start:
            current = came_from[current][1]
        return came_from[current][0]

    move = first_step_to({0})
    if move != "stay":
        return move
    return first_step_to({2})

def make_move(x, y, board, oxygen):
    directions = [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)]
    width = len(board)
    height = len(board[0]) if width else 0
    oxygen_max = 28
    start = (x, y, oxygen)
    queue = [start]
    came_from = {start: ("stay", start)}
    head = 0
    found = None

    while head < len(queue):
        cx, cy, current_oxygen = queue[head]
        head += 1
        if board[cx][cy] == 2:
            found = (cx, cy, current_oxygen)
            break

        for action, dx, dy in directions:
            nx = cx + dx
            ny = cy + dy
            if nx < 0 or nx >= width or ny < 0 or ny >= height:
                continue
            if board[nx][ny] == -1:
                continue
            next_oxygen = current_oxygen - 1
            if next_oxygen <= 0 and board[nx][ny] != 2:
                continue
            if board[nx][ny] == 1:
                next_oxygen = oxygen_max
            state = (nx, ny, next_oxygen)
            if state in came_from:
                continue
            came_from[state] = (action, (cx, cy, current_oxygen))
            queue.append(state)

    if found is None:
        return "stay"
    current = found
    while came_from[current][1] != start:
        current = came_from[current][1]
    return came_from[current][0]

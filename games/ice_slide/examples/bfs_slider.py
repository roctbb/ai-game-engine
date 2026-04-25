def make_move(x, y, board):
    start = (x, y)
    goal = None
    for col_x, column in enumerate(board):
        for row_y, cell in enumerate(column):
            if cell == 1:
                goal = (col_x, row_y)
                break
        if goal is not None:
            break
    if goal is None:
        return "right"

    directions = [
        ("right", 1, 0),
        ("down", 0, 1),
        ("left", -1, 0),
        ("up", 0, -1),
    ]

    def slide(cell, dx, dy):
        cx, cy = cell
        while True:
            nx = cx + dx
            ny = cy + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                return (cx, cy)
            if board[nx][ny] == -1:
                return (cx, cy)
            cx, cy = nx, ny
            if (cx, cy) == goal:
                return (cx, cy)

    queue = [start]
    came_from = {start: ("", start)}
    head = 0
    while head < len(queue):
        current = queue[head]
        head += 1
        if current == goal:
            break
        for action, dx, dy in directions:
            nxt = slide(current, dx, dy)
            if nxt == current or nxt in came_from:
                continue
            came_from[nxt] = (action, current)
            queue.append(nxt)

    if goal not in came_from:
        return "right"
    current = goal
    while came_from[current][1] != start:
        current = came_from[current][1]
    return came_from[current][0]

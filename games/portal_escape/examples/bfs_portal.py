def make_move(x, y, board):
    directions = [
        ("right", 1, 0),
        ("down", 0, 1),
        ("left", -1, 0),
        ("up", 0, -1),
    ]
    portals_by_id = {}
    exit_cell = None
    for col_x, column in enumerate(board):
        for row_y, cell in enumerate(column):
            if cell == 1:
                exit_cell = (col_x, row_y)
            elif cell > 1:
                portals_by_id.setdefault(cell, []).append((col_x, row_y))

    portal_targets = {}
    for cells in portals_by_id.values():
        if len(cells) == 2:
            portal_targets[cells[0]] = cells[1]
            portal_targets[cells[1]] = cells[0]

    def after_portal(cell):
        return portal_targets.get(cell, cell)

    if exit_cell is None:
        return "stay"

    start = (x, y)
    queue = [start]
    came_from = {start: ("stay", start)}
    head = 0
    found = None

    while head < len(queue):
        current = queue[head]
        head += 1
        if current == exit_cell:
            found = current
            break
        for action, dx, dy in directions:
            nx = current[0] + dx
            ny = current[1] + dy
            step_cell = (nx, ny)
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            if board[nx][ny] == -1:
                continue
            nxt = after_portal(step_cell)
            if nxt in came_from:
                continue
            came_from[nxt] = (action, current)
            queue.append(nxt)

    if found is None:
        return "stay"
    current = found
    while came_from[current][1] != start:
        current = came_from[current][1]
    return came_from[current][0]

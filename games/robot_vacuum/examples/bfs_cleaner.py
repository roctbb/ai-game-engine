def make_move(x, y, board, battery):
    directions = [
        ("right", 1, 0),
        ("down", 0, 1),
        ("left", -1, 0),
        ("up", 0, -1),
    ]

    def first_step_to(targets):
        start = (x, y)
        queue = [start]
        came_from = {start: ("", start)}
        head = 0
        found = None

        while head < len(queue):
            current = queue[head]
            head += 1
            if current in targets:
                found = current
                break
            for action, dx, dy in directions:
                nx = current[0] + dx
                ny = current[1] + dy
                nxt = (nx, ny)
                if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                    continue
                if board[nx][ny] == -1 or nxt in came_from:
                    continue
                came_from[nxt] = (action, current)
                queue.append(nxt)

        if found is None:
            return ("stay", 999)
        distance = 0
        current = found
        while came_from[current][1] != start:
            current = came_from[current][1]
            distance += 1
        return (came_from[current][0] if found != start else "stay", distance + 1)

    charger = (1, 1)
    charger_action, charger_distance = first_step_to([charger])
    if battery <= charger_distance + 4:
        return charger_action

    targets = []
    for col_x, column in enumerate(board):
        for row_y, cell in enumerate(column):
            if cell == 1:
                targets.append((col_x, row_y))
    if not targets:
        return charger_action

    action, _distance = first_step_to(targets)
    return action

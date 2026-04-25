def make_move(x, y, board, fuel, ore_mined):
    directions = [
        ("right", 1, 0),
        ("down", 0, 1),
        ("left", -1, 0),
        ("up", 0, -1),
    ]

    def first_step_to(target_values):
        start = (x, y)
        if board[x][y] in target_values:
            return ("stay", 0)
        queue = [start]
        came_from = {start: ("stay", start)}
        head = 0
        found = None

        while head < len(queue):
            current = queue[head]
            head += 1
            cx, cy = current
            if board[cx][cy] in target_values and current != start:
                found = current
                break
            for action, dx, dy in directions:
                nx = cx + dx
                ny = cy + dy
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
        return (came_from[current][0], distance + 1)

    base_action, base_distance = first_step_to({2})
    has_ore = any(cell == 1 for row in board for cell in row)
    if not has_ore or fuel <= base_distance + 6:
        return base_action

    ore_action, _ore_distance = first_step_to({1})
    return ore_action

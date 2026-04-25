def make_move(x, y, board, keys):
    directions = [("right", 1, 0), ("down", 0, 1), ("left", -1, 0), ("up", 0, -1)]
    start = (x, y, keys)
    queue = [start]
    came_from = {start: ("stay", start)}
    head = 0
    found = None

    while head < len(queue):
        cx, cy, count = queue[head]
        head += 1
        if board[cx][cy] == 2:
            found = (cx, cy, count)
            break
        for action, dx, dy in directions:
            nx, ny = cx + dx, cy + dy
            if nx < 0 or nx >= len(board) or ny < 0 or ny >= len(board[nx]):
                continue
            cell = board[nx][ny]
            if cell == -1:
                continue
            new_count = count
            if cell == -2:
                if new_count <= 0:
                    continue
                new_count -= 1
            elif cell == 1:
                new_count += 1
            state = (nx, ny, new_count)
            if state in came_from:
                continue
            came_from[state] = (action, (cx, cy, count))
            queue.append(state)

    if found is None:
        return "stay"
    current = found
    while came_from[current][1] != start:
        current = came_from[current][1]
    return came_from[current][0]

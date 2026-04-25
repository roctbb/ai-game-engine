def make_move(x, y, board):
    food = None
    for col_x, column in enumerate(board):
        for row_y, cell in enumerate(column):
            if cell == 1:
                food = (col_x, row_y)
                break
        if food is not None:
            break

    directions = [
        ("right", 1, 0),
        ("down", 0, 1),
        ("left", -1, 0),
        ("up", 0, -1),
    ]
    if food is None:
        for action, dx, dy in directions:
            nx = x + dx
            ny = y + dy
            if 0 <= nx < len(board) and 0 <= ny < len(board[nx]) and board[nx][ny] != -1:
                return action
        return "right"

    start = (x, y)
    queue = [start]
    came_from = {start: ("right", start)}
    head = 0

    while head < len(queue):
        current = queue[head]
        head += 1
        if current == food:
            while came_from[current][1] != start:
                current = came_from[current][1]
            return came_from[current][0]
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

    for action, dx, dy in directions:
        nx = x + dx
        ny = y + dy
        if 0 <= nx < len(board) and 0 <= ny < len(board[nx]) and board[nx][ny] != -1:
            return action
    return "right"

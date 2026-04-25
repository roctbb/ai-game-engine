from collections import deque


def make_choice(start_x, start_y, field):
    width = len(field)
    height = len(field[0]) if width else 0

    for action, dx, dy in (
        ("fire_left", -1, 0),
        ("fire_right", 1, 0),
        ("fire_up", 0, -1),
        ("fire_down", 0, 1),
    ):
        x, y = start_x + dx, start_y + dy
        while 0 <= x < width and 0 <= y < height:
            if field[x][y] in (-1, 1):
                break
            if isinstance(field[x][y], dict):
                return action
            x += dx
            y += dy

    queue = deque([(start_x, start_y, [])])
    visited = {(start_x, start_y)}
    moves = (
        ("go_right", 1, 0),
        ("go_down", 0, 1),
        ("go_left", -1, 0),
        ("go_up", 0, -1),
    )
    while queue:
        x, y, path = queue.popleft()
        if field[x][y] == 1 and path:
            return path[0]
        for action, dx, dy in moves:
            nx, ny = x + dx, y + dy
            if nx < 0 or ny < 0 or nx >= width or ny >= height or (nx, ny) in visited:
                continue
            cell = field[nx][ny]
            if cell == -1 or isinstance(cell, dict):
                continue
            visited.add((nx, ny))
            queue.append((nx, ny, path + [action]))

    return "shield"

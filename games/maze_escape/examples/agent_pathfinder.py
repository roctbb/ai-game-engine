def make_move(x, y, maze):
    start = (x, y)
    width = len(maze)
    height = len(maze[0]) if width else 0
    goal = None

    for col_x, column in enumerate(maze):
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
    queue = [start]
    head = 0
    came_from = {start: ("", start)}

    while head < len(queue):
        current = queue[head]
        head += 1
        if current == goal:
            break

        for action, dx, dy in directions:
            next_cell = (current[0] + dx, current[1] + dy)
            if next_cell[0] < 0 or next_cell[1] < 0:
                continue
            if next_cell[0] >= width or next_cell[1] >= height:
                continue
            if maze[next_cell[0]][next_cell[1]] == -1:
                continue
            if next_cell in came_from:
                continue
            came_from[next_cell] = (action, current)
            queue.append(next_cell)

    if goal not in came_from:
        return "right"

    current = goal
    while came_from[current][1] != start:
        current = came_from[current][1]
    return came_from[current][0]

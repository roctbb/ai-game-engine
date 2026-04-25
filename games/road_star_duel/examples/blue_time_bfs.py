DELTAS = {"left": (-1, 0), "up": (0, -1), "right": (1, 0), "down": (0, 1), "stay": (0, 0)}


def advance(cars, width):
    result = set()
    for x, y in cars:
        dx = 1 if y % 2 == 1 else -1
        result.add(((x + dx) % width, y))
    return result


def make_move(x, y, board, score=0, slot="blue"):
    width = len(board)
    height = len(board[0]) if width else 0
    cars = set()
    stars = set()
    blocked = set()
    for xx, column in enumerate(board):
        for yy, cell in enumerate(column):
            if cell == -1:
                cars.add((xx, yy))
            elif cell == 1:
                stars.add((xx, yy))
            elif cell == -2:
                blocked.add((xx, yy))
    if not stars:
        return "stay"

    queue = [((x, y), frozenset(cars), [])]
    seen = {((x, y), frozenset(cars))}
    head = 0
    while head < len(queue):
        position, car_state, path = queue[head]
        head += 1
        if position in stars:
            return path[0] if path else "stay"
        current_cars = set(car_state)
        next_cars = advance(current_cars, width)
        for action, (dx, dy) in DELTAS.items():
            nx, ny = position[0] + dx, position[1] + dy
            if ny < 0 or ny >= height or nx < 0 or nx >= width:
                continue
            if (nx, ny) in current_cars or (nx, ny) in next_cars or (nx, ny) in blocked:
                continue
            state = ((nx, ny), frozenset(next_cars))
            if state in seen:
                continue
            seen.add(state)
            queue.append(((nx, ny), frozenset(next_cars), path + [action]))
    return "stay"

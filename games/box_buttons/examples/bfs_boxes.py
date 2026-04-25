DELTAS = {
    "up": (0, -1),
    "down": (0, 1),
    "left": (-1, 0),
    "right": (1, 0),
}


def make_move(x, y, board):
    boxes = set()
    targets = set()
    walls = set()
    for xx, column in enumerate(board):
        for yy, cell in enumerate(column):
            if cell == -1:
                walls.add((xx, yy))
            elif cell == 1:
                boxes.add((xx, yy))
            elif cell == 2:
                targets.add((xx, yy))
            elif cell == 3:
                boxes.add((xx, yy))
                targets.add((xx, yy))

    start = ((x, y), tuple(sorted(boxes)))
    queue = [(start, [])]
    seen = {start}
    head = 0
    while head < len(queue):
        (player, box_tuple), path = queue[head]
        head += 1
        current_boxes = set(box_tuple)
        if current_boxes and current_boxes <= targets:
            return path[0] if path else "stay"
        for action, (dx, dy) in DELTAS.items():
            nx, ny = player[0] + dx, player[1] + dy
            if (nx, ny) in walls:
                continue
            next_boxes = set(current_boxes)
            if (nx, ny) in current_boxes:
                bx, by = nx + dx, ny + dy
                if (bx, by) in walls or (bx, by) in current_boxes:
                    continue
                next_boxes.remove((nx, ny))
                next_boxes.add((bx, by))
            state = ((nx, ny), tuple(sorted(next_boxes)))
            if state in seen:
                continue
            seen.add(state)
            queue.append((state, path + [action]))
    return "stay"

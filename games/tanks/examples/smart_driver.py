def make_choice(x, y, map_state):
    """A safer starter bot for the old large tanks arena."""
    width = len(map_state)
    height = len(map_state[0]) if width else 0

    def inside(cx, cy):
        return 0 <= cx < width and 0 <= cy < height

    def cell(cx, cy):
        return map_state[cx][cy] if inside(cx, cy) else {"player": None, "items": [], "object": {"type": "Wall"}}

    def blocked(cx, cy):
        here = cell(cx, cy)
        if here.get("player"):
            return True
        obj = here.get("object")
        if obj and not obj.get("is_transparent", False):
            return True
        return False

    my_team = cell(x, y)["player"]["properties"].get("team")

    # First priority: if an enemy player, tower, wall or ancient is in a clear line, shoot.
    for action, dx, dy in [
        ("fire_left", -1, 0),
        ("fire_right", 1, 0),
        ("fire_up", 0, -1),
        ("fire_down", 0, 1),
    ]:
        cx = x + dx
        cy = y + dy
        while inside(cx, cy):
            here = cell(cx, cy)
            player = here.get("player")
            obj = here.get("object")
            if player:
                return action if player["properties"].get("team") != my_team else "fire_right"
            if obj and not obj.get("is_flat", False):
                return action
            cx += dx
            cy += dy

    # Second priority: collect the nearest visible item.
    target = None
    best = 10**9
    for cx in range(width):
        for cy in range(height):
            if blocked(cx, cy):
                continue
            if cell(cx, cy).get("items"):
                dist = abs(cx - x) + abs(cy - y)
                if dist < best:
                    best = dist
                    target = (cx, cy)

    moves = [
        ("go_left", x - 1, y),
        ("go_right", x + 1, y),
        ("go_up", x, y - 1),
        ("go_down", x, y + 1),
    ]

    if target:
        tx, ty = target
        moves.sort(key=lambda move: abs(move[1] - tx) + abs(move[2] - ty))

    for action, nx, ny in moves:
        if inside(nx, ny) and not blocked(nx, ny):
            return action

    return "fire_right"

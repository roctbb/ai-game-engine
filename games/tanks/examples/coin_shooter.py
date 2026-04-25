def make_choice(x, y, map_state):
    """Simple legacy tanks bot: move to coins, shoot visible enemies."""
    width = len(map_state)
    height = len(map_state[0]) if width else 0

    def cell(cx, cy):
        if 0 <= cx < width and 0 <= cy < height:
            return map_state[cx][cy]
        return {"player": None, "items": [], "object": {"type": "Wall"}}

    # Shoot the first visible non-friendly object or player in a straight line.
    rays = [
        ("fire_left", -1, 0),
        ("fire_right", 1, 0),
        ("fire_up", 0, -1),
        ("fire_down", 0, 1),
    ]
    my_team = cell(x, y)["player"]["properties"].get("team")
    for action, dx, dy in rays:
        cx = x + dx
        cy = y + dy
        while 0 <= cx < width and 0 <= cy < height:
            here = cell(cx, cy)
            player = here.get("player")
            obj = here.get("object")
            if player:
                if player["properties"].get("team") != my_team:
                    return action
                break
            if obj and not obj.get("is_flat", False):
                return action
            cx += dx
            cy += dy

    # Move toward the nearest coin.
    target = None
    best_dist = 10**9
    for cx in range(width):
        for cy in range(height):
            items = cell(cx, cy).get("items") or []
            if any(item.get("type") == "Coin" for item in items):
                dist = abs(cx - x) + abs(cy - y)
                if dist < best_dist:
                    best_dist = dist
                    target = (cx, cy)

    if target is None:
        return "fire_right"

    tx, ty = target
    if abs(tx - x) >= abs(ty - y) and tx != x:
        return "go_right" if tx > x else "go_left"
    if ty != y:
        return "go_down" if ty > y else "go_up"
    return "fire_right"

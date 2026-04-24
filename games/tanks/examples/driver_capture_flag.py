def make_choice(x, y, map_state):
    flag = map_state["flag"]
    bases = map_state["bases"]
    enemy = map_state["enemy"]

    if flag["carrier"] == "player":
        target = bases["player"]
    else:
        target = flag

    dx = target["x"] - x
    dy = target["y"] - y

    if enemy["x"] == x and enemy["y"] == y:
        return "up" if y > 0 else "down"

    if enemy["y"] == y and abs(enemy["x"] - x) <= 1 and dy != 0:
        return "down" if dy > 0 else "up"

    if abs(dx) >= abs(dy) and dx != 0:
        return "right" if dx > 0 else "left"
    if dy != 0:
        return "down" if dy > 0 else "up"
    return "stay"

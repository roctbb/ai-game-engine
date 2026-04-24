def make_choice(x, y, map_state):
    flag = map_state["flag"]
    bases = map_state["bases"]
    enemy = map_state["enemy"]
    w = map_state["map"]["width"]
    h = map_state["map"]["height"]

    carrying = flag["carrier"] == "player"
    target = bases["player"] if carrying else flag
    tx, ty = target["x"], target["y"]
    ex, ey = enemy["x"], enemy["y"]

    moves = {
        "up":    (x, y - 1),
        "down":  (x, y + 1),
        "left":  (x - 1, y),
        "right": (x + 1, y),
    }

    # Отфильтровываем ходы за пределы карты
    valid = {}
    for m, (nx, ny) in moves.items():
        if 0 <= nx < w and 0 <= ny < h:
            valid[m] = (nx, ny)

    if not valid:
        return "stay"

    def mdist(ax, ay, bx, by):
        return abs(ax - bx) + abs(ay - by)

    cur_dist = mdist(x, y, tx, ty)

    # Ходы, приближающие к цели
    closer = {m: p for m, p in valid.items() if mdist(p[0], p[1], tx, ty) < cur_dist}
    # Ходы, не ухудшающие расстояние
    same_or_closer = {m: p for m, p in valid.items() if mdist(p[0], p[1], tx, ty) <= cur_dist}

    def pick_safest(candidates):
        """Из кандидатов выбираем ход, максимально далёкий от врага."""
        best_m = None
        best_edist = -1
        for m, (nx, ny) in candidates.items():
            ed = mdist(nx, ny, ex, ey)
            if ed > best_edist:
                best_edist = ed
                best_m = m
        return best_m

    if carrying:
        # Приоритет: приближаемся к базе, избегая столкновения с врагом
        safe_closer = {m: p for m, p in closer.items() if p != (ex, ey)}
        if safe_closer:
            return pick_safest(safe_closer)
        # Если все приближающие ходы ведут на врага — обходим
        safe_same = {m: p for m, p in same_or_closer.items() if p != (ex, ey)}
        if safe_same:
            return pick_safest(safe_same)
        # Все ходы ведут на врага — всё равно идём к цели
        if closer:
            return pick_safest(closer)
        return pick_safest(valid)
    else:
        # Без флага — просто идём к нему кратчайшим путём
        if closer:
            return pick_safest(closer)
        return pick_safest(valid) or "stay"

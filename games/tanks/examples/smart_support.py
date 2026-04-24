def make_support(state):
    cd = state["support"]["boost_cooldown"]
    if cd != 0:
        return "none"

    own = state["self"]
    enemy = state["enemy"]
    flag = state["flag"]
    bases = state["bases"]

    if flag["carrier"] == "player":
        target = bases["player"]
    else:
        target = flag

    dist_target = abs(target["x"] - own["x"]) + abs(target["y"] - own["y"])
    dist_enemy = abs(enemy["x"] - own["x"]) + abs(enemy["y"] - own["y"])

    # Не бустим если в 1 шаге от цели — перескочим
    if dist_target <= 1:
        return "none"

    # Буст когда несём флаг и враг близко
    if flag["carrier"] == "player" and dist_enemy <= 3:
        return "boost"

    # Буст когда далеко от цели
    if dist_target >= 3:
        return "boost"

    return "none"

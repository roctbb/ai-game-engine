def make_support(state):
    if state["support"]["boost_cooldown"] != 0:
        return "none"

    own = state["self"]
    flag = state["flag"]
    bases = state["bases"]

    if flag["carrier"] == "player":
        target = bases["player"]
    else:
        target = flag

    distance = abs(target["x"] - own["x"]) + abs(target["y"] - own["y"])
    if distance >= 2:
        return "boost"
    return "none"

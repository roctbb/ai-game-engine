def make_move(state):
    me = state["me"]
    player = state["players"][me]
    money, towers = player["money"], player["towers"]
    occupied = [t["pad"] for t in towers]
    build_order = [(3, "arrow"), (4, "blast"), (5, "slow"), (6, "arrow"), (2, "blast")]
    for pad, kind in build_order[:2]:
        if pad not in occupied:
            if money >= state["tower_types"][kind]["cost"]:
                return {"action": "build", "pad": pad, "tower": kind}
            return None
    if player["income_upgrades"] < 4:
        if money >= 40 + player["income_upgrades"] * 20:
            return {"action": "income"}
        return None
    for pad, kind in build_order[2:]:
        if pad not in occupied and money >= state["tower_types"][kind]["cost"]:
            return {"action": "build", "pad": pad, "tower": kind}
    for tower in towers:
        cost = state["tower_types"][tower["type"]]["cost"] * tower["level"]
        if tower["level"] < 3 and money >= cost:
            return {"action": "upgrade", "pad": tower["pad"]}
    if money >= 42:
        return {"action": "send", "unit": "armored" if state["tick"] % 3 else "swarm"}
    return None

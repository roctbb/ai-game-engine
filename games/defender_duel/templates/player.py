def make_move(state):
    player = state["players"][state["me"]]
    occupied = [tower["pad"] for tower in player["towers"]]
    for pad in (3, 4, 5):
        if pad not in occupied and player["money"] >= 30:
            return {"action": "build", "pad": pad, "tower": "arrow"}
    if player["money"] >= 16:
        return {"action": "send", "unit": "scout"}
    return None

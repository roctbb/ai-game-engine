def make_move(state):
    if state["arrows"] <= 0:
        return "reload"
    if state["enemy_aimed"] and state["hp"] < 60:
        return "shield"
    if state["enemy_hp"] <= 35:
        return "shoot"
    return "aim"

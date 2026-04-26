def choose_action(state):
    if state["battery"] <= 2 and state["on_charger"]:
        return "charge"
    elif state["battery"] <= state["distance_to_charger"] + 1:
        return "return_to_charger"
    elif state["dirty"] and state["battery"] >= 2:
        return "clean"
    elif state["front_clear"] and state["battery"] >= 1:
        return "move"
    return "wait"

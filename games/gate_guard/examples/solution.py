def choose_action(gate):
    if gate["color"] == "red":
        return "attack"
    elif gate["color"] == "blue":
        if gate["has_key"]:
            return "use_key"
        return "wait"
    elif gate["trap"]:
        return "disarm"
    return "open"

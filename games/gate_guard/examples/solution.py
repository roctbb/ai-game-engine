def choose_action(gate):
    if gate["enemy_distance"] <= 1:
        return "attack"
    elif gate["trap"] and gate["trap_damage"] < gate["hp"]:
        return "disarm"
    elif gate["locked"] and gate["has_key"]:
        return "use_key"
    elif gate["locked"]:
        return "wait"
    return "open"

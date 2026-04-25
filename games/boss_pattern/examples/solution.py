def choose_action(turn, boss_state):
    if boss_state == "heavy_attack":
        return "shield"
    elif boss_state == "summon":
        return "area_spell"
    return "attack"

# turn - номер хода, boss_state - состояние босса.
# boss_state: prepares, heavy_attack, rest, summon.
# Верните shield, attack, area_spell или heal.

def choose_action(turn, boss_state):
    if boss_state == "heavy_attack":
        return "shield"
    elif boss_state == "summon":
        return "area_spell"
    # TODO: каждый 5-й ход маг должен лечиться, если нет более срочной угрозы.
    else:
        return "attack"

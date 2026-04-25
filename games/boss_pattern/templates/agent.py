# turn - номер хода, boss_state - состояние босса.
# boss_state: prepares, heavy_attack, rest, summon.
# Верните shield, attack или area_spell.

def choose_action(turn, boss_state):
    if boss_state == "heavy_attack":
        return "shield"
    elif boss_state == "summon":
        return "area_spell"
    else:
        return "attack"

# Дуэль лучников. state содержит hp, enemy_hp, arrows, enemy_aimed, turn.
# Верните aim, shoot, shield или reload.

def make_move(state):
    if state["arrows"] <= 0:
        return "reload"
    if state["enemy_aimed"] and state["hp"] < 60:
        return "shield"
    if state["enemy_hp"] <= 25:
        return "shoot"
    # После aim следующий shoot станет сильнее, но своего aimed в state нет.
    # Поэтому простая стратегия начинает с прицеливания.
    return "aim"

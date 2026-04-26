def choose_action(enemy, arrows, hp):
    threat = enemy["damage"] - enemy["distance"] * 2
    if arrows <= 0:
        return "reload"
    elif enemy["is_aiming"] and threat >= 20 and hp < 50:
        return "shield"
    elif enemy["distance"] <= 3 and enemy["armor"] <= 1:
        return "shoot"
    elif enemy["hp"] <= 25 and enemy["armor"] <= 1:
        return "shoot"
    return "wait"

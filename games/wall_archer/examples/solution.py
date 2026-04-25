def choose_action(enemy, arrows, hp):
    if arrows <= 0:
        return "reload"
    elif enemy["distance"] <= 3:
        return "shoot"
    elif enemy["is_aiming"] and hp < 50:
        return "shield"
    return "wait"

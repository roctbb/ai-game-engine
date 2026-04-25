def choose_target(enemies):
    target = enemies[0]
    for enemy in enemies:
        if enemy["hp"] < target["hp"]:
            target = enemy
    return target["id"]

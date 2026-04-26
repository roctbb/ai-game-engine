def choose_target(enemies):
    target = enemies[0]
    for enemy in enemies:
        if enemy["hp"] < target["hp"]:
            target = enemy
        elif enemy["hp"] == target["hp"] and enemy["distance"] < target["distance"]:
            target = enemy
        elif (
            enemy["hp"] == target["hp"]
            and enemy["distance"] == target["distance"]
            and enemy["reward"] > target["reward"]
        ):
            target = enemy
    return target["id"]

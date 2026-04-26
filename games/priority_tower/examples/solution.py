def choose_target(enemies):
    best = enemies[0]
    best_score = best["danger"] * 3 + best["speed"] * 2 - best["distance"] + best["hp"] // 10
    for enemy in enemies:
        score = enemy["danger"] * 3 + enemy["speed"] * 2 - enemy["distance"] + enemy["hp"] // 10
        if score > best_score:
            best = enemy
            best_score = score
        elif score == best_score and enemy["distance"] < best["distance"]:
            best = enemy
            best_score = score
        elif score == best_score and enemy["distance"] == best["distance"] and enemy["hp"] > best["hp"]:
            best = enemy
            best_score = score
    return best["id"]

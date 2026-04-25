def choose_target(enemies):
    best = enemies[0]
    best_score = best["danger"] * 3 + best["speed"] * 2 - best["distance"]
    for enemy in enemies:
        score = enemy["danger"] * 3 + enemy["speed"] * 2 - enemy["distance"]
        if score > best_score:
            best = enemy
            best_score = score
    return best["id"]

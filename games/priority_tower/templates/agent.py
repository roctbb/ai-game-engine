def choose_target(enemies):
    # Счет опасности: danger * 3 + speed * 2 - distance + hp // 10.
    # При равном счете выбираем ближайшего, затем с большим hp.
    best = enemies[0]
    best_score = best["danger"] * 3 + best["speed"] * 2 - best["distance"] + best["hp"] // 10

    for enemy in enemies:
        score = enemy["danger"] * 3 + enemy["speed"] * 2 - enemy["distance"] + enemy["hp"] // 10
        # TODO: обновите цель, если score больше.
        # TODO: при равном score выберите ближайшего врага.
        if False:
            best = enemy
            best_score = score

    return best["id"]

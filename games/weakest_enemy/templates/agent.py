def choose_target(enemies):
    # enemies - список словарей: {"id": "...", "hp": число, "distance": число}
    # Нужно вернуть id врага с минимальным hp.
    target = enemies[0]

    for enemy in enemies:
        # TODO: если нашли врага слабее текущей цели, запомните его.
        if enemy["hp"] < target["hp"]:
            target = enemy

    return target["id"]

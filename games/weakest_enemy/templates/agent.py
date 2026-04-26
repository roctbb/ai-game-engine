def choose_target(enemies):
    # enemies - список словарей:
    # {"id": "...", "hp": число, "distance": число, "reward": число}
    # Правило выбора:
    # 1) меньше hp,
    # 2) если hp равны - меньше distance,
    # 3) если снова равны - больше reward.
    target = enemies[0]

    for enemy in enemies:
        # TODO: добавьте проверки distance и reward при равном hp.
        if enemy["hp"] < target["hp"]:
            target = enemy

    return target["id"]

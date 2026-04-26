def count_plants(field):
    # field[x][y]: сначала столбец x, потом строка y.
    # 0 - пусто, 1 - морковь, 2 - пшеница, 3 - кукуруза.
    # Нужно вернуть сумму очков урожая, а не просто количество клеток.
    total = 0

    for x in range(len(field)):
        for y in range(len(field[x])):
            if field[x][y] > 0:
                # TODO: добавьте к total значение клетки field[x][y].
                # Сейчас шаблон считает только количество растений.
                total += 1

    return total

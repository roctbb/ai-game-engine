def count_plants(field):
    # field[x][y]: сначала столбец x, потом строка y.
    # Растение обозначено числом 1, пустая клетка - числом 0.
    total = 0

    for x in range(len(field)):
        for y in range(len(field[x])):
            if field[x][y] == 1:
                total += 1

    return total

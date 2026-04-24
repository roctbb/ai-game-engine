def make_choice(field, role):
    available_positions = []
    for i in range(len(field)):
        for j in range(len(field[0])):
            if field[i][j] == 0:
                available_positions.append((i, j))

    # Детерминированный pseudo-random без import: пользовательский рантайм
    # специально не открывает внешние модули для демо-кодов.
    seed = len(available_positions) * 7 + role * 3
    return available_positions[seed % len(available_positions)]

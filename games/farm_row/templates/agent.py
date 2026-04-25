def solve(row):
    # row - список клеток грядки.
    # 1 означает сухое растение: нужна команда "water".
    # 0 означает пусто или уже влажно: нужна команда "skip".
    #
    # Верните список команд той же длины, что и row.
    commands = []
    for cell in row:
        if cell == 1:
            # Сейчас растение отмечаем как пропуск.
            # Замените эту строку на commands.append("water").
            commands.append("skip")
        else:
            commands.append("skip")
    return commands

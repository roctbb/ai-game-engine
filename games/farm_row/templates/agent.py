def solve(row):
    # row - список клеток грядки.
    # Каждая клетка - словарь {"plant": True/False, "moisture": число}.
    # Поливать надо только растения с влажностью меньше 3.
    #
    # Верните список команд той же длины, что и row.
    commands = []
    for cell in row:
        if cell["plant"]:
            # TODO: проверьте влажность cell["moisture"].
            commands.append("skip")
        else:
            commands.append("skip")
    return commands

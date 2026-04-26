def solve(corridor):
    # corridor - клетки коридора слева направо.
    # "." - пусто, "C" - кристалл, "B" - большой кристалл,
    # "X" - проклятый кристалл, "#" - стена.
    #
    # Идите до первой стены. C и B надо собрать, X надо пропустить.
    commands = []
    index = 0
    while index < len(corridor):
        cell = corridor[index]
        if cell == "#":
            break
        if cell == "C":
            # TODO: сначала добавьте "collect".
            commands.append("move")
        else:
            commands.append("move")
        index += 1
    return commands

def solve(corridor):
    # corridor - клетки коридора слева направо.
    # "." - пусто, "C" - кристалл, "#" - стена.
    #
    # Идите до первой стены. Для кристалла сначала "collect", потом "move".
    commands = []
    index = 0
    while index < len(corridor):
        cell = corridor[index]
        if cell == "#":
            break
        if cell == "C":
            # Перед движением с кристалла нужна команда "collect".
            # Добавьте ее здесь.
            commands.append("move")
        else:
            commands.append("move")
        index += 1
    return commands

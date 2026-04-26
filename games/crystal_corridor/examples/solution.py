def solve(corridor):
    commands = []
    index = 0
    while index < len(corridor) and corridor[index] != "#":
        if corridor[index] in ("C", "B"):
            commands.append("collect")
        commands.append("move")
        index += 1
    return commands

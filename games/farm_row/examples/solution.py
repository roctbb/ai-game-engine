def solve(row):
    commands = []
    for cell in row:
        if cell["plant"] and cell["moisture"] < 3:
            commands.append("water")
        else:
            commands.append("skip")
    return commands

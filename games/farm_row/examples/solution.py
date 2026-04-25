def solve(row):
    commands = []
    for cell in row:
        if cell == 1:
            commands.append("water")
        else:
            commands.append("skip")
    return commands

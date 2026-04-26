def solve(ores, capacity):
    total_weight = 0
    commands = []
    for ore in ores:
        weight = ore["weight"]
        value = ore["value"]
        if total_weight + weight <= capacity and value >= weight:
            commands.append("take")
            total_weight += weight
        else:
            commands.append("skip")
    return commands

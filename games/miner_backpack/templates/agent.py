def solve(ores, capacity):
    # ores - куски руды по порядку:
    # {"weight": вес, "value": ценность}
    # capacity - максимальный вес рюкзака.
    #
    # Верните список команд "take" или "skip".
    # Берем руду, если она помещается и ценность не меньше веса.
    commands = []
    total_weight = 0

    for ore in ores:
        weight = ore["weight"]
        value = ore["value"]
        # TODO: проверьте и вместимость, и ценность.
        commands.append("skip")

    return commands

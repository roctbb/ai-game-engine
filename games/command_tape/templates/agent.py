def run_tape(tape):
    # tape - строка из букв F, L, R, A, C, P и точки.
    # Нужно вернуть список полных команд в том же порядке.
    mapping = {
        "F": "forward",
        "L": "turn_left",
        "R": "turn_right",
        "A": "attack",
        "C": "collect",
        # TODO: добавьте "." -> "wait" и "P" -> "pickup".
    }

    commands = []
    for symbol in tape:
        commands.append(mapping.get(symbol, "forward"))

    return commands

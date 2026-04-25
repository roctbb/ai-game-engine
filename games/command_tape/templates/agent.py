def run_tape(tape):
    # tape - строка из букв F, L, R, A, C.
    # Нужно вернуть список полных команд в том же порядке.
    mapping = {
        "F": "forward",
        "L": "turn_left",
        "R": "turn_right",
        "A": "attack",
        "C": "collect",
    }

    commands = []
    for symbol in tape:
        commands.append(mapping[symbol])

    return commands

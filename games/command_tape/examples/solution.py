def run_tape(tape):
    mapping = {"F": "forward", "L": "turn_left", "R": "turn_right", "A": "attack", "C": "collect", ".": "wait", "P": "pickup"}
    commands = []
    for symbol in tape:
        commands.append(mapping[symbol])
    return commands

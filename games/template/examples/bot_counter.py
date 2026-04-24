def make_choice(state):
    if state["turn"] >= 5:
        return "stop"
    return "inc"

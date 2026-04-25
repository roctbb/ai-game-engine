def make_support(state):
    if state["support"]["boost_cooldown"] != 0:
        return "none"

    own = state.get("self")
    if not own:
        return "none"

    # Бустим не каждый раз: удобнее сохранить ускорение для движения по большой карте.
    if state["tick"] % 12 == 0:
        return "boost"
    return "none"

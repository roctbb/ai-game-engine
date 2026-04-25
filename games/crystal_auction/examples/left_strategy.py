def bid(state):
    value = state["crystal_value"]
    budget = state["budget"]
    rounds_left = state["rounds_left"]
    if rounds_left <= 1:
        return min(budget, value)
    return min(budget, max(1, value // 2))

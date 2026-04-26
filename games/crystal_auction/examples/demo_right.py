def bid(state):
    value = state["crystal_value"]
    budget = state["budget"]
    rounds_left = state["rounds_left"]
    if rounds_left <= 1:
        return min(budget, value)
    if value > state["average_value"]:
        return min(budget, state["fair_bid"] + 2)
    return min(budget, max(1, state["fair_bid"] - 2))

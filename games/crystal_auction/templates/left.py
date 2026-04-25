# Аукцион кристаллов. state содержит crystal_value, budget, rounds_left, my_value.
# Верните целое число - ставку от 0 до budget.

def bid(state):
    value = state["crystal_value"]
    budget = state["budget"]
    rounds_left = state["rounds_left"]

    if rounds_left <= 1:
        return min(budget, value)

    # TODO: придумайте ставку, которая не тратит весь бюджет слишком рано.
    return min(budget, max(1, value // 2))

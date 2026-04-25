# Аукцион кристаллов. state содержит crystal_value, budget, rounds_left, my_value.
# Верните целое число - ставку от 0 до budget.

def bid(state):
    value = state["crystal_value"]
    budget = state["budget"]

    return min(budget, max(1, value // 2))

# Аукцион кристаллов. state содержит crystal_value, budget, rounds_left,
# my_value, fair_bid и average_value.
# Верните целое число - ставку от 0 до budget.

def bid(state):
    value = state["crystal_value"]
    budget = state["budget"]
    rounds_left = state["rounds_left"]
    fair_bid = state["fair_bid"]

    if rounds_left <= 1:
        return min(budget, value)

    # TODO: настройте ставку: хорошие кристаллы можно брать смелее.
    if value > state["average_value"]:
        return min(budget, fair_bid + 2)
    return min(budget, max(1, fair_bid - 2))

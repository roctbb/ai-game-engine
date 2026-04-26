def choose_potion(resources, recipes):
    best_name = None
    best_profit = -1
    costs = {"water": 1, "herb": 2, "crystal": 5, "mushroom": 3}
    for name, recipe in recipes.items():
        can_make = True
        ingredient_cost = 0
        for resource, amount in recipe.items():
            if resource == "value":
                continue
            if resources.get(resource, 0) < amount:
                can_make = False
            ingredient_cost += costs[resource] * amount
        profit = recipe["value"] - ingredient_cost
        if can_make and profit > best_profit:
            best_name = name
            best_profit = profit
    return best_name

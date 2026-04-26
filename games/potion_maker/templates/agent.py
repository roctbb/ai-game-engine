def choose_potion(resources, recipes):
    # resources - сколько ресурсов есть.
    # recipes - рецепты зелий; поле "value" означает ценность, не ингредиент.
    # Стоимости ингредиентов: water=1, herb=2, crystal=5, mushroom=3.
    # Нужно выбрать доступное зелье с максимальной прибылью.
    best_name = None
    best_profit = -1
    costs = {"water": 1, "herb": 2, "crystal": 5, "mushroom": 3}

    for name, recipe in recipes.items():
        can_make = True
        ingredient_cost = 0
        for resource, amount in recipe.items():
            if resource == "value":
                continue
            # TODO: если ресурса не хватает, поставьте can_make = False.
            ingredient_cost += costs[resource] * amount

        profit = recipe["value"] - ingredient_cost
        # TODO: если зелье можно сварить и profit лучше, запомните его.

    return best_name

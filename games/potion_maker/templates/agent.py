def choose_potion(resources, recipes):
    # resources - сколько ресурсов есть.
    # recipes - рецепты зелий; поле "value" означает ценность, не ингредиент.
    best_name = None
    best_value = -1

    for name, recipe in recipes.items():
        can_make = True
        for resource, amount in recipe.items():
            if resource == "value":
                continue
            # TODO: если ресурса не хватает, поставьте can_make = False.

        # TODO: если зелье можно сварить и его value лучше, запомните его.

    return best_name

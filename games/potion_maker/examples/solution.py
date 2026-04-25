def choose_potion(resources, recipes):
    best_name = None
    best_value = -1
    for name, recipe in recipes.items():
        can_make = True
        for resource, amount in recipe.items():
            if resource == "value":
                continue
            if resources.get(resource, 0) < amount:
                can_make = False
        if can_make and recipe["value"] > best_value:
            best_name = name
            best_value = recipe["value"]
    return best_name

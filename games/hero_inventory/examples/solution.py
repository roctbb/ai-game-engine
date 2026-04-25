def choose_item(inventory, situation):
    if situation["hp"] < 40 and "healing_potion" in inventory:
        return "healing_potion"
    elif situation["door"] and "small_key" in inventory:
        return "small_key"
    elif situation["dark"] and "torch" in inventory:
        return "torch"
    return "apple"

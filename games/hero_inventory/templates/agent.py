def choose_item(inventory, situation):
    # Порядок правил важен: здоровье -> дверь -> темнота -> яблоко.
    if situation["hp"] < 40 and "healing_potion" in inventory:
        return "healing_potion"

    # TODO: добавьте правило для двери и ключа.
    # TODO: добавьте правило для темноты и факела.

    return "apple"

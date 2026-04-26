def choose_item(inventory, situation):
    # Порядок правил важен:
    # здоровье -> яд -> дверь -> темнота -> голод -> запасной предмет.
    if situation["hp"] < 40 and "healing_potion" in inventory:
        return "healing_potion"

    # TODO: добавьте правило для отравления и antidote.
    # TODO: добавьте правило для двери и small_key.
    # TODO: добавьте правило для темноты и torch.

    return "apple"

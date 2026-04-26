def choose_action(state):
    # Порядок правил важен:
    # зарядка -> возврат к зарядке -> уборка -> движение -> ожидание.
    if state["battery"] <= 2 and state["on_charger"]:
        return "charge"

    # Если батареи хватает только на путь домой и 1 запасной ход,
    # надо вернуть "return_to_charger".
    # TODO: добавьте это правило через state["distance_to_charger"].

    # TODO: добавьте правило для уборки грязной клетки.
    # TODO: добавьте правило для движения вперед.

    return "wait"

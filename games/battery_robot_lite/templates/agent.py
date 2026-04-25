def choose_action(state):
    # Порядок правил важен: зарядка -> уборка -> движение -> ожидание.
    if state["battery"] <= 2 and state["on_charger"]:
        return "charge"

    # TODO: добавьте правило для уборки грязной клетки.
    # TODO: добавьте правило для движения вперед.

    return "wait"

def make_support(state):
    # Поддержка в новой оболочке оставлена как простой бонус скорости.
    # Основная старая механика танков живет в make_choice водителя.
    if state["support"]["boost_cooldown"] == 0 and state.get("self"):
        return "boost"
    return "none"

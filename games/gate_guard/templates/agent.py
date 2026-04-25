def choose_action(gate):
    # gate - словарь с описанием ворот.
    # gate["color"]   - цвет ворот
    # gate["has_key"] - есть ли ключ
    # gate["trap"]    - есть ли ловушка
    #
    # Правила:
    # red  -> "attack"
    # blue -> "use_key", если ключ есть, иначе "wait"
    # trap -> "disarm"
    # иначе -> "open"
    if gate["color"] == "red":
        return "attack"
    return "open"

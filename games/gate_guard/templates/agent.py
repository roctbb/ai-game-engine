def choose_action(gate):
    # gate - словарь с описанием ситуации у ворот.
    # gate["enemy_distance"] - расстояние до врага
    # gate["trap"]           - есть ли ловушка
    # gate["trap_damage"]    - урон ловушки
    # gate["hp"]             - здоровье героя
    # gate["locked"]         - ворота закрыты
    # gate["has_key"]        - есть ли ключ
    #
    # Приоритеты:
    # 1. Враг рядом -> "attack"
    # 2. Безопасная ловушка -> "disarm"
    # 3. Закрытые ворота и есть ключ -> "use_key"
    # 4. Закрытые ворота без ключа -> "wait"
    # 5. Иначе -> "open"
    if gate["enemy_distance"] <= 1:
        return "attack"

    # TODO: добавьте обработку ловушки и закрытых ворот.
    return "open"

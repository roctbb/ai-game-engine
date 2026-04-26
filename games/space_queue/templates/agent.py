def schedule(ships):
    # ships - список словарей с id, priority, fuel, broken,
    # passengers и service_time.
    # Срочность:
    # priority*10 + passengers*2 + broken*20 + (10 - fuel) - service_time
    # Чем больше срочность, тем раньше корабль.
    # TODO: отсортируйте ships по убыванию срочности.
    ordered = ships

    result = []
    for ship in ordered:
        # В ответ кладем только id, не весь словарь корабля.
        result.append(ship["id"])

    return result

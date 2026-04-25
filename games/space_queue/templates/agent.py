def schedule(ships):
    # ships - список словарей с id, priority, fuel и broken.
    # Чем выше priority, тем раньше корабль. При равенстве раньше меньший fuel.
    # TODO: отсортируйте ships по убыванию priority и возрастанию fuel.
    ordered = ships

    result = []
    for ship in ordered:
        # В ответ кладем только id, не весь словарь корабля.
        result.append(ship["id"])

    return result

def choose_actions(events):
    # events - список событий; в ответ нужен список действий той же длины.
    # Событие - словарь {"type": "...", "noise": число}.
    # type может быть clear, noise, enemy или lost_route.
    actions = []
    alert = 0

    for event in events:
        if event["type"] == "enemy":
            actions.append("attack")
            alert = 0
        else:
            # TODO: обработайте lost_route и накопление тревоги от шума.
            actions.append("patrol")

    return actions

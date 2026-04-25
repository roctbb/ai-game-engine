def choose_actions(events):
    actions = []
    for event in events:
        if event == "enemy":
            actions.append("attack")
        elif event == "lost_route":
            actions.append("return_to_route")
        else:
            actions.append("patrol")
    return actions

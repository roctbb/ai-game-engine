def choose_actions(events):
    actions = []
    alert = 0
    for event in events:
        if event["type"] == "enemy":
            actions.append("attack")
            alert = 0
        elif event["type"] == "lost_route":
            actions.append("return_to_route")
            alert = 0
        elif event["type"] == "noise":
            alert += event["noise"]
            if alert >= 3:
                actions.append("investigate")
            else:
                actions.append("patrol")
        else:
            actions.append("patrol")
    return actions

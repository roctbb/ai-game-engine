def place_tower(state):
    if state["budget"] < 5:
        return None

    lanes_count = state["lanes"]
    pressure = []
    for lane in range(lanes_count):
        pressure.append(0)

    for enemy in state["enemies"]:
        lane = enemy["lane"]
        urgency = enemy["position"] * 3 + enemy["hp"]
        pressure[lane] += urgency

    for lane in range(lanes_count):
        pressure[lane] -= state["towers"][lane] * 2

    best_lane = 0
    best_score = pressure[0]
    for lane in range(1, lanes_count):
        if pressure[lane] > best_score:
            best_lane = lane
            best_score = pressure[lane]

    return best_lane

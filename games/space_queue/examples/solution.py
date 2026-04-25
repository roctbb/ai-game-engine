def schedule(ships):
    ordered = sorted(ships, key=lambda ship: (-ship["priority"], ship["fuel"]))
    result = []
    for ship in ordered:
        result.append(ship["id"])
    return result

def schedule(ships):
    def urgency(ship):
        repair_bonus = 20 if ship["broken"] else 0
        return (
            ship["priority"] * 10
            + ship["passengers"] * 2
            + repair_bonus
            + (10 - ship["fuel"])
            - ship["service_time"]
        )

    ordered = sorted(ships, key=lambda ship: (-urgency(ship), ship["id"]))
    result = []
    for ship in ordered:
        result.append(ship["id"])
    return result

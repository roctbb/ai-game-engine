# ruff: noqa: F821
# travel_time(source, target) предоставляется движком.
def make_move(state):
    me = state["me"]
    orders = []
    for planet in state["planets"]:
        if planet["owner"] != me:
            continue
        targets = [p for p in state["planets"] if p["owner"] != me]
        if not targets:
            continue
        target = min(targets, key=lambda p: travel_time(planet, p))
        ships = planet["ships"] // 2
        if ships > target["ships"]:
            orders.append({"from": planet["id"], "to": target["id"], "ships": ships})
    return orders

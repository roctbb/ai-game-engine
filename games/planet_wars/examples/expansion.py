# ruff: noqa: F821
# travel_time(source, target) предоставляется движком.
def make_move(state):
    me = state["me"]
    mine = [p for p in state["planets"] if p["owner"] == me]
    targets = [p for p in state["planets"] if p["owner"] != me]
    incoming = {}
    for fleet in state["fleets"]:
        if fleet["owner"] == me:
            incoming[fleet["to"]] = incoming.get(fleet["to"], 0) + fleet["ships"]
    orders = []
    for source in mine:
        available = source["ships"] - 6
        best, best_score, needed = None, -1, 0
        for target in targets:
            distance = travel_time(source, target)
            growth = target["production"] * distance if target["owner"] is not None else 0
            cost = target["ships"] + growth + 2 - incoming.get(target["id"], 0)
            if not 0 < cost <= available:
                continue
            value = target["production"] * 10 / (cost + distance * 2)
            if value > best_score:
                best, best_score, needed = target, value, cost
        if best is not None:
            orders.append({"from": source["id"], "to": best["id"], "ships": needed})
            incoming[best["id"]] = incoming.get(best["id"], 0) + needed
        elif available > 15 and targets and len(mine) > 1:
            front = min(mine, key=lambda p: min(travel_time(p, t) for t in targets))
            if source["id"] != front["id"]:
                orders.append({"from": source["id"], "to": front["id"], "ships": available})
    return orders

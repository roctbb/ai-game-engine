def make_move(state):
    position = state["position"]
    goal = state["goal"]
    x0 = position["x"]
    y0 = position["y"]
    goal_x = goal["x"]
    goal_y = goal["y"]

    coins = set()
    for coin in state["coins"]:
        coins.add((coin["x"], coin["y"]))

    scores = {}
    choices = {}
    for x in range(goal_x, x0 - 1, -1):
        for y in range(goal_y, y0 - 1, -1):
            base = 1 if (x, y) in coins else 0
            best_score = -1
            best_action = "right"

            if x == goal_x and y == goal_y:
                scores[(x, y)] = base
                choices[(x, y)] = "right"
                continue

            if x < goal_x:
                right_score = scores[(x + 1, y)]
                if right_score > best_score:
                    best_score = right_score
                    best_action = "right"
            if y < goal_y:
                down_score = scores[(x, y + 1)]
                if down_score > best_score:
                    best_score = down_score
                    best_action = "down"

            scores[(x, y)] = base + best_score
            choices[(x, y)] = best_action

    return choices[(x0, y0)]

def make_move(x, y, board):
    x0 = x
    y0 = y
    goal_x = len(board) - 1
    goal_y = len(board[0]) - 1 if board else 0

    coins = set()
    for xx, column in enumerate(board):
        for yy, cell in enumerate(column):
            if cell == 1:
                coins.add((xx, yy))

    scores = {}
    choices = {}
    for x in range(goal_x, x0 - 1, -1):
        for y in range(goal_y, y0 - 1, -1):
            if board[x][y] == -1:
                scores[(x, y)] = -100000
                choices[(x, y)] = "right"
                continue

            base = 1 if (x, y) in coins else 0
            best_score = -1
            best_action = "right"

            if x == goal_x and y == goal_y:
                scores[(x, y)] = base
                choices[(x, y)] = "right"
                continue

            if x < goal_x:
                right_score = scores.get((x + 1, y), -100000)
                if right_score > best_score:
                    best_score = right_score
                    best_action = "right"
            if y < goal_y:
                down_score = scores.get((x, y + 1), -100000)
                if down_score > best_score:
                    best_score = down_score
                    best_action = "down"

            scores[(x, y)] = base + best_score
            choices[(x, y)] = best_action

    action = choices.get((x0, y0), "right")
    if action == "right" and x0 + 1 <= goal_x and board[x0 + 1][y0] != -1:
        return "right"
    if y0 + 1 <= goal_y and board[x0][y0 + 1] != -1:
        return "down"
    return action

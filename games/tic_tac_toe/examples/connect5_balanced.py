def make_choice(field, role):
    winning_move = find_winning_move(field, role)
    if winning_move is not None:
        return winning_move

    blocking_move = find_winning_move(field, -role)
    if blocking_move is not None:
        return blocking_move

    center = len(field) // 2
    if field[center][center] == 0:
        return center, center

    best_move = None
    best_score = -1
    for x in range(len(field)):
        for y in range(len(field[x])):
            if field[x][y] != 0:
                continue
            score = score_cell(field, x, y, role) + score_cell(field, x, y, -role)
            if score > best_score:
                best_score = score
                best_move = (x, y)

    if best_move is not None:
        return best_move
    return 0, 0


def find_winning_move(field, role):
    for x in range(len(field)):
        for y in range(len(field[x])):
            if field[x][y] != 0:
                continue
            field[x][y] = role
            is_win = has_five(field, role)
            field[x][y] = 0
            if is_win:
                return x, y
    return None


def has_five(field, role):
    directions = ((1, 0), (0, 1), (1, 1), (1, -1))
    for x in range(len(field)):
        for y in range(len(field[x])):
            if field[x][y] != role:
                continue
            for dx, dy in directions:
                if count_line(field, x, y, dx, dy, role) >= 5:
                    return True
    return False


def score_cell(field, x, y, role):
    directions = ((1, 0), (0, 1), (1, 1), (1, -1))
    score = 0
    for dx, dy in directions:
        score += count_from_cell(field, x, y, dx, dy, role)
        score += count_from_cell(field, x, y, -dx, -dy, role)
    return score


def count_line(field, x, y, dx, dy, role):
    count = 0
    while 0 <= x < len(field) and 0 <= y < len(field[x]) and field[x][y] == role:
        count += 1
        x += dx
        y += dy
    return count


def count_from_cell(field, x, y, dx, dy, role):
    count = 0
    x += dx
    y += dy
    while 0 <= x < len(field) and 0 <= y < len(field[x]) and field[x][y] == role:
        count += 1
        x += dx
        y += dy
    return count

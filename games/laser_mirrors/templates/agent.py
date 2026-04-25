# board[x][y]: "." пусто, "/" и "\" зеркала, "#" стена, "T" цель.
# Луч стартует в start_x, start_y и движется на dx, dy.
# Верните True, если луч попадет в цель.

def trace(board, start_x, start_y, dx, dy):
    x = start_x
    y = start_y
    seen = set()

    while 0 <= x < len(board) and 0 <= y < len(board[x]):
        state = (x, y, dx, dy)
        if state in seen:
            return False
        seen.add(state)

        cell = board[x][y]
        if cell == "T":
            return True
        if cell == "#":
            return False
        if cell == "/":
            # TODO: отразите направление от зеркала /.
            dx, dy = -dy, -dx
        elif cell == "\\":
            # TODO: отразите направление от зеркала \.
            dx, dy = dy, dx

        x += dx
        y += dy

    return False

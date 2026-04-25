def trace(board, start_x, start_y, dx, dy):
    x = start_x
    y = start_y
    seen = set()
    while 0 <= x < len(board) and 0 <= y < len(board[x]):
        if (x, y, dx, dy) in seen:
            return False
        seen.add((x, y, dx, dy))
        cell = board[x][y]
        if cell == "T":
            return True
        if cell == "#":
            return False
        if cell == "/":
            dx, dy = -dy, -dx
        elif cell == "\\":
            dx, dy = dy, dx
        x += dx
        y += dy
    return False

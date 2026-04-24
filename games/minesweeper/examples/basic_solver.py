def choose_cell(board, flags_left):
    height = len(board)
    width = len(board[0]) if height else 0

    for y in range(height):
        for x in range(width):
            number = board[y][x]
            if number < 0:
                continue
            unknown = []
            flags = 0
            for ny in range(max(0, y - 1), min(height, y + 2)):
                for nx in range(max(0, x - 1), min(width, x + 2)):
                    if nx == x and ny == y:
                        continue
                    if board[ny][nx] == -2:
                        unknown.append((nx, ny))
                    elif board[ny][nx] == -1:
                        flags += 1
            if unknown and number == flags:
                return unknown[0]
            if unknown and number == flags + len(unknown) and flags_left > 0:
                return ("flag", unknown[0][0], unknown[0][1])

    for y in range(height):
        for x in range(width):
            if board[y][x] == -2:
                return (x, y)
    return (0, 0)

def simulate(board):
    result = []
    for column in board:
        result.append(column[:])
    changed = True
    while changed:
        changed = False
        for x in range(len(result)):
            for y in range(len(result[x]) - 2, -1, -1):
                if result[x][y] == "A" and result[x][y + 1] == ".":
                    result[x][y] = "."
                    result[x][y + 1] = "A"
                    changed = True
    return result

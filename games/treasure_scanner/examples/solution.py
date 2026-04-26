def scan(board):
    column_cost = 3
    row_cost = 5
    best = {"axis": "column", "index": 0, "score": sum(board[0]) - column_cost}
    for x in range(len(board)):
        total = sum(board[x]) - column_cost
        if total > best["score"]:
            best = {"axis": "column", "index": x, "score": total}
    height = len(board[0])
    for y in range(height):
        total = 0
        for x in range(len(board)):
            total += board[x][y]
        total -= row_cost
        if total > best["score"]:
            best = {"axis": "row", "index": y, "score": total}
    return best

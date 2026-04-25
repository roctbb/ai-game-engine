def scan(board):
    # board[x][y]: сначала столбец x, потом строка y.
    # Ответ: {"axis": "column" или "row", "index": номер, "score": сумма}
    best = {"axis": "column", "index": 0, "score": sum(board[0])}

    # Сначала проверяем все столбцы.
    for x in range(len(board)):
        score = sum(board[x])
        if score > best["score"]:
            best = {"axis": "column", "index": x, "score": score}

    # Потом проверяем строки: для строки y собираем board[x][y] по всем x.
    height = len(board[0])
    for y in range(height):
        # TODO: посчитайте сумму строки y по всем столбцам x.
        score = 0
        for x in range(len(board)):
            score += board[x][y]
        # TODO: если сумма строки лучше best["score"], обновите best.

    return best

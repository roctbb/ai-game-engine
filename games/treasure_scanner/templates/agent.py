def scan(board):
    # board[x][y]: сначала столбец x, потом строка y.
    # Столбец стоит 3 энергии, строка стоит 5 энергии.
    # Ответ: {"axis": "column" или "row", "index": номер, "score": прибыль}
    column_cost = 3
    row_cost = 5
    best = {"axis": "column", "index": 0, "score": sum(board[0]) - column_cost}

    # Сначала проверяем все столбцы.
    for x in range(len(board)):
        score = sum(board[x]) - column_cost
        if score > best["score"]:
            best = {"axis": "column", "index": x, "score": score}

    # Потом проверяем строки: для строки y собираем board[x][y] по всем x.
    height = len(board[0])
    for y in range(height):
        # TODO: посчитайте сумму строки y по всем столбцам x.
        score = 0
        for x in range(len(board)):
            score += board[x][y]
        score -= row_cost
        # TODO: если сумма строки лучше best["score"], обновите best.

    return best

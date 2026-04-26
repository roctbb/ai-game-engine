# board[x][y]: "A" яблоко, "." пусто, "#" камень.
# Верните новую карту после падения яблок вниз до устойчивого состояния.

def simulate(board):
    result = []
    for column in board:
        result.append(column[:])

    # TODO: повторяйте проходы, пока яблоки больше не двигаются.
    # Один проход сдвигает яблоки только на одну клетку вниз.
    for x in range(len(result)):
        for y in range(len(result[x]) - 2, -1, -1):
            if result[x][y] == "A" and result[x][y + 1] == ".":
                result[x][y] = "."
                result[x][y + 1] = "A"

    return result

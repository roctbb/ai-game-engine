# mines[x][y] == True, если там мина.
# Верните матрицу чисел: -1 для мины, иначе количество мин вокруг.

def build_numbers(mines):
    width = len(mines)
    height = len(mines[0])
    result = [[0 for y in range(height)] for x in range(width)]

    for x in range(width):
        for y in range(height):
            if mines[x][y]:
                result[x][y] = -1
                continue

            count = 0
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue
                    nx = x + dx
                    ny = y + dy
                    # TODO: проверьте границы и увеличьте count, если рядом мина.
                    if False:
                        count += 1
            result[x][y] = count

    return result

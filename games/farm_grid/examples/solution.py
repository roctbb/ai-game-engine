def count_plants(field):
    total = 0
    for x in range(len(field)):
        for y in range(len(field[x])):
            if field[x][y] == 1:
                total += 1
    return total

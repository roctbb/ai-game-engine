def count_plants(field):
    total = 0
    for x in range(len(field)):
        for y in range(len(field[x])):
            total += field[x][y]
    return total

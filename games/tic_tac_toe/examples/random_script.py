import random


def make_choice(field, role):
    available_positions = []
    for i in range(len(field)):
        for j in range(len(field[0])):
            if field[i][j] == 0:
                available_positions.append((i, j))

    return random.choice(available_positions)

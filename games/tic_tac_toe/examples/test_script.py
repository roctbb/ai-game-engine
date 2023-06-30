import random


def make_choice(field, role):
    available_positions = []
    for i in range(len(field)):
        for j in range(len(field[0])):
            if field[i][j] == 0:
                available_positions.append((i, j))

    if role == -1:
        return available_positions[0]
    else:
        return available_positions[-1]

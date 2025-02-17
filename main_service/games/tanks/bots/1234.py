import random


def make_choice(x, y, field):
    me = field[x][y]['player']

    if me['inventory']:
        return f"use {me['inventory'][0]['type']}"

    return random.choice(["fire_up", "fire_down", "fire_left", "fire_right", "go_up", "go_down", "go_left", "go_right"])

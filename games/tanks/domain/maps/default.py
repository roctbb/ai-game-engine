import imp
import random
from domain.items.coin import Coin
from domain.map import Map
from domain.game import Game
from domain.common import Position, Point, Direction
from domain.objects.wall import Wall
from domain.player import Player

TEMPLATE = """
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
. # # # # # . # # # # . # # # # # .
. # . . . . . . . . . . . . . . # .
. # . . . . . . . . . . . . . . # .
. # . . . . # # # # # # . . . . # .
. # . . . . # . . . . # . . . . # .
. . . . . . . . . . . . . . . . . .
. . . . . . . # . . # . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . # . . # . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . # # . . # # . . . . . .
. # . . . . # . . . . # . . . . # .
. # . . . . . . # # . . . . . . # .
. # . . . . . . # # . . . . . . # .
. # . . . . # . . . . # . . . . # .
. . . . . . # # . . # # . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . # . . # . . . . . . .
. . . . . . . . . . . . . . . . . .
. . . . . . . # . . # . . . . . . .
. . . . . . . . . . . . . . . . . .
. # . . . . # . . . . # . . . . # .
. # . . . . # # # # # # . . . . # .
. # . . . . . . . . . . . . . . # .
. # . . . . . . . . . . . . . . # .
. # # # # # . # # # # . # # # # # .
. . . . . . . . . . . . . . . . . .
. . . . . . . . . . . . . . . . . .
""".strip('\n')


class DefaultMap(Map):
    @classmethod
    def init(cls, game: Game, players):
        template = TEMPLATE.replace(' ', '')
        rows = template.split('\n')

        width = len(rows)
        height = len(rows[0])
        game.size = (width, height)

        for i in range(len(rows)):
            for j in range(len(rows[i])):
                if rows[i][j] == '#':
                    game.objects[(i, j)] = Wall()

        for i in range(10):
            while True:
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)

                if (x, y) in game.objects:
                    continue

                game.items[(x, y)] = Coin()
                break

        for player in players:
            while True:
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)

                if (x, y) in game.objects or (x, y) in game.items:
                    continue

                game.players[(x, y)] = Player(player)
                break

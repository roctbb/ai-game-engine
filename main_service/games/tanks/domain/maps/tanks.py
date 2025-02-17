import imp
import random
import sys
from domain.items.coin import Coin
from domain.items.healthkit import HealthKit
from domain.items.sniper import SniperBooster
from domain.map import Map
from domain.game import Game
from domain.common import Position, Point, Direction
from domain.objects.Snow import Snow
from domain.objects.ancients import RadientAncient, DareAncient
from domain.objects.road import Road
from domain.objects.rocks import Rocks
from domain.objects.stump import Stump
from domain.objects.tree import Tree
from domain.objects.wall import Wall
from domain.objects.water import Water
from domain.player import Player
from domain.units.tower import Tower

TEMPLATE = """
#.....#.....#....#.....#......
.#.....#.....#..#.....#.......
..###...................w###..
..#.....................www#..
..#.ttt...tttt..ttt...ttttw#..
....t....................tw...
....t....................tw...
.#.....#######..#######.www.#.
#......#..............#.w....#
....t..#.##........##.#.wt....
....t..#..#.##..##.#..#.wt....
..#.t..##.#.#....#.#.##.wt.#..
.##.......#........#.......##.
#.#.......#........#.......#.#
..#.t..##.#.#....#.#.##.wt.#..
....t..#..#.##..##.#..#.wt....
....t..#.##........##.#.wt....
.#..t..#..............#.w...#.
#...t..#######..#######.w....#
....t...................w.....
..#.tttt................w..#..
..#.........##TT##......w..#..
..###.......#w..w#wwwwwww###..
............T.DD.T............
............T.DD.T............
..###wwwwwww#w..w#.......###..
..#..w......##TT##.........#..
..#..w................tttt.#..
.....w...................t....
#....w.#######..#######..t...#
.#...w.#..............#..t..#.
....tw.#.##........##.#..t....
....tw.#..#.##..##.#..#..t....
..#.tw.##.#.#....#.#.##..t.#..
#.#.......#........#.......#.#
.##.......#........#.......##.
..#..w.##.#.#....#.#.##..t.#..
....tw.#..#.##..##.#..#..t....
....tw.#.##........##.#..t....
.....w.#..............#.......
#..www.#######...............#
.#.wt....................t..#.
...wt....................t....
..#wtttt...ttt..ttt...tttt.#..
..#www.....................#..
..###w...................###..
.......#.....#..#.....#.....#.
......#.....#....#.....#.....#
""".strip('\n')

BACKGROUND = """
rrrrrrrrrrrrrrrrrrrrrrrrrrrrrr
rrrrrrrrrrrrrrrrrrrrrrrrrrrrrr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rr.....rrrrrrrrrrrrrrrr.....rr
rr.....rrrrrrrrrrrrrrrr.....rr
rr.....rrrrrrrrrrrrrrrr.....rr
rrrr...rrrrrrrrrrrrrrrr...rrrr
rr.r.,.rrrrrrrrrrrrrrrr...r.rr
rr.rrrrrrrrrrrrrrrrrrrrrrrr.rr
rr.rrrrrrrrrrrrrrrrrrrrrrrr.rr
rr.r...rrrrrrrrrrrrrrrr...r.rr
rrrr...rrrrrrrrrrrrrrrr...rrrr
rr.....rrrrrrrrrrrrrrrr.....rr
rr.....rrrrrrrrrrrrrrrr.....rr
rr.....rrrrrrrrrrrrrrrr.....rr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rrrrrrrrrrrrrrrrrrrrrrrrrrrrrr
rrrrrrrrrrrrrrrrrrrrrrrrrrrrrr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rr.....rrrrrrrrrrrrrrrr.....rr
rr.....rrrrrrrrrrrrrrrr.....rr
rr.....rrrrrrrrrrrrrrrr.....rr
rrrr...rrrrrrrrrrrrrrrr...rrrr
rr.r...rrrrrrrrrrrrrrrr...r.rr
rr.rrrrrrrrrrrrrrrrrrrrrrrr.rr
rr.rrrrrrrrrrrrrrrrrrrrrrrr.rr
rr.r...rrrrrrrrrrrrrrrr...r.rr
rrrr...rrrrrrrrrrrrrrrr...rrrr
rr.....rrrrrrrrrrrrrrrr.....rr
rr.....rrrrrrrrrrrrrrrr.....rr
rr.....rrrrrrrrrrrrrrrr.....rr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rr............rr............rr
rrrrrrrrrrrrrrrrrrrrrrrrrrrrrr
rrrrrrrrrrrrrrrrrrrrrrrrrrrrrr
""".strip('\n')

TYPES = {
    '#': Wall,
    'w': Water,
    't': Tree,
    'r': Road,
    's': Stump,
    'k': Rocks,
    'R': RadientAncient,
    'D': DareAncient,
    '*': Snow
}


class TankMap(Map):
    @classmethod
    def init(cls, game: Game, players):

        print("initing BigMap")

        for template, target in ((BACKGROUND, game.backgrounds), (TEMPLATE, game.objects)):

            template = template.replace(' ', '')
            rows = template.split('\n')

            width = len(rows)
            height = len(rows[0])
            game.size = (width, height)

            for i in range(len(rows)):
                for j in range(len(rows[i])):
                    if rows[i][j] in TYPES:
                        target[(i, j)] = TYPES[rows[i][j]]()

        template = TEMPLATE.replace(' ', '')
        rows = template.split('\n')

        for i in range(len(rows)):
            for j in range(len(rows[i])):
                if rows[i][j] == 'T':
                    game.players[(i, j)] = Tower('Dare')

        for i in range(30):
            i = 0
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)

            if (x, y) in game.objects or (x, y) in game.items or (x, y) in game.players:
                continue

            game.objects[(x, y)] = Coin()



        for player in players:
            i = 0
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)

            if (x, y) in game.objects or (x, y) in game.items or (x, y) in game.players:
                continue

            game.players[(x, y)] = Player(player, {"team": 'Radient'})
            i += 1

        print("game is ready")
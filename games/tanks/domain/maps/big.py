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
....................
..tttttttttttttttt..
..tt............tt..
..t...########...t..
......#......#......
..t...T..DD..T...s..
..s...T..DD..T...t..
..t...#......#...t..
..t...###TT###...t..
..tt............tt..
..ttt.stt..ttt.ktt..
....................
.##ttttt....ttttt##.
...t...t....t...t...
.#.t.t.t....t.t.t.#.
.#...t.t....t.t...#.
##tttt........tttt##
................k...
.....TT........k.k..
ttt...........k.k...
..t..........wwwwwsw
.............wwwwwsw
..t..........wwk....
ttt........wwww.....
ttt........wwww.....
..t........ww.......
...........wwTT.....
..t..............ttt
ttt..............t..
.....TT....ww.......
...........ww....t..
wswwwwwwwwwww....ttt
wswwwwwwwwwww....ttt
...k.............t..
.k...k...TT.........
....k............t..
..k..............ttt
...k.k.......TT.....
....k...............
##tttt........tttt##
.#...t.t....t.t...#.
.#.t.t.t....t.t.t.#.
...t...t....t...t...
.##ttttt....ttttt##.
....................
..ttt.stt..ttt.ktt..
..tt............tt..
..t...###TT###...t..
......#......#......
..t...T..RR..T...s..
..s...T..RR..T...t..
..t...#......#...t..
..t...########...t..
..tt............tt..
..tttttttttttttttt..
....................
""".strip('\n')

BACKGROUND = """
....................
....................
....................
......rrrrrrrr......
......rrrrrrrr......
......rrrrrrrr......
......rrrrrrrr......
......rrrrrrrr......
......rrrrrrrr......
.........rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.....k...
.........rr....k.k..
.....rrrrrr...k.k...
.....rrrrrr.......w.
.....rr...........w.
.....rr........k....
.....rr.............
.....rr.............
.....rr.............
.....rr.............
.....rrrrrrrrrr.....
.....rrrrrrrrrr.....
.............rr.....
.............rr.....
.w...........rr.....
.w...........rr.....
...k.........rr.....
.k...k.......rr.....
....k....rrrrrr.....
..k......rrrrrr.....
...k.k...rr.........
....k....rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.........
.........rr.........
......rrrrrrrr......
......rrrrrrrr......
......rrrrrrrr......
......rrrrrrrr......
......rrrrrrrr......
......rrrrrrrr......
....................
....................
....................
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


class BigMap(Map):
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
                    game.players[(i, j)] = Tower('Radient' if i >= width // 2 else 'Dare')

        for i in range(20):
            while True:
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)

                if (x, y) in game.objects or (x, y) in game.items or (x, y) in game.players:
                    continue

                game.items[(x, y)] = SniperBooster()
                break

        for i in range(20):
            while True:
                x = random.randint(0, width - 1)
                y = random.randint(0, height - 1)

                if (x, y) in game.objects or (x, y) in game.items or (x, y) in game.players:
                    continue

                game.items[(x, y)] = HealthKit()
                break

        for player in players:
            i = 0
            x = random.randint(0, width - 1)
            y = random.randint(0, height - 1)

            if (x, y) in game.objects or (x, y) in game.items or (x, y) in game.players:
                continue

            game.players[(x, y)] = Player(player, {"team": 'Radient' if i % 2 == 0 else 'Dare'})
            i += 1

        print("game is ready")